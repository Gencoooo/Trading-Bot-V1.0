"""Popular TradingView community scripts that are widely used as bot signals
(via webhook alerts to 3Commas, WunderTrading, etc.)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as ta
from .base import Strategy, add
from .classic import enter_exit, long_while


class UTBot(Strategy):
    family = "trend"
    source = "TradingView 'UT Bot Alerts' (QuantNomad), Key=1, ATR=10"
    description = "Kauf wenn der Kurs den ATR-Trailing-Stop von unten kreuzt, Verkauf umgekehrt."

    def generate(self, df, interval):
        stop = ta.atr_trailing_stop(df, self.params.get("key", 1.0), self.params.get("atr", 10))["stop"]
        return long_while(df["close"] > stop)


class SqueezeMomentum(Strategy):
    family = "breakout"
    source = "TradingView 'Squeeze Momentum Indicator' (LazyBear)"
    description = "Kauf wenn der Squeeze (BB in KC) endet und das Momentum positiv ist; Ausstieg bei fallendem Momentum."

    def generate(self, df, interval):
        n = 20
        close = df["close"]
        bb = ta.bollinger(close, n, 2.0, ddof=0)
        rng = ta.sma(ta.true_range(df), n)
        mid = ta.sma(close, n)
        kc_upper, kc_lower = mid + 1.5 * rng, mid - 1.5 * rng
        squeeze_on = (bb["lower"] > kc_lower) & (bb["upper"] < kc_upper)
        hh = df["high"].rolling(n).max()
        ll = df["low"].rolling(n).min()
        mom = ta.linreg(close - ((hh + ll) / 2 + mid) / 2, n)
        released = squeeze_on.shift(1, fill_value=False) & ~squeeze_on
        entry = released & (mom > 0)
        exit_ = (mom < mom.shift(1)) & (mom.shift(1) < mom.shift(2))
        return enter_exit(entry, exit_)


class WaveTrendCross(Strategy):
    family = "mean_reversion"
    source = "TradingView 'WaveTrend Oscillator' (LazyBear), 10/21, OB/OS 53"
    description = "Kauf bei WT-Kreuzung nach oben unter -53, Verkauf bei Kreuzung nach unten über +53."

    def generate(self, df, interval):
        wt = ta.wavetrend(df, 10, 21)
        up = ta.crossed_above(wt["wt1"], wt["wt2"]) & (wt["wt1"] < -53)
        down = ta.crossed_below(wt["wt1"], wt["wt2"]) & (wt["wt1"] > 53)
        return enter_exit(up, down)


class ChandelierExit(Strategy):
    family = "trend"
    source = "TradingView 'Chandelier Exit' (everget), ATR 22 x 3"
    description = "Long wenn der Kurs über dem Short-Chandelier-Stop schließt, bis er unter den Long-Stop fällt."

    def generate(self, df, interval):
        n, mult = 22, 3.0
        a = mult * ta.atr(df, n)
        long_stop = (df["close"].rolling(n).max() - a).to_numpy()
        short_stop = (df["close"].rolling(n).min() + a).to_numpy()
        close = df["close"].to_numpy()
        ls = long_stop.copy()
        ss = short_stop.copy()
        direction = np.zeros(len(df))
        for i in range(1, len(df)):
            if np.isnan(long_stop[i]) or np.isnan(ls[i - 1]):
                direction[i] = direction[i - 1] or 1.0
                continue
            ls[i] = max(long_stop[i], ls[i - 1]) if close[i - 1] > ls[i - 1] else long_stop[i]
            ss[i] = min(short_stop[i], ss[i - 1]) if close[i - 1] < ss[i - 1] else short_stop[i]
            if close[i] > ss[i - 1]:
                direction[i] = 1.0
            elif close[i] < ls[i - 1]:
                direction[i] = -1.0
            else:
                direction[i] = direction[i - 1]
        warm = np.isnan(long_stop)
        direction[warm] = 0.0
        return long_while(pd.Series(direction > 0, index=df.index))


add("ut_bot", UTBot, key=1.0, atr=10)
add("squeeze_momentum", SqueezeMomentum)
add("wavetrend_cross", WaveTrendCross)
add("chandelier_exit", ChandelierExit)
