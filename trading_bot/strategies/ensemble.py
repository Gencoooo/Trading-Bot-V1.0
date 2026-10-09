"""This project's own bot - designed from the benchmark of all other bots.

Two building blocks are provided:

* :class:`TrendEnsemble` - a vote of several slow trend rules (lookbacks in
  *days*, so the bot behaves the same on 1h, 4h and 1d candles), sized by
  volatility targeting, optionally gated by a Bitcoin market-regime filter,
  traded with a rebalancing band to keep fees low.
* :class:`MetaSelector` - "learn from the other bots" online: every month it
  re-ranks a pool of public bots by their trailing net performance on the coin
  and follows the best ones.

Concrete versions (the evolution documented in the report) are registered at
the bottom of this file.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as ta
from ..backtest import Costs, ExitRules, Signals, run_backtest
from ..data import INTERVAL_MINUTES, load_ohlcv
from .base import Strategy, add, get_strategy


def _bars(days: float, interval: str) -> int:
    return max(int(round(days * 1440 / INTERVAL_MINUTES[interval])), 1)


def btc_close_aligned(df: pd.DataFrame, interval: str) -> pd.Series | None:
    """Bitcoin closes on the asset's timestamps (used as market-regime context)."""
    try:
        btc = load_ohlcv("BTCUSDT", interval)
        if btc.empty or btc.index[-1] < df.index[-1]:
            btc = load_ohlcv("BTCUSDT", interval, update=True)
    except Exception:
        return None
    if btc.empty:
        return None
    return btc["close"].reindex(df.index, method="ffill")


def trend_votes(df: pd.DataFrame, interval: str, components: list[tuple]) -> pd.DataFrame:
    """Each component is a 0/1 'trend is up' vote. Lookbacks are given in days."""
    close = df["close"]
    votes = {}
    for comp in components:
        kind = comp[0]
        if kind == "sma":
            n = _bars(comp[1], interval)
            votes[f"sma{comp[1]}"] = close > ta.sma(close, n)
        elif kind == "ema_cross":
            f, s = _bars(comp[1], interval), _bars(comp[2], interval)
            votes[f"ema{comp[1]}_{comp[2]}"] = ta.ema(close, f) > ta.ema(close, s)
        elif kind == "tsmom":
            n = _bars(comp[1], interval)
            votes[f"tsmom{comp[1]}"] = close > close.shift(n)
        elif kind == "donchian":
            entry_n, exit_n = _bars(comp[1], interval), _bars(comp[2], interval)
            upper = df["high"].rolling(entry_n).max().shift(1)
            lower = df["low"].rolling(exit_n).min().shift(1)
            state = np.zeros(len(df))
            c, up, lo = close.to_numpy(), upper.to_numpy(), lower.to_numpy()
            for i in range(1, len(df)):
                state[i] = state[i - 1]
                if c[i] > up[i]:
                    state[i] = 1.0
                elif c[i] < lo[i]:
                    state[i] = 0.0
            votes[f"donchian{comp[1]}_{comp[2]}"] = pd.Series(state > 0, index=df.index)
        elif kind == "supertrend":
            period = _bars(comp[1], interval)
            votes[f"supertrend{comp[1]}x{comp[2]}"] = ta.supertrend(df, period, comp[2])["direction"] > 0
        else:
            raise ValueError(f"unknown component {kind}")
    out = pd.DataFrame(votes, index=df.index).astype(float)
    # a vote only counts once its indicator has warmed up
    warm = max((_bars(max(x for x in comp[1:] if isinstance(x, (int, float))), interval) for comp in components),
               default=0)
    out.iloc[:warm] = np.nan
    return out


class TrendEnsemble(Strategy):
    family = "ensemble"
    source = "Eigenentwicklung (Trading-Bot-V1.0)"

    def __init__(self, components=(("sma", 50), ("sma", 100), ("sma", 200)), vol_target=None,
                 vol_days=30, max_exposure=1.0, btc_filter=False, btc_days=200, btc_scale=0.0,
                 threshold=0.0, binary=False, band=0.1, stop_atr=None, **kw):
        super().__init__(components=list(components), vol_target=vol_target, vol_days=vol_days,
                         max_exposure=max_exposure, btc_filter=btc_filter, btc_days=btc_days,
                         btc_scale=btc_scale, threshold=threshold, binary=binary, band=band,
                         stop_atr=stop_atr, **kw)

    def exposure(self, df: pd.DataFrame, interval: str) -> pd.Series:
        p = self.params
        votes = trend_votes(df, interval, p["components"])
        score = votes.mean(axis=1)
        if p["binary"]:
            pos = (score > p["threshold"]).astype(float)
        else:
            pos = score.where(score > p["threshold"], 0.0)
        if p["vol_target"]:
            r = np.log(df["close"]).diff()
            per_year = 365 * 1440 / INTERVAL_MINUTES[interval]
            vol = np.sqrt((r ** 2).ewm(span=_bars(p["vol_days"], interval), adjust=False).mean() * per_year)
            pos = pos * (p["vol_target"] / vol.replace(0, np.nan)).clip(upper=p["max_exposure"])
        if p["btc_filter"]:
            btc = btc_close_aligned(df, interval)
            if btc is not None:
                risk_on = btc > ta.sma(btc, _bars(p["btc_days"], interval))
                pos = pos.where(risk_on.fillna(True), pos * p["btc_scale"])
        return pos.clip(lower=0.0, upper=p["max_exposure"]).where(score.notna())

    def generate(self, df, interval):
        pos = self.exposure(df, interval)
        sig = Signals(target=pos.fillna(0.0).to_numpy(), min_rebalance=self.params["band"])
        if self.params["stop_atr"]:
            sig.stop_distance = (self.params["stop_atr"] * ta.atr(df, _bars(20, interval)) / df["close"]).to_numpy()
            sig.rules = ExitRules(trail_stop_loss=True)
        return sig


_CANDIDATES: dict = {"key": None, "runs": {}}


def _candidate_run(name: str, df: pd.DataFrame, interval: str) -> tuple[np.ndarray, np.ndarray]:
    """Exposure and per-bar returns of a candidate bot, cached for the current data set
    (several MetaSelector variants share the same candidate backtests)."""
    key = (interval, len(df), df.index[0], df.index[-1], float(df["close"].iloc[-1]))
    if _CANDIDATES["key"] != key:
        _CANDIDATES["key"], _CANDIDATES["runs"] = key, {}
    if name not in _CANDIDATES["runs"]:
        res = run_backtest(df, get_strategy(name).generate(df, interval), interval, Costs())
        _CANDIDATES["runs"][name] = (res.exposure.to_numpy(), res.equity.pct_change().fillna(0.0).to_numpy())
    return _CANDIDATES["runs"][name]


class MetaSelector(Strategy):
    """Follows the public bots that performed best on this coin recently."""

    family = "ensemble"
    source = "Eigenentwicklung: Online-Auswahl der besten Bots (walk-forward)"

    def __init__(self, candidates=(), lookback_days=180, rebalance_days=30, top_k=3, min_sharpe=0.0,
                 band=0.1, **kw):
        super().__init__(candidates=list(candidates), lookback_days=lookback_days, rebalance_days=rebalance_days,
                         top_k=top_k, min_sharpe=min_sharpe, band=band, **kw)

    def generate(self, df, interval):
        p = self.params
        n = len(df)
        runs = [_candidate_run(name, df, interval) for name in p["candidates"]]
        E = np.array([r[0] for r in runs])
        R = np.array([r[1] for r in runs])
        lb, step = _bars(p["lookback_days"], interval), _bars(p["rebalance_days"], interval)
        bpy = 365 * 1440 / INTERVAL_MINUTES[interval]
        target = np.zeros(n)
        for T in range(lb, n, step):
            window = R[:, T - lb + 1:T + 1]  # returns known at the close of bar T
            sd = window.std(axis=1)
            sharpe = np.where(sd > 0, window.mean(axis=1) / np.where(sd > 0, sd, 1) * np.sqrt(bpy), 0.0)
            order = np.argsort(-sharpe)[:p["top_k"]]
            chosen = [k for k in order if sharpe[k] > p["min_sharpe"]]
            end = min(T + step, n)
            if chosen:
                target[T:end] = E[chosen, T:end].mean(axis=0)
        return Signals(target=np.clip(target, 0.0, 1.0), min_rebalance=p["band"])
