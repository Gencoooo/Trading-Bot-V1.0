"""Technical indicators implemented from scratch (numpy/pandas only).

Conventions follow TA-Lib where it matters for the ported strategies:
RSI, ATR and ADX use Wilder smoothing, Bollinger Bands use the population
standard deviation. Every function is causal: the value at bar ``t`` only uses
data up to and including bar ``t`` (verified by tests/test_causality.py).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view


def _rolling(s: pd.Series, n: int, func) -> pd.Series:
    """Apply ``func`` to all length-``n`` windows at once (func maps (m, n) -> (m,))."""
    arr = s.to_numpy(dtype=float)
    out = np.full(len(arr), np.nan)
    if len(arr) >= n:
        out[n - 1:] = func(sliding_window_view(arr, n))
    return pd.Series(out, index=s.index)


# --------------------------------------------------------------------------- #
# Moving averages
# --------------------------------------------------------------------------- #
def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def wilder(s: pd.Series, n: int) -> pd.Series:
    """Wilder's smoothing (RMA), alpha = 1/n."""
    return s.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def wma(s: pd.Series, n: int) -> pd.Series:
    w = np.arange(1, n + 1, dtype=float)
    return _rolling(s, n, lambda win: win @ w / w.sum())


def hma(s: pd.Series, n: int) -> pd.Series:
    half = max(int(n / 2), 1)
    root = max(int(np.sqrt(n)), 1)
    return wma(2 * wma(s, half) - wma(s, n), root)


def dema(s: pd.Series, n: int) -> pd.Series:
    e1 = ema(s, n)
    return 2 * e1 - ema(e1, n)


def tema(s: pd.Series, n: int) -> pd.Series:
    e1 = ema(s, n)
    e2 = ema(e1, n)
    return 3 * e1 - 3 * e2 + ema(e2, n)


# --------------------------------------------------------------------------- #
# Price transforms
# --------------------------------------------------------------------------- #
def typical_price(df: pd.DataFrame) -> pd.Series:
    return (df["high"] + df["low"] + df["close"]) / 3.0


def hl2(df: pd.DataFrame) -> pd.Series:
    return (df["high"] + df["low"]) / 2.0


def heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    ha_close = ((df["open"] + df["high"] + df["low"] + df["close"]) / 4.0).to_numpy()
    o = df["open"].to_numpy()
    ha_open = np.empty(len(df))
    if len(df):
        ha_open[0] = (o[0] + df["close"].iloc[0]) / 2.0
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0
    ha_high = np.maximum.reduce([df["high"].to_numpy(), ha_open, ha_close])
    ha_low = np.minimum.reduce([df["low"].to_numpy(), ha_open, ha_close])
    return pd.DataFrame({"open": ha_open, "high": ha_high, "low": ha_low, "close": ha_close},
                        index=df.index)


# --------------------------------------------------------------------------- #
# Oscillators
# --------------------------------------------------------------------------- #
def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = wilder(delta.clip(lower=0.0), n)
    loss = wilder((-delta).clip(lower=0.0), n)
    rs = gain / loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    out = out.where(loss != 0.0, 100.0)  # only gains -> RSI 100
    return out.where(gain.notna())


def fisher_rsi(rsi_values: pd.Series) -> pd.Series:
    """Inverse-Fisher transform of RSI used by many Freqtrade strategies, range (-1, 1)."""
    x = 0.1 * (rsi_values - 50.0)
    return np.tanh(x)


def macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(s, fast) - ema(s, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def stoch_fast(df: pd.DataFrame, k: int = 5, d: int = 3) -> pd.DataFrame:
    """TA-Lib STOCHF: fast %K and its SMA (fast %D)."""
    ll = df["low"].rolling(k, min_periods=k).min()
    hh = df["high"].rolling(k, min_periods=k).max()
    fastk = 100.0 * (df["close"] - ll) / (hh - ll).replace(0.0, np.nan)
    return pd.DataFrame({"fastk": fastk, "fastd": sma(fastk, d)})


def stoch(df: pd.DataFrame, k: int = 5, smooth_k: int = 3, d: int = 3) -> pd.DataFrame:
    """TA-Lib STOCH: slow %K = SMA(fast %K), slow %D = SMA(slow %K)."""
    fast = stoch_fast(df, k, 1)
    slowk = sma(fast["fastk"], smooth_k)
    return pd.DataFrame({"slowk": slowk, "slowd": sma(slowk, d)})


def stoch_rsi(s: pd.Series, n: int = 14, k: int = 3, d: int = 3) -> pd.DataFrame:
    r = rsi(s, n)
    lo = r.rolling(n, min_periods=n).min()
    hi = r.rolling(n, min_periods=n).max()
    raw = 100.0 * (r - lo) / (hi - lo).replace(0.0, np.nan)
    kline = sma(raw, k)
    return pd.DataFrame({"k": kline, "d": sma(kline, d)})


def cci(df: pd.DataFrame, n: int = 20) -> pd.Series:
    tp = typical_price(df)
    ma = sma(tp, n)
    md = _rolling(tp, n, lambda win: np.abs(win - win.mean(axis=1, keepdims=True)).mean(axis=1))
    return (tp - ma) / (0.015 * md.replace(0.0, np.nan))


def mfi(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tp = typical_price(df)
    flow = tp * df["volume"]
    up = flow.where(tp > tp.shift(1), 0.0).rolling(n, min_periods=n).sum()
    down = flow.where(tp < tp.shift(1), 0.0).rolling(n, min_periods=n).sum()
    ratio = up / down.replace(0.0, np.nan)
    return (100.0 - 100.0 / (1.0 + ratio)).where(down != 0.0, 100.0).where(up.notna())


def williams_r(df: pd.DataFrame, n: int = 14) -> pd.Series:
    hh = df["high"].rolling(n, min_periods=n).max()
    ll = df["low"].rolling(n, min_periods=n).min()
    return -100.0 * (hh - df["close"]) / (hh - ll).replace(0.0, np.nan)


def momentum(s: pd.Series, n: int = 10) -> pd.Series:
    return s - s.shift(n)


def roc(s: pd.Series, n: int = 10) -> pd.Series:
    return s / s.shift(n) - 1.0


def wavetrend(df: pd.DataFrame, n1: int = 10, n2: int = 21) -> pd.DataFrame:
    """LazyBear's WaveTrend oscillator."""
    ap = typical_price(df)
    esa = ema(ap, n1)
    d = ema((ap - esa).abs(), n1)
    ci = (ap - esa) / (0.015 * d.replace(0.0, np.nan))
    wt1 = ema(ci, n2)
    return pd.DataFrame({"wt1": wt1, "wt2": sma(wt1, 4)})


def awesome_oscillator(df: pd.DataFrame) -> pd.Series:
    mid = hl2(df)
    return sma(mid, 5) - sma(mid, 34)


def obv(df: pd.DataFrame) -> pd.Series:
    """On-balance volume (TA-Lib convention: starts at the first bar's volume)."""
    direction = np.sign(df["close"].diff()).fillna(1.0)
    return (direction * df["volume"]).cumsum()


# --------------------------------------------------------------------------- #
# Volatility & trend strength
# --------------------------------------------------------------------------- #
def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1)
    return tr.max(axis=1, skipna=False).fillna(df["high"] - df["low"])


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return wilder(true_range(df), n)


def bollinger(s: pd.Series, n: int = 20, k: float = 2.0, ddof: int = 0) -> pd.DataFrame:
    mid = sma(s, n)
    sd = s.rolling(n, min_periods=n).std(ddof=ddof)
    return pd.DataFrame({"mid": mid, "upper": mid + k * sd, "lower": mid - k * sd})


def keltner(df: pd.DataFrame, n: int = 20, k: float = 2.0, atr_n: int = 10) -> pd.DataFrame:
    mid = ema(df["close"], n)
    a = atr(df, atr_n)
    return pd.DataFrame({"mid": mid, "upper": mid + k * a, "lower": mid - k * a})


def donchian(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    upper = df["high"].rolling(n, min_periods=n).max()
    lower = df["low"].rolling(n, min_periods=n).min()
    return pd.DataFrame({"upper": upper, "lower": lower, "mid": (upper + lower) / 2.0})


def adx(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr = wilder(true_range(df), n)
    plus_di = 100.0 * wilder(plus_dm, n) / tr.replace(0.0, np.nan)
    minus_di = 100.0 * wilder(minus_dm, n) / tr.replace(0.0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return pd.DataFrame({"adx": wilder(dx, n), "plus_di": plus_di, "minus_di": minus_di})


def efficiency_ratio(s: pd.Series, n: int = 20) -> pd.Series:
    """Kaufman efficiency ratio: |net move| / path length, in [0, 1]. High = trending."""
    change = (s - s.shift(n)).abs()
    path = s.diff().abs().rolling(n, min_periods=n).sum()
    return change / path.replace(0.0, np.nan)


def realized_vol(s: pd.Series, n: int = 20) -> pd.Series:
    return np.log(s).diff().rolling(n, min_periods=n).std()


def linreg(s: pd.Series, n: int) -> pd.Series:
    """Value of the least-squares line at the last bar of each window (Pine ``linreg(s, n, 0)``)."""
    x = np.arange(n, dtype=float)
    xc = x - x.mean()
    denom = (xc ** 2).sum()

    def _last(win: np.ndarray) -> np.ndarray:
        slope = win @ xc / denom
        return win.mean(axis=1) + slope * xc[-1]

    return _rolling(s, n, _last)


# --------------------------------------------------------------------------- #
# Path-dependent trend indicators
# --------------------------------------------------------------------------- #
def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """Classic Supertrend. ``direction`` is +1 (up-trend) or -1 (down-trend)."""
    a = atr(df, period).to_numpy()
    mid = hl2(df).to_numpy()
    close = df["close"].to_numpy()
    n = len(df)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    line = np.full(n, np.nan)
    direction = np.zeros(n)
    for i in range(n):
        if np.isnan(a[i]):
            continue
        bu = mid[i] + multiplier * a[i]
        bl = mid[i] - multiplier * a[i]
        if i == 0 or np.isnan(upper[i - 1]):
            upper[i], lower[i], direction[i] = bu, bl, 1.0
        else:
            upper[i] = bu if (bu < upper[i - 1] or close[i - 1] > upper[i - 1]) else upper[i - 1]
            lower[i] = bl if (bl > lower[i - 1] or close[i - 1] < lower[i - 1]) else lower[i - 1]
            if direction[i - 1] > 0:
                direction[i] = -1.0 if close[i] < lower[i] else 1.0
            else:
                direction[i] = 1.0 if close[i] > upper[i] else -1.0
        line[i] = lower[i] if direction[i] > 0 else upper[i]
    return pd.DataFrame({"supertrend": line, "direction": direction}, index=df.index)


def psar(df: pd.DataFrame, step: float = 0.02, max_step: float = 0.2) -> pd.Series:
    """Parabolic SAR, a line-by-line port of TA-Lib's ``SAR`` (value for bar t is
    the stop computed with data up to bar t-1, after a possible reversal at t)."""
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(df)
    out = np.full(n, np.nan)
    if n < 2:
        return pd.Series(out, index=df.index)
    up, down = high[1] - high[0], low[0] - low[1]
    minus_dm = down if (down > up and down > 0) else 0.0
    is_long = not minus_dm > 0
    if is_long:
        ep, sar = high[1], low[0]
    else:
        ep, sar = low[1], high[0]
    af = step
    new_low, new_high = low[1], high[1]
    for i in range(1, n):
        prev_low, prev_high = new_low, new_high
        new_low, new_high = low[i], high[i]
        if is_long:
            if new_low <= sar:  # reversal to short
                is_long = False
                sar = max(ep, prev_high, new_high)
                out[i] = sar
                af, ep = step, new_low
                sar = max(sar + af * (ep - sar), prev_high, new_high)
            else:
                out[i] = sar
                if new_high > ep:
                    ep, af = new_high, min(af + step, max_step)
                sar = min(sar + af * (ep - sar), prev_low, new_low)
        else:
            if new_high >= sar:  # reversal to long
                is_long = True
                sar = min(ep, prev_low, new_low)
                out[i] = sar
                af, ep = step, new_high
                sar = min(sar + af * (ep - sar), prev_low, new_low)
            else:
                out[i] = sar
                if new_low < ep:
                    ep, af = new_low, min(af + step, max_step)
                sar = max(sar + af * (ep - sar), prev_high, new_high)
    return pd.Series(out, index=df.index)


def atr_trailing_stop(df: pd.DataFrame, key: float = 1.0, period: int = 10) -> pd.DataFrame:
    """ATR trailing stop of the popular 'UT Bot Alerts' TradingView script."""
    close = df["close"].to_numpy()
    nloss = key * atr(df, period).to_numpy()
    n = len(df)
    stop = np.full(n, np.nan)
    for i in range(n):
        if np.isnan(nloss[i]):
            continue
        prev = stop[i - 1] if i > 0 and not np.isnan(stop[i - 1]) else 0.0
        pc = close[i - 1] if i > 0 else close[i]
        if close[i] > prev and pc > prev:
            stop[i] = max(prev, close[i] - nloss[i])
        elif close[i] < prev and pc < prev:
            stop[i] = min(prev, close[i] + nloss[i])
        elif close[i] > prev:
            stop[i] = close[i] - nloss[i]
        else:
            stop[i] = close[i] + nloss[i]
    return pd.DataFrame({"stop": stop}, index=df.index)


def ichimoku(df: pd.DataFrame, tenkan: int = 9, kijun: int = 26, senkou: int = 52) -> pd.DataFrame:
    """Ichimoku lines *as visible at bar t* (the cloud is shifted forward, i.e. computed
    ``kijun`` bars earlier), so the frame is safe to use for signals."""
    def mid(n: int) -> pd.Series:
        return (df["high"].rolling(n, min_periods=n).max() + df["low"].rolling(n, min_periods=n).min()) / 2
    t = mid(tenkan)
    k = mid(kijun)
    span_a = ((t + k) / 2).shift(kijun)
    span_b = mid(senkou).shift(kijun)
    return pd.DataFrame({"tenkan": t, "kijun": k, "span_a": span_a, "span_b": span_b})


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def crossed_above(a: pd.Series, b) -> pd.Series:
    b_prev = b.shift(1) if isinstance(b, pd.Series) else b
    return (a > b) & (a.shift(1) <= b_prev)


def crossed_below(a: pd.Series, b) -> pd.Series:
    b_prev = b.shift(1) if isinstance(b, pd.Series) else b
    return (a < b) & (a.shift(1) >= b_prev)


def rescale(s: pd.Series, old_min: float, old_max: float, new_min: float = 0.0, new_max: float = 1.0) -> pd.Series:
    return new_min + (new_max - new_min) * (s - old_min) / max(old_max - old_min, 1e-10)


def expanding_minmax_normalize(s: pd.Series) -> pd.Series:
    """Normalize to [0, 1] with the running (past-only) min/max - the causal version of
    the global min/max scaling that causes look-ahead bias in many public bots."""
    lo = s.cummin()
    hi = s.cummax()
    return (s - lo) / (hi - lo).replace(0.0, np.nan)


def cdl_hammer(df: pd.DataFrame) -> pd.Series:
    """Port of TA-Lib ``CDLHAMMER`` with its default candle settings: small real body
    (< avg body of the previous 10 candles), lower shadow longer than the body,
    upper shadow < 10 % of the avg range of the previous 10 candles, and the body
    near the prior candle's low (within 20 % of the avg range of the 5 candles before it)."""
    o, h, l, c = (df[x] for x in ("open", "high", "low", "close"))
    body = (c - o).abs()
    hl = h - l
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - l
    body_short = body.rolling(10).mean().shift(1)
    very_short = 0.1 * hl.rolling(10).mean().shift(1)
    near = 0.2 * hl.rolling(5).mean().shift(2)
    hit = (body < body_short) & (lower > body) & (upper < very_short) & (np.minimum(o, c) <= l.shift(1) + near)
    return hit.astype(int) * 100
