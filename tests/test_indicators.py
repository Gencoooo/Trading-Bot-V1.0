import numpy as np
import pandas as pd
import pytest

from trading_bot import indicators as ta
from trading_bot.data import synthetic_ohlcv

DF = synthetic_ohlcv(n=1500, interval="4h", seed=3)
O, H, L, C, V = (DF[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))


def test_basic_moving_averages():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert ta.sma(s, 3).iloc[-1] == pytest.approx(4.0)
    assert ta.wma(s, 3).iloc[-1] == pytest.approx((3 * 1 + 4 * 2 + 5 * 3) / 6)
    assert np.isnan(ta.ema(s, 3).iloc[1])


def test_rsi_extremes():
    up = pd.Series(np.arange(1, 50, dtype=float))
    assert ta.rsi(up, 14).iloc[-1] == pytest.approx(100.0)
    down = pd.Series(np.arange(50, 1, -1, dtype=float))
    assert ta.rsi(down, 14).iloc[-1] == pytest.approx(0.0)


def test_supertrend_follows_trend():
    up = synthetic_ohlcv(n=300, drift=0.01, vol=0.01, regimes=False, seed=1)
    assert ta.supertrend(up, 10, 3)["direction"].iloc[-50:].mean() > 0.9


def test_expanding_normalize_is_causal():
    s = pd.Series(np.random.default_rng(0).normal(size=200)).cumsum()
    full = ta.expanding_minmax_normalize(s)
    part = ta.expanding_minmax_normalize(s.iloc[:100])
    np.testing.assert_allclose(full.iloc[:100], part)


talib = pytest.importorskip("talib", reason="TA-Lib not installed - optional cross-check")


@pytest.mark.parametrize("name,mine,ref", [
    ("SMA", lambda: ta.sma(DF.close, 20), lambda: talib.SMA(C, 20)),
    ("EMA", lambda: ta.ema(DF.close, 20), lambda: talib.EMA(C, 20)),
    ("RSI", lambda: ta.rsi(DF.close, 14), lambda: talib.RSI(C, 14)),
    ("MACD", lambda: ta.macd(DF.close)["macd"], lambda: talib.MACD(C)[0]),
    ("ATR", lambda: ta.atr(DF, 14), lambda: talib.ATR(H, L, C, 14)),
    ("ADX", lambda: ta.adx(DF, 14)["adx"], lambda: talib.ADX(H, L, C, 14)),
    ("PLUS_DI", lambda: ta.adx(DF, 25)["plus_di"], lambda: talib.PLUS_DI(H, L, C, 25)),
    ("BBANDS", lambda: ta.bollinger(DF.close, 20, 2.0)["lower"], lambda: talib.BBANDS(C, 20, 2, 2)[2]),
    ("CCI", lambda: ta.cci(DF, 20), lambda: talib.CCI(H, L, C, 20)),
    ("MFI", lambda: ta.mfi(DF, 14), lambda: talib.MFI(H, L, C, V, 14)),
    ("STOCHF", lambda: ta.stoch_fast(DF, 5, 3)["fastd"], lambda: talib.STOCHF(H, L, C, 5, 3, 0)[1]),
    ("STOCH", lambda: ta.stoch(DF, 5, 3, 3)["slowk"], lambda: talib.STOCH(H, L, C, 5, 3, 0, 3, 0)[0]),
    ("SAR", lambda: ta.psar(DF), lambda: talib.SAR(H, L, 0.02, 0.2)),
    ("TEMA", lambda: ta.tema(DF.close, 9), lambda: talib.TEMA(C, 9)),
    ("WILLR", lambda: ta.williams_r(DF, 14), lambda: talib.WILLR(H, L, C, 14)),
    ("OBV", lambda: ta.obv(DF), lambda: talib.OBV(C, V)),
    ("LINEARREG", lambda: ta.linreg(DF.close, 20), lambda: talib.LINEARREG(C, 20)),
    ("CDLHAMMER", lambda: ta.cdl_hammer(DF), lambda: talib.CDLHAMMER(O, H, L, C)),
])
def test_matches_talib(name, mine, ref):
    # skip the warm-up: TA-Lib seeds Wilder smoothing slightly differently
    a = np.asarray(mine(), float)[800:]
    b = np.asarray(ref(), float)[800:]
    np.testing.assert_allclose(a, b, rtol=1e-6, atol=1e-8, err_msg=name)
