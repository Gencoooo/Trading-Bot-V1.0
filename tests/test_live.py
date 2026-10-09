"""Paper/live runner: decisions must match the backtest engine exactly."""

import numpy as np
import pandas as pd
import pytest

from trading_bot import live
from trading_bot.backtest import Costs, run_backtest
from trading_bot.data import synthetic_ohlcv
from trading_bot.strategies import get_strategy

DF = synthetic_ohlcv(n=900, interval="1d", seed=11)


@pytest.mark.parametrize("name", ["golden_cross_50_200", "turtle_20_10", "ft_bband_rsi", "dca_bot"])
def test_target_exposure_matches_backtest(name):
    strat = get_strategy(name)
    for k in (600, 700, 850):
        price = float(DF["open"].iloc[k])
        live_expo = live.target_exposure(strat, DF.iloc[:k], "1d", price, Costs())
        # reference: full backtest where bar k is flat at its open price
        ref_df = DF.iloc[:k + 1].copy()
        ref_df.iloc[-1, ref_df.columns.get_indexer(["open", "high", "low", "close"])] = price
        if hasattr(strat, "simulate"):
            ref = strat.simulate(ref_df, "1d", Costs())
        else:
            sig = strat.generate(DF.iloc[:k], "1d")
            ext = lambda x, fill: None if x is None else np.append(np.asarray(x, float), fill)  # noqa: E731
            sig.entries = None if sig.entries is None else ext(sig.entries, 0).astype(bool)
            sig.exits = None if sig.exits is None else ext(sig.exits, 0).astype(bool)
            sig.target = None if sig.target is None else ext(sig.target, np.nan)
            sig.stop_distance = None if sig.stop_distance is None else ext(sig.stop_distance, np.nan)
            ref = run_backtest(ref_df, sig, "1d", Costs())
        assert live_expo == pytest.approx(float(ref.exposure.iloc[-1]), abs=1e-9)


def test_paper_broker_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "STATE_DIR", tmp_path)
    monkeypatch.setattr(live, "latest_price", lambda symbol: 100.0)
    broker = live.PaperBroker(name="t", starting_cash=1000.0, costs=Costs(fee=0.001, slippage=0.0))
    broker.market_order("BTCUSDT", "buy", 5.0)
    bal = broker.balances()
    assert bal["BTC"] == pytest.approx(5.0)
    assert bal["USDT"] == pytest.approx(1000 - 500 * 1.001)
    broker.market_order("BTCUSDT", "sell", 5.0)
    assert broker.balances()["USDT"] == pytest.approx(1000 - 500 * 1.001 + 500 * 0.999)
    # state survives a restart
    again = live.PaperBroker(name="t")
    assert len(again.state["trades"]) == 2


def test_runner_step_rebalances_paper_account(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "STATE_DIR", tmp_path)
    prices = {"AAAUSDT": float(DF["close"].iloc[-1])}
    monkeypatch.setattr(live, "latest_price", lambda s: prices[s])
    monkeypatch.setattr(live, "fetch_klines", lambda *a, **k: DF)
    broker = live.PaperBroker(name="r", starting_cash=1000.0)
    runner = live.BotRunner(get_strategy("buy_hold"), ["AAAUSDT"], "1d", broker)
    report = runner.step()
    assert report["AAAUSDT"]["target"] == pytest.approx(1.0)
    assert broker.balances().get("AAA", 0) > 0
    assert isinstance(report["_equity"], float)
    assert pd.notna(report["_equity"])


def test_portfolio_runner_rebalances_to_target(tmp_path, monkeypatch):
    from trading_bot.portfolio_strategies import EqualWeightHold
    monkeypatch.setattr(live, "STATE_DIR", tmp_path)
    start = (pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=899)).strftime("%Y-%m-%d")
    data = {"AAAUSDT": synthetic_ohlcv(n=900, interval="1d", seed=11, start=start),
            "BBBUSDT": synthetic_ohlcv(n=900, interval="1d", seed=12, start=start)}
    monkeypatch.setattr(live, "fetch_klines", lambda s, *a, **k: data[s])
    monkeypatch.setattr(live, "latest_price", lambda s: float(data[s]["close"].iloc[-1]))
    broker = live.PaperBroker(name="p", starting_cash=1000.0, costs=Costs(fee=0.0, slippage=0.0))
    runner = live.PortfolioBotRunner(EqualWeightHold(), list(data), "1d", broker)
    report = runner.step()
    assert report["_rebalanced"]
    bal = broker.balances()
    for sym, base in (("AAAUSDT", "AAA"), ("BBBUSDT", "BBB")):
        value = bal[base] * float(data[sym]["close"].iloc[-1])
        assert value == pytest.approx(500.0, rel=1e-6)


def test_portfolio_runner_catches_up_missed_rebalance(tmp_path, monkeypatch):
    """A decision that was not executed (bot offline) is executed on the next run, once."""
    from trading_bot.portfolio_strategies import EqualWeightHold
    monkeypatch.setattr(live, "STATE_DIR", tmp_path)
    start = (pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=899)).strftime("%Y-%m-%d")
    data = {"AAAUSDC": synthetic_ohlcv(n=900, interval="1d", seed=11, start=start),
            "BBBUSDC": synthetic_ohlcv(n=900, interval="1d", seed=12, start=start)}
    monkeypatch.setattr(live, "fetch_klines", lambda s, *a, **k: data[s])
    monkeypatch.setattr(live, "latest_price", lambda s: float(data[s]["close"].iloc[-1]))
    broker = live.PaperBroker(name="c", starting_cash=1000.0, costs=Costs(fee=0.0, slippage=0.0), quote="USDC")
    weekly = EqualWeightHold(rebalance_days=7)
    state = tmp_path / "c.runner.json"
    # pretend the last executed decision is three weeks old -> the latest one must be caught up
    state.write_text('{"last_decision": "%s"}' % (data["AAAUSDC"].index[-22]).isoformat())
    runner = live.PortfolioBotRunner(weekly, list(data), "1d", broker, state_path=state)
    assert runner.step()["_rebalanced"]
    assert broker.balances()["AAA"] > 0 and broker.state["quote"] == "USDC"
    assert not runner.step()["_rebalanced"]  # same decision is not executed twice


def test_runner_skips_symbols_the_exchange_does_not_offer(tmp_path, monkeypatch):
    from trading_bot.portfolio_strategies import EqualWeightHold
    monkeypatch.setattr(live, "STATE_DIR", tmp_path)
    start = (pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=899)).strftime("%Y-%m-%d")
    data = {"AAAUSDT": synthetic_ohlcv(n=900, interval="1d", seed=11, start=start),
            "BBBUSDT": synthetic_ohlcv(n=900, interval="1d", seed=12, start=start)}
    monkeypatch.setattr(live, "fetch_klines", lambda s, *a, **k: data[s])

    def price(symbol):
        if symbol == "BBBUSDT":
            raise RuntimeError("market not available on testnet")
        return float(data[symbol]["close"].iloc[-1])

    monkeypatch.setattr(live, "latest_price", price)
    broker = live.PaperBroker(name="s", starting_cash=1000.0, costs=Costs(fee=0.0, slippage=0.0))
    report = live.PortfolioBotRunner(EqualWeightHold(), list(data), "1d", broker).step()
    assert report["_rebalanced"] and "BBBUSDT" not in report
    assert broker.balances()["AAA"] > 0
