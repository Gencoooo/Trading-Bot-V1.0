"""Classic technical-analysis bots as found in Gekko, Zenbot, Jesse, backtrader /
backtesting.py examples and academic papers. Parameters are the published defaults."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as ta
from ..backtest import ExitRules, Signals
from .base import Strategy, add


def long_while(cond: pd.Series) -> Signals:
    """Hold a long position exactly while ``cond`` is true."""
    return Signals(target=cond.fillna(False).astype(float).to_numpy())


def enter_exit(entry: pd.Series, exit_: pd.Series, rules: ExitRules | None = None) -> Signals:
    return Signals(entries=entry.fillna(False).to_numpy(), exits=exit_.fillna(False).to_numpy(),
                   rules=rules or ExitRules())


class BuyAndHold(Strategy):
    family = "benchmark"
    source = "Benchmark"
    description = "Kaufen am ersten Tag und halten - die Messlatte für jeden Bot."

    def generate(self, df, interval):
        target = np.ones(len(df))
        return Signals(target=target)


class MACross(Strategy):
    family = "trend"

    def generate(self, df, interval):
        fast, slow, kind = self.params["fast"], self.params["slow"], self.params.get("kind", "sma")
        ma = ta.sma if kind == "sma" else ta.ema
        f, s = ma(df["close"], fast), ma(df["close"], slow)
        return long_while(f > s)


class PriceAboveMA(Strategy):
    family = "trend"

    def generate(self, df, interval):
        return long_while(df["close"] > ta.sma(df["close"], self.params["n"]))


class MACDCross(Strategy):
    family = "trend"

    def generate(self, df, interval):
        m = ta.macd(df["close"], self.params.get("fast", 12), self.params.get("slow", 26), self.params.get("signal", 9))
        return long_while(m["hist"] > 0)


class RSIReversion(Strategy):
    family = "mean_reversion"

    def generate(self, df, interval):
        r = ta.rsi(df["close"], self.params.get("n", 14))
        return enter_exit(r < self.params.get("low", 30), r > self.params.get("high", 70))


class BollingerReversion(Strategy):
    family = "mean_reversion"

    def generate(self, df, interval):
        bb = ta.bollinger(df["close"], self.params.get("n", 20), self.params.get("k", 2.0))
        exit_band = bb["upper"] if self.params.get("exit", "upper") == "upper" else bb["mid"]
        return enter_exit(df["close"] < bb["lower"], df["close"] > exit_band)


class BollingerBreakout(Strategy):
    family = "breakout"

    def generate(self, df, interval):
        bb = ta.bollinger(df["close"], self.params.get("n", 20), self.params.get("k", 2.0))
        return enter_exit(df["close"] > bb["upper"], df["close"] < bb["mid"])


class Donchian(Strategy):
    family = "breakout"

    def generate(self, df, interval):
        entry_n, exit_n = self.params["entry"], self.params["exit"]
        upper = df["high"].rolling(entry_n, min_periods=entry_n).max().shift(1)
        lower = df["low"].rolling(exit_n, min_periods=exit_n).min().shift(1)
        sig = enter_exit(df["close"] > upper, df["close"] < lower)
        if self.params.get("atr_stop"):
            # Turtle "2N" stop: 2 x ATR(20) below the entry, frozen at entry time.
            sig.stop_distance = (2.0 * ta.atr(df, 20) / df["close"]).to_numpy()
        return sig


class SupertrendTV(Strategy):
    family = "trend"

    def generate(self, df, interval):
        st = ta.supertrend(df, self.params.get("period", 10), self.params.get("mult", 3.0))
        return long_while(st["direction"] > 0)


class Ichimoku(Strategy):
    family = "trend"

    def generate(self, df, interval):
        ich = ta.ichimoku(df)
        cloud_top = np.maximum(ich["span_a"], ich["span_b"])
        cloud_bot = np.minimum(ich["span_a"], ich["span_b"])
        entry = (df["close"] > cloud_top) & (ich["tenkan"] > ich["kijun"])
        exit_ = (df["close"] < cloud_bot) | (ich["tenkan"] < ich["kijun"])
        return enter_exit(entry, exit_)


class ParabolicSAR(Strategy):
    family = "trend"

    def generate(self, df, interval):
        return long_while(df["close"] > ta.psar(df))


class StochRSIGekko(Strategy):
    family = "mean_reversion"

    def generate(self, df, interval):
        """Gekko StochRSI: RSI(3) stochastic, long after `persistence` bars below 20,
        flat after `persistence` bars above 80."""
        n, pers = self.params.get("n", 3), self.params.get("persistence", 3)
        r = ta.rsi(df["close"], n)
        lo, hi = r.rolling(n).min(), r.rolling(n).max()
        srsi = 100 * (r - lo) / (hi - lo).replace(0.0, np.nan)
        low_run = (srsi < 20).astype(int).rolling(pers).sum() == pers
        high_run = (srsi > 80).astype(int).rolling(pers).sum() == pers
        return enter_exit(low_run, high_run)


class CCIGekko(Strategy):
    family = "mean_reversion"

    def generate(self, df, interval):
        c = ta.cci(df, self.params.get("n", 20))
        return enter_exit(c <= -100, c >= 100)


class ConnorsRSI2(Strategy):
    family = "mean_reversion"

    def generate(self, df, interval):
        close = df["close"]
        r2 = ta.rsi(close, 2)
        entry = (close > ta.sma(close, 200)) & (r2 < 10)
        exit_ = close > ta.sma(close, 5)
        return enter_exit(entry, exit_)


class TSMOM(Strategy):
    family = "trend"

    def generate(self, df, interval):
        return long_while(ta.roc(df["close"], self.params["lookback"]) > 0)


class KeltnerBreakout(Strategy):
    family = "breakout"

    def generate(self, df, interval):
        kc = ta.keltner(df, 20, 2.0, 10)
        return enter_exit(df["close"] > kc["upper"], df["close"] < kc["mid"])


class HeikinAshiTrend(Strategy):
    family = "trend"

    def generate(self, df, interval):
        ha = ta.heikin_ashi(df)
        e = ta.ema(df["close"], 50)
        green = ha["close"] > ha["open"]
        entry = green & green.shift(1, fill_value=False) & (ha["close"] > e)
        exit_ = (~green) & (~green.shift(1, fill_value=True))
        return enter_exit(entry, exit_)


class ADXTrend(Strategy):
    family = "trend"

    def generate(self, df, interval):
        a = ta.adx(df, 14)
        entry = (a["adx"] > 25) & (a["plus_di"] > a["minus_di"])
        exit_ = a["plus_di"] < a["minus_di"]
        return enter_exit(entry, exit_)


class WilliamsR(Strategy):
    family = "mean_reversion"

    def generate(self, df, interval):
        w = ta.williams_r(df, 14)
        return enter_exit(ta.crossed_above(w, -80), w > -20)


class HullTrend(Strategy):
    family = "trend"

    def generate(self, df, interval):
        h = ta.hma(df["close"], self.params.get("n", 55))
        return long_while(h > h.shift(2))


add("buy_hold", BuyAndHold)
add("golden_cross_50_200", MACross, fast=50, slow=200, kind="sma",
    source="backtrader/backtesting.py Beispiele, Detzel et al. (2018) MA-Regeln",
    description="Long solange SMA50 > SMA200 ('Golden Cross').")
add("sma_cross_10_20", MACross, fast=10, slow=20, kind="sma",
    source="backtesting.py Quickstart 'SmaCross' (n1=10, n2=20)",
    description="Long solange SMA10 > SMA20.")
add("ema_cross_12_26", MACross, fast=12, slow=26, kind="ema",
    source="Zenbot trend_ema / klassischer EMA-Crossover",
    description="Long solange EMA12 > EMA26.")
add("sma200_filter", PriceAboveMA, n=200,
    source="Meb Faber 'A Quantitative Approach to Tactical Asset Allocation' (200-Tage-Linie)",
    description="Long solange Close > SMA200.")
add("macd_gekko", MACDCross,
    source="Gekko MACD-Strategie (12/26/9, Histogramm-Vorzeichen)",
    description="Long solange MACD-Histogramm > 0.")
add("rsi_gekko", RSIReversion, n=14, low=30, high=70,
    source="Gekko RSI-Strategie (14, 30/70)",
    description="Kauf bei RSI<30, Verkauf bei RSI>70.")
add("bollinger_reversion", BollingerReversion, n=20, k=2.0, exit="upper",
    source="Zenbot bollinger-Strategie",
    description="Kauf unter dem unteren Band, Verkauf über dem oberen Band.")
add("bollinger_breakout", BollingerBreakout, n=20, k=2.0,
    source="Bollinger-Ausbruch (Momentum-Variante)",
    description="Kauf über dem oberen Band, Verkauf unter der Mittellinie.")
add("turtle_20_10", Donchian, entry=20, exit=10, atr_stop=True,
    source="Turtle Trading System 1 / Jesse 'Donchian' Beispiel",
    description="20-Bar-Hoch-Ausbruch, Ausstieg am 10-Bar-Tief, 2N-Stop.")
add("turtle_55_20", Donchian, entry=55, exit=20, atr_stop=True,
    source="Turtle Trading System 2",
    description="55-Bar-Hoch-Ausbruch, Ausstieg am 20-Bar-Tief, 2N-Stop.")
add("supertrend_10_3", SupertrendTV, period=10, mult=3.0,
    source="TradingView Supertrend (ATR 10, Faktor 3)",
    description="Long solange der Supertrend nach oben zeigt.")
add("ichimoku", Ichimoku,
    source="Ichimoku Kinko Hyo (9/26/52)",
    description="Long über der Wolke mit Tenkan > Kijun.")
add("parabolic_sar", ParabolicSAR,
    source="Wilder Parabolic SAR (0.02/0.2), Zenbot sar",
    description="Long solange Close > SAR.")
add("stochrsi_gekko", StochRSIGekko, n=3, persistence=3,
    source="Gekko StochRSI (interval 3, 20/80, persistence 3)",
    description="Kauf nach 3 Bars StochRSI<20, Verkauf nach 3 Bars >80.")
add("cci_gekko", CCIGekko, n=20,
    source="Gekko CCI (±100)",
    description="Kauf bei CCI<=-100, Verkauf bei CCI>=100.")
add("connors_rsi2", ConnorsRSI2,
    source="Larry Connors RSI(2) (Short Term Trading Strategies That Work)",
    description="Über SMA200: Kauf bei RSI(2)<10, Verkauf über SMA5.")
add("tsmom_30", TSMOM, lookback=30,
    source="Time-Series Momentum (Moskowitz/Ooi/Pedersen 2012; Liu/Tsyvinski Krypto-Momentum)",
    description="Long wenn die Rendite der letzten 30 Bars > 0.")
add("tsmom_90", TSMOM, lookback=90,
    source="Time-Series Momentum (Moskowitz/Ooi/Pedersen 2012)",
    description="Long wenn die Rendite der letzten 90 Bars > 0.")
add("keltner_breakout", KeltnerBreakout,
    source="Keltner-Kanal-Ausbruch (EMA20 ± 2 ATR)",
    description="Kauf über dem oberen Keltner-Band, Verkauf unter der Mitte.")
add("heikin_ashi_trend", HeikinAshiTrend,
    source="Heikin-Ashi-Trendbots (YouTube/TradingView)",
    description="Zwei grüne HA-Kerzen über EMA50 -> Kauf; zwei rote -> Verkauf.")
add("adx_trend", ADXTrend,
    source="Wilder ADX/DMI",
    description="Kauf bei ADX>25 und +DI>-DI, Verkauf bei +DI<-DI.")
add("williams_r", WilliamsR,
    source="Williams %R (14)",
    description="Kauf beim Kreuzen über -80, Verkauf über -20.")
add("hull_trend", HullTrend, n=55,
    source="TradingView 'Hull Suite' (HMA 55)",
    description="Long solange die Hull-MA steigt.")
