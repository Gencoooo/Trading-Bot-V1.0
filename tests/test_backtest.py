import numpy as np
import pandas as pd
import pytest

from trading_bot.backtest import Costs, ExitRules, Signals, run_backtest

NO_COSTS = Costs(fee=0.0, slippage=0.0)


def frame(opens, highs=None, lows=None, closes=None):
    opens = np.asarray(opens, float)
    closes = np.asarray(closes if closes is not None else opens, float)
    highs = np.asarray(highs if highs is not None else np.maximum(opens, closes), float)
    lows = np.asarray(lows if lows is not None else np.minimum(opens, closes), float)
    idx = pd.date_range("2024-01-01", periods=len(opens), freq="1D", tz="UTC")
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes, "volume": 1.0}, index=idx)


def test_signal_is_executed_at_next_open():
    df = frame([100, 110, 121, 133.1])
    entries = np.array([True, False, False, False])
    res = run_backtest(df, Signals(entries=entries), "1d", NO_COSTS, initial_capital=1000)
    # bought at the open of bar 1 (110), not at the close of bar 0
    assert res.trades.iloc[0]["entry_price"] == pytest.approx(110)
    assert res.equity.iloc[0] == pytest.approx(1000)
    assert res.equity.iloc[-1] == pytest.approx(1000 * 133.1 / 110)


def test_fees_and_slippage_round_trip():
    df = frame([100, 100, 100, 100])
    entries = np.array([True, False, False, False])
    exits = np.array([False, True, False, False])
    costs = Costs(fee=0.001, slippage=0.0005)
    res = run_backtest(df, Signals(entries=entries, exits=exits), "1d", costs, initial_capital=1000)
    buy_px, sell_px = 100 * 1.0005, 100 * 0.9995
    qty = 1000 / (buy_px * 1.001)
    expected = qty * sell_px * (1 - 0.001)
    assert res.equity.iloc[-1] == pytest.approx(expected)
    assert res.trades.iloc[0]["return"] == pytest.approx(expected / 1000 - 1)


def test_stop_loss_fills_at_stop_or_gap_open():
    # entry at 100 (bar 1 open); bar 2 trades down to 85 -> 10 % stop at 90
    df = frame([100, 100, 98, 95], highs=[100, 101, 99, 96], lows=[100, 99, 85, 94], closes=[100, 99, 88, 95])
    sig = Signals(entries=np.array([True, False, False, False]), rules=ExitRules(stop_loss=0.10))
    res = run_backtest(df, sig, "1d", NO_COSTS, initial_capital=1000)
    t = res.trades.iloc[0]
    assert t["exit_reason"] == "stop_loss"
    assert t["exit_price"] == pytest.approx(90)
    # gap below the stop -> filled at the open
    df2 = frame([100, 100, 80, 80], highs=[100, 101, 81, 81], lows=[100, 99, 79, 79], closes=[100, 99, 80, 80])
    res2 = run_backtest(df2, sig, "1d", NO_COSTS, initial_capital=1000)
    assert res2.trades.iloc[0]["exit_price"] == pytest.approx(80)


def test_roi_table_takes_profit_intrabar():
    df = frame([100, 100, 103, 103], highs=[100, 101, 106, 104], lows=[100, 99, 102, 102], closes=[100, 100, 103, 103])
    sig = Signals(entries=np.array([True, False, False, False]), rules=ExitRules(roi={0: 0.05}))
    res = run_backtest(df, sig, "1d", NO_COSTS, initial_capital=1000)
    t = res.trades.iloc[0]
    assert t["exit_reason"] == "roi"
    assert t["exit_price"] == pytest.approx(105)


def test_stop_has_priority_over_take_profit_in_same_bar():
    df = frame([100, 100, 100], highs=[100, 100, 120], lows=[100, 100, 80], closes=[100, 100, 100])
    sig = Signals(entries=np.array([True, False, False]), rules=ExitRules(stop_loss=0.1, roi={0: 0.1}))
    res = run_backtest(df, sig, "1d", NO_COSTS, initial_capital=1000)
    assert res.trades.iloc[0]["exit_reason"] == "stop_loss"


def test_trailing_stop_uses_previous_highs_only():
    # entry 100, rallies to a 130 high, then drops; 10 % trailing -> stop at 117
    # (bar 3's low of 118 must not trigger: its own high may come after its low)
    df = frame([100, 100, 120, 125, 119],
               highs=[100, 100, 130, 126, 120], lows=[100, 100, 119, 118, 100], closes=[100, 100, 125, 120, 105])
    sig = Signals(entries=np.array([True, False, False, False, False]), rules=ExitRules(trailing_stop=0.10))
    res = run_backtest(df, sig, "1d", NO_COSTS, initial_capital=1000)
    t = res.trades.iloc[0]
    assert t["exit_reason"] == "stop_loss"
    assert t["exit_price"] == pytest.approx(117)


def test_target_mode_rebalances_and_respects_band():
    df = frame([100] * 6)
    target = np.array([1.0, 0.5, 0.52, 0.0, 0.0, 0.0])
    res = run_backtest(df, Signals(target=target, min_rebalance=0.05), "1d", NO_COSTS, initial_capital=1000)
    assert res.exposure.iloc[1] == pytest.approx(1.0)
    assert res.exposure.iloc[2] == pytest.approx(0.5)
    assert res.exposure.iloc[3] == pytest.approx(0.5)   # 0.52 is inside the 5 % band
    assert res.exposure.iloc[4] == pytest.approx(0.0)


def test_short_position_profits_when_price_falls():
    df = frame([100, 100, 90, 80])
    target = np.array([-1.0, -1.0, -1.0, -1.0])
    static = Signals(target=target, min_rebalance=10.0)  # never re-size after entry
    res = run_backtest(df, static, "1d", NO_COSTS, initial_capital=1000, allow_short=True)
    assert res.equity.iloc[-1] == pytest.approx(1000 * (1 + (100 - 80) / 100))
    long_only = run_backtest(df, Signals(target=target), "1d", NO_COSTS, initial_capital=1000)
    assert long_only.equity.iloc[-1] == pytest.approx(1000)


def test_atr_stop_distance_is_frozen_at_entry():
    df = frame([100, 100, 100, 100], highs=[100, 100, 100, 100], lows=[100, 100, 94, 90], closes=[100, 100, 100, 95])
    dist = np.array([0.05, 0.5, 0.5, 0.5])  # only the value of the signal bar counts
    sig = Signals(entries=np.array([True, False, False, False]), stop_distance=dist)
    res = run_backtest(df, sig, "1d", NO_COSTS, initial_capital=1000)
    assert res.trades.iloc[0]["exit_price"] == pytest.approx(95)


def test_stop_in_target_mode_waits_for_rearm():
    df = frame([100, 100, 85, 90, 95, 100], lows=[100, 100, 84, 89, 94, 99])
    target = np.array([1.0, 1.0, 1.0, 0.0, 1.0, 1.0])
    res = run_backtest(df, Signals(target=target, rules=ExitRules(stop_loss=0.1)), "1d", NO_COSTS)
    assert res.exposure.iloc[3] == 0.0       # stopped out, target still 1 -> stays flat
    assert res.exposure.iloc[5] > 0.99       # re-armed after target went to 0
