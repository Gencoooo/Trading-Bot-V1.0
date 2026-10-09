"""Ports of popular community strategies from github.com/freqtrade/freqtrade-strategies
(and Freqtrade's official SampleStrategy template).

Entry/exit conditions, ``minimal_roi`` tables, stop-losses and trailing-stop
settings are copied from the original files (using their hyperopted
``buy_params``/``sell_params`` where present). TA-Lib indicators are replaced by
the equivalents in :mod:`trading_bot.indicators`, so values can differ marginally.
"""

from __future__ import annotations

import pandas as pd

from .. import indicators as ta
from ..backtest import ExitRules, Signals
from .base import Strategy, add

REPO = "freqtrade-strategies"


def _qt_bollinger(s: pd.Series, n: int, k: float = 2.0) -> pd.DataFrame:
    """qtpylib.bollinger_bands (sample std)."""
    return ta.bollinger(s, n, k, ddof=1)


def _signals(entry, exit_, rules: ExitRules) -> Signals:
    entry = pd.Series(entry).fillna(False).to_numpy(dtype=bool)
    exit_ = pd.Series(exit_).fillna(False).to_numpy(dtype=bool)
    return Signals(entries=entry, exits=exit_, rules=rules)


class FreqtradeStrategy(Strategy):
    family = "mean_reversion"
    roi: dict[int, float] = {}
    stoploss: float = 0.10
    trailing_stop: float | None = None
    trailing_offset: float = 0.0
    trail_stop_loss: bool = False

    def rules(self) -> ExitRules:
        return ExitRules(stop_loss=self.stoploss, roi=dict(self.roi), trailing_stop=self.trailing_stop,
                         trailing_offset=self.trailing_offset, trail_stop_loss=self.trail_stop_loss)

    def conditions(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:  # pragma: no cover
        raise NotImplementedError

    def generate(self, df, interval):
        entry, exit_ = self.conditions(df)
        return _signals(entry, exit_, self.rules())


class BinHV45(FreqtradeStrategy):
    source = f"{REPO}/berlinguyinca/BinHV45.py"
    native_timeframe = "1m"
    description = "Dip-Käufer: Schlusskurs fällt stark unter das untere Bollinger-Band (40), TP 1.25 %."
    roi = {0: 0.0125}
    stoploss = 0.05

    def conditions(self, df):
        bb = _qt_bollinger(df["close"], 40)
        bbdelta = (bb["mid"] - bb["lower"]).abs()
        closedelta = (df["close"] - df["close"].shift()).abs()
        tail = (df["close"] - df["low"]).abs()
        entry = (bb["lower"].shift() > 0) & (bbdelta > df["close"] * 0.007) & \
            (closedelta > df["close"] * 0.017) & (tail < bbdelta * 0.025) & \
            (df["close"] < bb["lower"].shift()) & (df["close"] <= df["close"].shift())
        return entry, pd.Series(False, index=df.index)


class ClucMay72018(FreqtradeStrategy):
    source = f"{REPO}/berlinguyinca/ClucMay72018.py"
    native_timeframe = "5m"
    description = "Kauf 1.5 % unter dem unteren BB unterhalb EMA50, Verkauf an der BB-Mitte, TP 1 %."
    roi = {0: 0.01}
    stoploss = 0.05

    def conditions(self, df):
        bb = _qt_bollinger(ta.typical_price(df), 20)
        ema50 = ta.ema(df["close"], 50)  # named 'ema100' in the original, but timeperiod=50
        vol_ok = df["volume"] < df["volume"].rolling(30).mean().shift(1) * 20
        entry = (df["close"] < ema50) & (df["close"] < 0.985 * bb["lower"]) & vol_ok
        return entry, df["close"] > bb["mid"]


class CombinedBinHAndCluc(FreqtradeStrategy):
    source = f"{REPO}/berlinguyinca/CombinedBinHAndCluc.py"
    native_timeframe = "5m"
    description = "Kombination aus BinHV45 und ClucMay72018, TP 5 %, SL 5 %."
    roi = {0: 0.05}
    stoploss = 0.05

    def conditions(self, df):
        bb40 = _qt_bollinger(df["close"], 40)
        lower = bb40["lower"].fillna(0.0)
        bbdelta = (bb40["mid"].fillna(0.0) - lower).abs()
        closedelta = (df["close"] - df["close"].shift()).abs()
        tail = (df["close"] - df["low"]).abs()
        bb20 = _qt_bollinger(ta.typical_price(df), 20)
        ema_slow = ta.ema(df["close"], 50)
        vol_mean = df["volume"].rolling(30).mean()
        binh = (lower.shift() > 0) & (bbdelta > df["close"] * 0.008) & (closedelta > df["close"] * 0.0175) & \
            (tail < bbdelta * 0.25) & (df["close"] < lower.shift()) & (df["close"] <= df["close"].shift())
        cluc = (df["close"] < ema_slow) & (df["close"] < 0.985 * bb20["lower"]) & \
            (df["volume"] < vol_mean.shift(1) * 20)
        return binh | cluc, df["close"] > bb20["mid"]


_ROI_00X = {60: 0.01, 30: 0.03, 20: 0.04, 0: 0.05}


class Strategy001(FreqtradeStrategy):
    family = "trend"
    source = f"{REPO}/Strategy001.py"
    native_timeframe = "5m"
    description = "EMA20/50-Kreuzung mit grüner Heikin-Ashi-Kerze."
    roi = _ROI_00X
    stoploss = 0.10

    def conditions(self, df):
        e20, e50, e100 = (ta.ema(df["close"], n) for n in (20, 50, 100))
        ha = ta.heikin_ashi(df)
        entry = ta.crossed_above(e20, e50) & (ha["close"] > e20) & (ha["open"] < ha["close"])
        exit_ = ta.crossed_above(e50, e100) & (ha["close"] < e20) & (ha["open"] > ha["close"])
        return entry, exit_


class Strategy002(FreqtradeStrategy):
    source = f"{REPO}/Strategy002.py"
    native_timeframe = "5m"
    description = "RSI<30, Stoch<20, unter BB und Hammer-Kerze."
    roi = _ROI_00X
    stoploss = 0.10

    def conditions(self, df):
        slowk = ta.stoch(df, 5, 3, 3)["slowk"]
        r = ta.rsi(df["close"], 14)
        bb = _qt_bollinger(ta.typical_price(df), 20)
        entry = (r < 30) & (slowk < 20) & (bb["lower"] > df["close"]) & (ta.cdl_hammer(df) == 100)
        exit_ = (ta.psar(df) > df["close"]) & (ta.fisher_rsi(r) > 0.3)
        return entry, exit_


class Strategy003(FreqtradeStrategy):
    source = f"{REPO}/Strategy003.py"
    native_timeframe = "5m"
    description = "Tief überverkauft (RSI<28, MFI<16, Fisher-RSI<-0.94) im Aufwärtstrend."
    roi = _ROI_00X
    stoploss = 0.10

    def conditions(self, df):
        close = df["close"]
        r = ta.rsi(close, 14)
        fr = ta.fisher_rsi(r)
        st = ta.stoch_fast(df, 5, 3)
        e5, e10, e50, e100 = (ta.ema(close, n) for n in (5, 10, 50, 100))
        entry = (r < 28) & (r > 0) & (close < ta.sma(close, 40)) & (fr < -0.94) & (ta.mfi(df, 14) < 16) & \
            ((e50 > e100) | ta.crossed_above(e5, e10)) & (st["fastd"] > st["fastk"]) & (st["fastd"] > 0)
        exit_ = (ta.psar(df) > close) & (fr > 0.3)
        return entry, exit_


class Strategy004(FreqtradeStrategy):
    source = f"{REPO}/Strategy004.py"
    native_timeframe = "5m"
    description = "Starker Trend (ADX) + CCI<-100 + Stochastik-Kreuzung aus dem Keller."
    roi = _ROI_00X
    stoploss = 0.10

    def conditions(self, df):
        adx14 = ta.adx(df, 14)["adx"]
        adx35 = ta.adx(df, 35)["adx"]
        c = ta.cci(df, 14)
        f5 = ta.stoch_fast(df, 5, 3)
        f50 = ta.stoch_fast(df, 50, 3)
        fk, fd = f5["fastk"], f5["fastd"]
        fkp, fdp = fk.shift(1), fd.shift(1)
        sfkp, sfdp = f50["fastk"].shift(1), f50["fastd"].shift(1)
        mean_vol = df["volume"].rolling(12).mean()
        entry = ((adx14 > 50) | (adx35 > 26)) & (c < -100) & (fkp < 20) & (fdp < 20) & \
            (sfkp < 30) & (sfdp < 30) & (fkp < fdp) & (fk > fd) & (mean_vol > 0.75)
        exit_ = (adx35 < 25) & ((fk > 70) | (fd > 70)) & (fkp < fdp) & (df["close"] > ta.ema(df["close"], 5))
        return entry, exit_


class Strategy005(FreqtradeStrategy):
    source = f"{REPO}/Strategy005.py"
    native_timeframe = "5m"
    description = "Volumen-Spike (4x) unter SMA40 mit RSI 26-35; Ausstieg RSI>74 bei MACD<0."
    roi = {1440: 0.01, 80: 0.02, 40: 0.03, 20: 0.04, 0: 0.05}
    stoploss = 0.10

    def conditions(self, df):
        close = df["close"]
        r = ta.rsi(close, 14)
        fr_norma = 50 * (ta.fisher_rsi(r) + 1)
        st = ta.stoch_fast(df, 5, 3)
        m = ta.macd(close)
        minus_di = ta.adx(df, 14)["minus_di"]
        entry = (df["volume"] > df["volume"].rolling(150).mean() * 4) & (close < ta.sma(close, 40)) & \
            (st["fastd"] > st["fastk"]) & (r > 26) & (st["fastd"] > 1) & (fr_norma < 5)
        exit_ = ta.crossed_above(r, 74) & (m["macd"] < 0) & (minus_di > 4)
        return entry, exit_


class BbandRsi(FreqtradeStrategy):
    source = f"{REPO}/berlinguyinca/BbandRsi.py"
    native_timeframe = "1h"
    description = "RSI<30 unter dem unteren BB kaufen, bei RSI>70 verkaufen."
    roi = {0: 0.1}
    stoploss = 0.25

    def conditions(self, df):
        r = ta.rsi(df["close"], 14)
        bb = _qt_bollinger(ta.typical_price(df), 20)
        return (r < 30) & (df["close"] < bb["lower"]), r > 70


class ADXMomentum(FreqtradeStrategy):
    family = "trend"
    source = f"{REPO}/berlinguyinca/ADXMomentum.py"
    native_timeframe = "1h"
    description = "ADX>25, Momentum>0, +DI>25 und +DI>-DI; TP 1 %."
    roi = {0: 0.01}
    stoploss = 0.25

    def conditions(self, df):
        adx = ta.adx(df, 14)["adx"]
        di = ta.adx(df, 25)
        mom = ta.momentum(df["close"], 14)
        entry = (adx > 25) & (mom > 0) & (di["plus_di"] > 25) & (di["plus_di"] > di["minus_di"])
        exit_ = (adx > 25) & (mom < 0) & (di["minus_di"] > 25) & (di["plus_di"] < di["minus_di"])
        return entry, exit_


class AdxSmas(FreqtradeStrategy):
    family = "trend"
    source = f"{REPO}/berlinguyinca/AdxSmas.py"
    native_timeframe = "1h"
    description = "SMA3/SMA6-Kreuzung bei ADX>25; TP 10 %."
    roi = {0: 0.1}
    stoploss = 0.25

    def conditions(self, df):
        adx = ta.adx(df, 14)["adx"]
        s3, s6 = ta.sma(df["close"], 3), ta.sma(df["close"], 6)
        return (adx > 25) & ta.crossed_above(s3, s6), (adx < 25) & ta.crossed_above(s6, s3)


class HLHB(FreqtradeStrategy):
    family = "trend"
    source = f"{REPO}/hlhb.py"
    native_timeframe = "4h"
    description = "RSI(10)-Kreuzung über 50 plus EMA5/10-Kreuzung bei ADX>25, mit Trailing-Stop."
    roi = {0: 0.6225, 703: 0.2187, 2849: 0.0363, 5520: 0.0}
    stoploss = 0.3211
    trailing_stop = 0.0117
    trailing_offset = 0.0186

    def conditions(self, df):
        hl2 = (df["close"] + df["open"]) / 2  # the original's "hl2" really is (close+open)/2
        r = ta.rsi(hl2, 10)
        e5, e10 = ta.ema(df["close"], 5), ta.ema(df["close"], 10)
        adx = ta.adx(df, 14)["adx"]
        entry = ta.crossed_above(r, 50) & ta.crossed_above(e5, e10) & (adx > 25)
        exit_ = ta.crossed_below(r, 50) & ta.crossed_below(e5, e10) & (adx > 25)
        return entry, exit_


class TripleSupertrend(FreqtradeStrategy):
    family = "trend"
    source = f"{REPO}/Supertrend.py"
    native_timeframe = "1h"
    description = "Drei Supertrends (hyperoptimiert) müssen 'up' sein; Ausstieg wenn drei andere 'down'."
    roi = {0: 0.087, 372: 0.058, 861: 0.029, 2221: 0.0}
    stoploss = 0.265
    trailing_stop = 0.05
    trailing_offset = 0.144
    trail_stop_loss = True  # trailing_only_offset_is_reached = False

    def conditions(self, df):
        def up(m, p):
            return ta.supertrend(df, p, m)["direction"] > 0
        entry = up(4, 8) & up(7, 9) & up(1, 8)
        exit_ = (~up(1, 16)) & (~up(3, 18)) & (~up(6, 18))
        return entry, exit_


class MultiMa(FreqtradeStrategy):
    family = "trend"
    source = f"{REPO}/MultiMa.py"
    native_timeframe = "4h"
    description = "TEMA-Leiter: Kauf wenn TEMA30<TEMA15 und TEMA45<TEMA30, Verkauf bei Bruch der langen Leiter."
    roi = {0: 0.523, 1553: 0.123, 2332: 0.076, 3169: 0.0}
    stoploss = 0.345

    def conditions(self, df):
        close = df["close"]
        cache: dict[int, pd.Series] = {}

        def tema(n):
            if n not in cache:
                cache[n] = ta.tema(close, n)
            return cache[n]

        entry = (tema(30) < tema(15)) & (tema(45) < tema(30))
        exit_ = pd.Series(False, index=df.index)
        for k in range(2, 12):
            exit_ |= tema(k * 68) > tema((k - 1) * 68)
        return entry, exit_


class UniversalMACD(FreqtradeStrategy):
    family = "mean_reversion"
    source = f"{REPO}/UniversalMACD.py"
    native_timeframe = "5m"
    description = "Kauf wenn EMA12/EMA26-1 in einem engen negativen Band liegt; Ausstieg nur über ROI/SL."
    roi = {0: 0.213, 27: 0.099, 60: 0.03, 164: 0.0}
    stoploss = 0.318

    def conditions(self, df):
        umacd = ta.ema(df["close"], 12) / ta.ema(df["close"], 26) - 1
        entry = umacd.between(-0.01416, -0.01176)
        exit_ = umacd.between(-0.00707, -0.02323)  # empty range in the original -> never fires
        return entry, exit_


class TrendFollowingFT(FreqtradeStrategy):
    family = "trend"
    source = f"{REPO}/futures/TrendFollowingStrategy.py (Long-Seite)"
    native_timeframe = "5m"
    description = "Close kreuzt EMA20 bei steigendem OBV; Trailing-Stop."
    roi = {0: 0.15, 30: 0.1, 60: 0.05}
    stoploss = 0.265
    trailing_stop = 0.05
    trailing_offset = 0.1
    trail_stop_loss = True

    def conditions(self, df):
        trend = df["close"].ewm(span=20, adjust=False).mean()
        o = ta.obv(df)
        entry = (df["close"] > trend) & (df["close"].shift(1) <= trend.shift(1)) & (o > o.shift(1))
        exit_ = (df["close"] < trend) & (df["close"].shift(1) >= trend.shift(1)) & (o > o.shift(1))
        return entry, exit_


class SampleStrategy(FreqtradeStrategy):
    source = "freqtrade/templates/sample_strategy.py (offizielles Template)"
    native_timeframe = "5m"
    description = "RSI kreuzt 30 aufwärts, TEMA unter BB-Mitte und steigend; Ausstieg RSI>70."
    roi = {60: 0.01, 30: 0.02, 0: 0.04}
    stoploss = 0.10

    def conditions(self, df):
        r = ta.rsi(df["close"], 14)
        t = ta.tema(df["close"], 9)
        bb = _qt_bollinger(ta.typical_price(df), 20)
        vol = df["volume"] > 0
        entry = ta.crossed_above(r, 30) & (t <= bb["mid"]) & (t > t.shift(1)) & vol
        exit_ = ta.crossed_above(r, 70) & (t > bb["mid"]) & (t < t.shift(1)) & vol
        return entry, exit_


for _name, _cls in [
    ("ft_binhv45", BinHV45), ("ft_clucmay72018", ClucMay72018), ("ft_combined_binh_cluc", CombinedBinHAndCluc),
    ("ft_strategy001", Strategy001), ("ft_strategy002", Strategy002), ("ft_strategy003", Strategy003),
    ("ft_strategy004", Strategy004), ("ft_strategy005", Strategy005), ("ft_bband_rsi", BbandRsi),
    ("ft_adx_momentum", ADXMomentum), ("ft_adx_smas", AdxSmas), ("ft_hlhb", HLHB),
    ("ft_supertrend", TripleSupertrend), ("ft_multi_ma", MultiMa), ("ft_universal_macd", UniversalMACD),
    ("ft_trend_following", TrendFollowingFT), ("ft_sample_strategy", SampleStrategy),
]:
    add(_name, _cls)
