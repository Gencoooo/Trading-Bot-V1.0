"""Look-ahead bias detector for *every* registered strategy.

A strategy is causal if appending future candles never changes its past
behaviour. We run each strategy on a truncated history and on the full history
and require identical equity curves on the common part. This catches the
classic bugs of public bots: global min/max scaling, centered windows,
``shift(-n)`` features, full-sample model fitting, etc.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("TB_TORCH_THREADS", "1")

from trading_bot.backtest import Costs, run_backtest  # noqa: E402
from trading_bot.data import synthetic_ohlcv  # noqa: E402
from trading_bot.strategies import get_strategy, list_strategies  # noqa: E402
from trading_bot.strategies.ml import torch_available  # noqa: E402

DATA = synthetic_ohlcv(n=1300, interval="1d", seed=7)
CUTS = (950, 1150)


def _equity(strategy, df):
    if hasattr(strategy, "simulate"):
        return strategy.simulate(df, "1d", Costs()).equity.to_numpy()
    return run_backtest(df, strategy.generate(df, "1d"), "1d", Costs()).equity.to_numpy()


def _names():
    names = list_strategies()
    if not torch_available():
        names = [n for n in names if n != "ml_lstm"]
    return names


@pytest.mark.parametrize("name", _names())
def test_strategy_has_no_lookahead(name):
    full = _equity(get_strategy(name), DATA)
    for cut in CUTS:
        part = _equity(get_strategy(name), DATA.iloc[:cut])
        np.testing.assert_allclose(part, full[:cut], rtol=1e-9, atol=1e-6,
                                   err_msg=f"{name} changes its past when future data is appended (cut={cut})")


def test_detector_flags_the_leaky_tutorial_demo():
    """The deliberately wrong 'tutorial' ML bot must be caught by the same check."""
    full = _equity(get_strategy("demo_leaky_tutorial_rf"), DATA)
    part = _equity(get_strategy("demo_leaky_tutorial_rf"), DATA.iloc[:CUTS[0]])
    assert not np.allclose(part, full[:CUTS[0]])


def test_detector_catches_a_leaky_strategy():
    """Sanity check: a strategy that normalizes with the global max must be caught."""
    from trading_bot.backtest import Signals

    class Leaky:
        def generate(self, df, interval):
            z = (df["close"] - df["close"].min()) / (df["close"].max() - df["close"].min())
            return Signals(target=(z < 0.5).astype(float).to_numpy())

    full = run_backtest(DATA, Leaky().generate(DATA, "1d"), "1d").equity.to_numpy()
    part = run_backtest(DATA.iloc[:CUTS[0]], Leaky().generate(DATA.iloc[:CUTS[0]], "1d"), "1d").equity.to_numpy()
    assert not np.allclose(part, full[:CUTS[0]])
