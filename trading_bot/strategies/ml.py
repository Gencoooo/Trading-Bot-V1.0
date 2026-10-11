"""Machine-learning "prediction bots" as they are commonly published on GitHub,
Kaggle, TradingView and in Freqtrade's FreqAI - but trained the honest way:

* strictly **walk-forward**: a model is only ever trained on data that was
  available at that time and is re-trained on a fixed calendar schedule,
* labels that look into the future are **purged** from the training window,
* feature scaling is fitted on the training window only (no global MinMax
  scaling - the bug behind many too-good-to-be-true public backtests).
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

from .. import indicators as ta
from ..backtest import ExitRules, Signals
from ..data import INTERVAL_MINUTES
from .base import Strategy, add


def bars_per_day(interval: str) -> float:
    return 1440.0 / INTERVAL_MINUTES[interval]


def make_features(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    """Causal, scale-free feature set shared by the ML bots."""
    close = df["close"]
    logc = np.log(close)
    r1 = logc.diff()
    f: dict[str, pd.Series] = {}
    for k in (1, 2, 3, 5, 10, 20, 50):
        f[f"ret_{k}"] = logc.diff(k)
    f["vol_10"] = r1.rolling(10).std()
    f["vol_30"] = r1.rolling(30).std()
    f["vol_ratio"] = f["vol_10"] / f["vol_30"]
    f["rsi_14"] = ta.rsi(close, 14) / 100 - 0.5
    f["rsi_7"] = ta.rsi(close, 7) / 100 - 0.5
    f["macd_hist"] = ta.macd(close)["hist"] / close
    bb = ta.bollinger(close, 20)
    width = (bb["upper"] - bb["lower"]).replace(0, np.nan)
    f["bb_pos"] = (close - bb["lower"]) / width - 0.5
    f["bb_width"] = width / bb["mid"]
    f["atr_pct"] = ta.atr(df, 14) / close
    a = ta.adx(df, 14)
    f["adx"] = a["adx"] / 100
    f["di_diff"] = (a["plus_di"] - a["minus_di"]) / 100
    for n in (20, 50, 200):
        f[f"dist_sma{n}"] = close / ta.sma(close, n) - 1
    lv = np.log1p(df["volume"])
    f["volume_z"] = (lv - lv.rolling(20).mean()) / lv.rolling(20).std()
    f["stoch_k"] = ta.stoch_fast(df, 14, 3)["fastk"] / 100 - 0.5
    f["er_20"] = ta.efficiency_ratio(close, 20)
    dow = df.index.dayofweek.to_numpy()
    f["dow_sin"] = pd.Series(np.sin(2 * np.pi * dow / 7), index=df.index)
    f["dow_cos"] = pd.Series(np.cos(2 * np.pi * dow / 7), index=df.index)
    if INTERVAL_MINUTES[interval] < 1440:
        hour = df.index.hour.to_numpy()
        f["hour_sin"] = pd.Series(np.sin(2 * np.pi * hour / 24), index=df.index)
        f["hour_cos"] = pd.Series(np.cos(2 * np.pi * hour / 24), index=df.index)
    return pd.DataFrame(f, index=df.index).replace([np.inf, -np.inf], np.nan)


class WalkForwardStrategy(Strategy):
    """Generic walk-forward trainer. Subclasses provide labels, fit and predict."""

    family = "ml"
    horizon = 1              # label horizon in bars (purge length)
    retrain_days = 90        # re-train cadence (calendar days)
    train_days = 730         # rolling training window (calendar days)
    min_train_days = 365     # first model needs at least this much history
    max_train_samples = 12000

    def labels(self, df: pd.DataFrame) -> pd.Series:
        fwd = df["close"].shift(-self.horizon) / df["close"] - 1
        return (fwd > 0).astype(float).where(fwd.notna())

    def features(self, df: pd.DataFrame, interval: str) -> pd.DataFrame:
        return make_features(df, interval)

    def fit(self, X: np.ndarray, y: np.ndarray):  # pragma: no cover
        raise NotImplementedError

    def predict(self, model, X: np.ndarray, rows: np.ndarray) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    def predict_series(self, df: pd.DataFrame, interval: str) -> np.ndarray:
        X = self.features(df, interval).to_numpy(dtype=float)
        y = self.labels(df).to_numpy(dtype=float)
        n = len(df)
        self._X = X
        valid = self.valid_rows(X)
        preds = np.full(n, np.nan)
        if not valid.any():
            return preds
        bpd = bars_per_day(interval)
        step = max(int(self.retrain_days * bpd), 1)
        window = min(int(self.train_days * bpd), self.max_train_samples)
        first = int(np.argmax(valid))
        start = first + max(int(self.min_train_days * bpd), 300) + self.horizon
        for T in range(start, n, step):
            lo = max(0, T - self.horizon - window)
            idx = np.arange(lo, T - self.horizon)
            idx = idx[valid[idx] & ~np.isnan(y[idx])]
            if len(idx) < 200 or (self.is_classifier and len(np.unique(y[idx])) < 2):
                continue
            model = self.fit(X[idx], y[idx], idx) if self.wants_index else self.fit(X[idx], y[idx])
            rows = np.arange(T, min(T + step, n))
            rows = rows[valid[rows]]
            if len(rows):
                preds[rows] = self.predict(model, X[rows], rows)
        return preds

    is_classifier = True
    wants_index = False

    def valid_rows(self, X: np.ndarray) -> np.ndarray:
        return ~np.isnan(X).any(axis=1)

    def generate(self, df, interval):
        p = self.predict_series(df, interval)
        return Signals(target=np.where(np.isnan(p), 0.0, (p > 0.5).astype(float)))


class LogisticBot(WalkForwardStrategy):
    source = "Typischer 'ML Trading Bot' (scikit-learn LogisticRegression auf TA-Features)"
    description = "Logistische Regression sagt die Richtung der nächsten Kerze voraus; long wenn P(up)>0.5."
    retrain_days = 30

    def fit(self, X, y):
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        model = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=300))
        return model.fit(X, y)

    def predict(self, model, X, rows):
        return model.predict_proba(X)[:, 1]


class RandomForestBot(WalkForwardStrategy):
    source = "GitHub-Klassiker 'Random Forest Stock/Crypto Prediction' (scikit-learn)"
    description = "Random Forest klassifiziert die nächste Kerze (hoch/runter); long wenn P(up)>0.5."

    def fit(self, X, y):
        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(n_estimators=100, max_depth=6, min_samples_leaf=50,
                                       max_features="sqrt", n_jobs=1, random_state=0)
        return model.fit(X, y)

    def predict(self, model, X, rows):
        return model.predict_proba(X)[:, 1]


class FreqAILightGBM(WalkForwardStrategy):
    source = "Freqtrade FreqAI (FreqaiExampleStrategy + LightGBMRegressor, DI-Ausreißerfilter)"
    description = ("LightGBM sagt die mittlere Rendite der nächsten 24 Kerzen voraus; Kauf bei >1 % "
                   "(nur wenn der Dissimilarity-Index < 1), Verkauf bei <0.")
    horizon = 24
    retrain_days = 30
    is_classifier = False
    entry_threshold = 0.01
    di_threshold = 1.0

    def labels(self, df):
        close = df["close"]
        fut_mean = close[::-1].rolling(self.horizon, min_periods=self.horizon).mean()[::-1].shift(-1)
        return fut_mean / close - 1

    def fit(self, X, y):
        import lightgbm as lgb
        mu, sd = X.mean(axis=0), X.std(axis=0) + 1e-12
        Z = (X - mu) / sd
        rng = np.random.default_rng(0)
        ref = Z[rng.choice(len(Z), size=min(len(Z), 1500), replace=False)]
        # characteristic distance: mean pairwise distance inside the training set
        d = np.sqrt(((ref[:400, None, :] - ref[None, :400, :]) ** 2).sum(-1))
        char_dist = d[np.triu_indices_from(d, 1)].mean()
        model = lgb.LGBMRegressor(n_estimators=200, learning_rate=0.05, num_leaves=31, subsample=0.8,
                                  subsample_freq=1, colsample_bytree=0.8, verbose=-1, n_jobs=1,
                                  random_state=0)
        model.fit(X, y)
        return model, mu, sd, ref, char_dist

    def predict(self, bundle, X, rows):
        model, mu, sd, ref, char_dist = bundle
        pred = model.predict(X)
        Z = (X - mu) / sd
        # distance to the nearest training point, via |a-b|^2 = |a|^2 + |b|^2 - 2ab
        sq = (Z ** 2).sum(1)[:, None] + (ref ** 2).sum(1)[None, :] - 2.0 * Z @ ref.T
        di = np.sqrt(np.maximum(sq.min(axis=1), 0.0)) / char_dist
        return np.where(di < self.di_threshold, pred, np.nan)  # NaN = do_predict 0

    def generate(self, df, interval):
        p = self.predict_series(df, interval)
        entries = np.nan_to_num(p, nan=-1.0) > self.entry_threshold
        exits = np.nan_to_num(p, nan=1.0) < 0.0
        return Signals(entries=entries, exits=exits)


class LSTMBot(WalkForwardStrategy):
    source = "Die populären 'LSTM Bitcoin Price Prediction'-Repos/Tutorials (PyTorch)"
    description = ("LSTM über die letzten 32 Kerzen sagt die nächste Kerzenrichtung voraus; long wenn P(up)>0.5. "
                   "Skalierung nur auf dem Trainingsfenster.")
    seq_len = 32
    epochs = 6
    hidden = 32
    wants_index = True
    feature_cols = ("ret_1", "ret_5", "ret_20", "vol_10", "rsi_14", "macd_hist", "bb_pos", "volume_z",
                    "dist_sma20", "dist_sma50")

    def features(self, df, interval):
        return make_features(df, interval)[list(self.feature_cols)]

    def valid_rows(self, X):
        ok = ~np.isnan(X).any(axis=1)
        # a sequence ending at t is valid only if the whole window is valid
        run = pd.Series(ok.astype(float)).rolling(self.seq_len, min_periods=self.seq_len).min()
        return run.fillna(0).to_numpy().astype(bool)

    def _windows(self, Z: np.ndarray, rows: np.ndarray) -> np.ndarray:
        L = self.seq_len
        offs = np.arange(-L + 1, 1)
        return Z[rows[:, None] + offs[None, :]]  # (m, L, f)

    def fit(self, X, y, idx):
        import torch
        from torch import nn
        torch.manual_seed(0)
        if os.environ.get("TB_TORCH_THREADS"):
            torch.set_num_threads(int(os.environ["TB_TORCH_THREADS"]))
        full = self._X
        mu = np.nanmean(full[idx], axis=0)
        sd = np.nanstd(full[idx], axis=0) + 1e-9
        Z = np.nan_to_num((full - mu) / sd)
        seqs = torch.tensor(self._windows(Z, idx), dtype=torch.float32)
        target = torch.tensor(y, dtype=torch.float32)

        class Net(nn.Module):
            def __init__(self, n_in, hidden):
                super().__init__()
                self.lstm = nn.LSTM(n_in, hidden, batch_first=True)
                self.head = nn.Linear(hidden, 1)

            def forward(self, x):
                out, _ = self.lstm(x)
                return self.head(out[:, -1, :]).squeeze(-1)

        net = Net(seqs.shape[-1], self.hidden)
        opt = torch.optim.Adam(net.parameters(), lr=2e-3)
        loss_fn = nn.BCEWithLogitsLoss()
        gen = torch.Generator().manual_seed(0)
        for _ in range(self.epochs):
            perm = torch.randperm(len(seqs), generator=gen)
            for b in range(0, len(seqs), 256):
                sel = perm[b:b + 256]
                opt.zero_grad()
                loss = loss_fn(net(seqs[sel]), target[sel])
                loss.backward()
                opt.step()
        net.eval()
        return net, Z

    def predict(self, bundle, X, rows):
        import torch
        net, Z = bundle
        with torch.no_grad():
            logits = net(torch.tensor(self._windows(Z, rows), dtype=torch.float32))
        return torch.sigmoid(logits).numpy()


class LorentzianKNN(Strategy):
    family = "ml"
    source = "TradingView 'Machine Learning: Lorentzian Classification' (jdehorty) - Re-Implementierung"
    description = ("k-NN (k=8) mit Lorentz-Distanz über RSI/WT/CCI/ADX-Features der letzten 2000 Kerzen "
                   "(jede 4.), Original-Label, Volatilitäts- und Kernel-Filter, 4 Kerzen Haltedauer.")

    def __init__(self, k=8, max_bars_back=2000, hold=4, **kw):
        super().__init__(k=k, max_bars_back=max_bars_back, hold=hold, **kw)

    @staticmethod
    def _features(df):
        close = df["close"]
        hlc3 = ta.typical_price(df)
        n_rsi14 = ta.rsi(close, 14) / 100
        n_rsi9 = ta.rsi(close, 9) / 100
        wt = ta.wavetrend(df, 10, 11)
        n_wt = ta.expanding_minmax_normalize(wt["wt1"] - wt["wt2"])
        n_cci = ta.expanding_minmax_normalize(ta.cci(df, 20))
        n_adx = ta.adx(df, 20)["adx"] / 100
        del hlc3
        return pd.concat([n_rsi14, n_wt, n_cci, n_adx, n_rsi9], axis=1).to_numpy(float)

    @staticmethod
    def _kernel(close: pd.Series, h=8.0, r=8.0, x=25) -> pd.Series:
        """Nadaraya-Watson estimate with a rational quadratic kernel (non-repainting)."""
        i = np.arange(x + 2, dtype=float)
        w = (1 + i ** 2 / (h ** 2 * 2 * r)) ** (-r)
        vals = close.to_numpy(float)
        out = np.full(len(vals), np.nan)
        for t in range(len(i) - 1, len(vals)):
            out[t] = vals[t - len(i) + 1:t + 1][::-1] @ w / w.sum()
        return pd.Series(out, index=close.index)

    def generate(self, df, interval):
        k, mbb, hold = self.params["k"], self.params["max_bars_back"], self.params["hold"]
        F = self._features(df)
        close = df["close"].to_numpy(float)
        n = len(df)
        # original label: direction of the *past* 4 bars, inverted (src[4] < src[0] -> short)
        label = np.zeros(n)
        label[4:] = np.where(close[:-4] < close[4:], -1.0, np.where(close[:-4] > close[4:], 1.0, 0.0))
        valid = ~np.isnan(F).any(axis=1)
        pred = np.zeros(n)
        for t in range(n):
            if not valid[t]:
                continue
            cand = np.arange(t - 4, max(t - mbb, -1), -4)
            cand = cand[cand >= 0]
            cand = cand[valid[cand]]
            if len(cand) < k:
                continue
            d = np.log1p(np.abs(F[cand] - F[t])).sum(axis=1)
            nn_idx = cand[np.argpartition(d, k - 1)[:k]]
            pred[t] = label[nn_idx].sum()
        atr1, atr10 = ta.atr(df, 1), ta.atr(df, 10)
        vol_ok = (atr1 > atr10).to_numpy()
        yhat = self._kernel(df["close"])
        bullish = (yhat > yhat.shift(1)).to_numpy()
        entries = (pred > 0) & vol_ok & bullish
        exits = (pred < 0) & vol_ok
        return Signals(entries=entries, exits=exits, rules=ExitRules(max_bars=hold))


class ARForecast(WalkForwardStrategy):
    source = "Statistische Prognose-Bots (ARIMA/AR-Modelle auf Renditen)"
    description = "AR(5)-Modell auf Log-Renditen, walk-forward neu geschätzt; long wenn die Prognose > 0."
    retrain_days = 30
    is_classifier = False
    lags = 5

    def labels(self, df):
        return np.log(df["close"]).diff().shift(-1)

    def features(self, df, interval):
        r = np.log(df["close"]).diff()
        return pd.concat({f"lag{i}": r.shift(i) for i in range(self.lags)}, axis=1)

    def fit(self, X, y):
        A = np.column_stack([np.ones(len(X)), X])
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        return coef

    def predict(self, coef, X, rows):
        return np.column_stack([np.ones(len(X)), X]) @ coef

    def generate(self, df, interval):
        p = self.predict_series(df, interval)
        return Signals(target=np.where(np.isnan(p), 0.0, (p > 0).astype(float)))


class LeakyTutorialRF(Strategy):
    """DELIBERATELY WRONG - shows why so many public ML bots look spectacular.

    Mimics the most common tutorial mistake: ``train_test_split(shuffle=True)`` on
    time-series data and then "backtesting" the model on data it has (partly) seen.
    The causality test flags it; it is excluded from all rankings."""

    family = "demo"
    source = "Typischer Tutorial-Fehler (train_test_split(shuffle=True), Backtest auf Trainingsdaten)"
    description = "Abschreckendes Beispiel mit Look-ahead-Bias - nicht handelbar."

    def generate(self, df, interval):
        from sklearn.ensemble import RandomForestClassifier
        X = make_features(df, interval)
        fwd = df["close"].shift(-1) / df["close"] - 1
        ok = X.notna().all(axis=1) & fwd.notna()
        rng = np.random.default_rng(0)
        train = ok & (rng.random(len(df)) < 0.7)  # random 70 % of ALL bars, future included
        model = RandomForestClassifier(n_estimators=100, max_depth=8, min_samples_leaf=5, n_jobs=1, random_state=0)
        model.fit(X[train].to_numpy(), (fwd[train] > 0).astype(int).to_numpy())
        p = np.zeros(len(df))
        valid = X.notna().all(axis=1).to_numpy()
        p[valid] = model.predict_proba(X[valid].to_numpy())[:, 1]
        return Signals(target=(p > 0.5).astype(float))


add("ml_logistic", LogisticBot)
add("ml_random_forest", RandomForestBot)
add("ml_freqai_lightgbm", FreqAILightGBM)
add("ml_lstm", LSTMBot)
add("ml_lorentzian_knn", LorentzianKNN)
add("ml_ar_forecast", ARForecast)
add("demo_leaky_tutorial_rf", LeakyTutorialRF)


def torch_available() -> bool:
    import importlib.util
    return importlib.util.find_spec("torch") is not None


__all__ = ["make_features", "WalkForwardStrategy", "torch_available"]
