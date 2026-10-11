import math

import numpy as np
import pandas as pd
import pytest

from trading_bot.data import _normalize, synthetic_ohlcv
from trading_bot.metrics import (compute_metrics, deflated_sharpe, expected_max_sharpe, max_drawdown,
                                 portfolio_equity, probabilistic_sharpe)


def daily(values, start="2020-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="1D", tz="UTC"), dtype=float)


def test_max_drawdown():
    assert max_drawdown(daily([100, 120, 60, 90, 130])) == pytest.approx(-0.5)


def test_cagr_and_total_return():
    eq = daily(np.linspace(100, 200, 366))  # doubles over 365 days
    m = compute_metrics(eq)
    assert m["total_return"] == pytest.approx(1.0)
    assert m["cagr"] == pytest.approx(1.0, rel=1e-3)


def test_sharpe_sign_and_scale():
    rng = np.random.default_rng(0)
    r = rng.normal(0.001, 0.02, 3000)
    m = compute_metrics(daily(100 * np.cumprod(1 + r)))
    assert m["sharpe"] == pytest.approx(r.mean() / r.std(ddof=1) * math.sqrt(365), rel=0.05)


def test_psr_and_dsr_ordering():
    rng = np.random.default_rng(1)
    good = pd.Series(rng.normal(0.002, 0.02, 1500))
    noise = pd.Series(rng.normal(0.0, 0.02, 1500))
    assert probabilistic_sharpe(good) > 0.95
    assert probabilistic_sharpe(noise) < 0.95
    # deflating by the number of trials can only lower confidence
    assert deflated_sharpe(good, n_trials=50, sharpe_std=0.5) < probabilistic_sharpe(good)
    assert expected_max_sharpe(100, 0.5) > expected_max_sharpe(10, 0.5) > 0


def test_portfolio_equal_weight():
    a = daily([100, 110, 121])
    b = daily([100, 90, 81])
    port = portfolio_equity({"a": a, "b": b})
    assert port.iloc[1] == pytest.approx(1.0)  # (+10 % - 10 %) / 2
    assert port.iloc[-1] == pytest.approx(1.0)


def test_binance_microsecond_timestamps_are_normalized():
    ms = 1735689600000  # 2025-01-01 in milliseconds
    raw = pd.DataFrame({"open_time": [ms, (ms + 86400000) * 1000], "open": [1, 2], "high": [1, 2], "low": [1, 2],
                        "close": [1, 2], "volume": [1, 1], "quote_volume": [1, 1], "trades": [1, 1]})
    out = _normalize(raw)
    assert list(out.index.strftime("%Y-%m-%d")) == ["2025-01-01", "2025-01-02"]


def test_synthetic_data_is_valid_ohlc():
    df = synthetic_ohlcv(500, seed=2)
    assert (df["high"] >= df[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1) + 1e-9).all()
