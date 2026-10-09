import numpy as np
import pandas as pd
import pytest

from trading_bot.backtest import Costs, Signals, run_backtest
from trading_bot.data import synthetic_ohlcv
from trading_bot.portfolio import run_portfolio_backtest

A = synthetic_ohlcv(400, seed=1)
B = synthetic_ohlcv(400, seed=2)


def test_single_asset_matches_per_coin_engine():
    w = pd.DataFrame({"A": 1.0}, index=A.index)
    port = run_portfolio_backtest({"A": A}, w, "1d", Costs(), band=0.0)
    single = run_backtest(A, Signals(target=np.ones(len(A)), min_rebalance=10.0), "1d", Costs())
    np.testing.assert_allclose(port.equity.to_numpy(), single.equity.to_numpy(), rtol=1e-9)


def test_equal_weight_rebalancing_and_costs():
    w = pd.DataFrame({"A": 0.5, "B": 0.5}, index=A.index)
    free = run_portfolio_backtest({"A": A, "B": B}, w, "1d", Costs(0, 0), band=0.0)
    costly = run_portfolio_backtest({"A": A, "B": B}, w, "1d", Costs(), band=0.0)
    assert costly.equity.iloc[-1] < free.equity.iloc[-1]
    assert free.weights.iloc[-1].sum() == pytest.approx(1.0)
    # weights are reset to 50/50 at every open, so the close weights stay close to it
    assert abs(free.weights.iloc[200]["A"] - 0.5) < 0.1


def test_delisted_coin_is_sold_at_its_last_close():
    short_b = B.iloc[:250]
    w = pd.DataFrame({"A": 0.5, "B": 0.5}, index=A.index)
    res = run_portfolio_backtest({"A": A, "B": short_b}, w, "1d", Costs(0, 0), band=0.0)
    assert res.weights["B"].iloc[260:].abs().max() == 0.0
    assert res.weights["A"].iloc[-1] > 0.45


def test_portfolio_engine_is_causal():
    rng = np.random.default_rng(0)
    w = pd.DataFrame(rng.random((400, 2)), index=A.index, columns=["A", "B"])
    full = run_portfolio_backtest({"A": A, "B": B}, w, "1d", Costs())
    part = run_portfolio_backtest({"A": A.iloc[:300], "B": B.iloc[:300]}, w.iloc[:300], "1d", Costs())
    np.testing.assert_allclose(part.equity.to_numpy(), full.equity.to_numpy()[:300], rtol=1e-9)


def _panel(n=None):
    syms = {"BTCUSDT": 1, "ETHUSDT": 2, "SOLUSDT": 3, "XRPUSDT": 4, "ADAUSDT": 5}
    p = {s: synthetic_ohlcv(1100, seed=k) for s, k in syms.items()}
    p["SOLUSDT"] = p["SOLUSDT"].iloc[300:]  # listed later
    p["XRPUSDT"] = p["XRPUSDT"].iloc[:800]  # delisted
    if n is not None:
        cut = p["BTCUSDT"].index[n]
        p = {s: df[df.index < cut] for s, df in p.items()}
    return p


def _portfolio_names():
    from trading_bot.portfolio_strategies import PORTFOLIO_REGISTRY
    return sorted(PORTFOLIO_REGISTRY)


@pytest.mark.parametrize("name", _portfolio_names())
def test_portfolio_strategies_have_no_lookahead(name):
    from trading_bot.portfolio_strategies import get_portfolio_strategy
    full = get_portfolio_strategy(name).run(_panel(), "1d", Costs()).equity
    for n in (700, 950):
        part = get_portfolio_strategy(name).run(_panel(n), "1d", Costs()).equity
        np.testing.assert_allclose(part.to_numpy(), full.to_numpy()[:len(part)], rtol=1e-9, atol=1e-6,
                                   err_msg=f"{name} cut={n}")


def test_rotation_bot_is_quote_currency_agnostic():
    """Renaming the pairs from USDT to USDC must not change any decision (incl. the BTC filter)."""
    from trading_bot.portfolio_strategies import get_portfolio_strategy
    usdt = _panel()
    usdc = {s.replace("USDT", "USDC"): df for s, df in usdt.items()}
    w1 = get_portfolio_strategy("rotation_bot_v1").weights(usdt, "1d")
    w2 = get_portfolio_strategy("rotation_bot_v1").weights(usdc, "1d")
    w2.columns = [c.replace("USDC", "USDT") for c in w2.columns]
    pd.testing.assert_frame_equal(w1, w2[w1.columns])
