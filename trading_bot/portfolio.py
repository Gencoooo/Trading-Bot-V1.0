"""Multi-asset portfolio backtester.

The per-coin engine in :mod:`trading_bot.backtest` evaluates every bot on each
coin separately (equal-weight sleeves). Some ideas - cross-sectional momentum,
risk-parity sizing - need one account that allocates capital *between* coins.
This engine provides that with the same execution model: weights decided on the
close of bar t are traded at the open of bar t+1, every fill pays fee and
slippage, a coin whose data ends (delisting) is sold at its last close.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import Costs
from .data import interval_to_timedelta, load_ohlcv


@dataclass
class PortfolioResult:
    equity: pd.Series
    weights: pd.DataFrame
    fees_paid: float
    turnover: float
    interval: str
    name: str = ""

    @property
    def exposure(self) -> pd.Series:
        return self.weights.sum(axis=1)


def load_panel(symbols, interval: str, **kw) -> dict[str, pd.DataFrame]:
    return {s: load_ohlcv(s, interval, **kw) for s in symbols}


def align_panel(panel: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Wide frames (time x symbol) for open/high/low/close/volume on the union index."""
    idx = pd.DatetimeIndex(sorted(set().union(*[df.index for df in panel.values()])), name="time")
    return {f: pd.DataFrame({s: df[f].reindex(idx) for s, df in panel.items()}) for f in
            ("open", "high", "low", "close", "volume")}


def run_portfolio_backtest(panel: dict[str, pd.DataFrame], weights: pd.DataFrame, interval: str,
                           costs: Costs | None = None, initial_capital: float = 10_000.0,
                           band: float = 0.02, name: str = "") -> PortfolioResult:
    """``weights``: target weight per symbol decided at each bar close (NaN = keep).
    Weights are clipped to >= 0 and scaled down if they sum to more than 1."""
    costs = costs or Costs()
    wide = align_panel(panel)
    idx = wide["close"].index
    syms = list(wide["close"].columns)
    o = wide["open"].to_numpy(float)
    c = wide["close"].to_numpy(float)
    W = weights.reindex(index=idx, columns=syms).to_numpy(float)
    n, m = c.shape
    last_bar = np.array([np.max(np.where(~np.isnan(c[:, j]))[0]) if (~np.isnan(c[:, j])).any() else -1
                         for j in range(m)])
    fee, slip = costs.fee, costs.slippage
    cash = initial_capital
    units = np.zeros(m)
    last_px = np.full(m, np.nan)
    equity = np.empty(n)
    held_w = np.zeros((n, m))
    pending = None
    fees = 0.0
    notional = 0.0

    for i in range(n):
        has = ~np.isnan(o[i])
        # 1) trade at the open towards the pending target weights
        if pending is not None:
            px = np.where(has, o[i], last_px)
            value = units * np.nan_to_num(px)
            eq = cash + value.sum()
            if eq > 0:
                cur_w = value / eq
                tgt = pending.copy()
                tgt[~has] = cur_w[~has]  # cannot trade coins without a bar
                delta = tgt - cur_w
                trade = has & ((np.abs(delta) >= band) | ((tgt == 0) & (units != 0)))
                # sells first to free cash, then buys
                for j in np.where(trade & (delta < 0))[0]:
                    qty = min(units[j], -delta[j] * eq / px[j]) if tgt[j] > 0 else units[j]
                    ex = px[j] * (1 - slip)
                    cash += qty * ex * (1 - fee)
                    fees += qty * ex * fee
                    notional += qty * ex
                    units[j] -= qty
                for j in np.where(trade & (delta > 0))[0]:
                    ex = px[j] * (1 + slip)
                    spend = min(delta[j] * eq, cash)
                    if spend <= 0:
                        continue
                    qty = spend / (ex * (1 + fee))
                    cash -= qty * ex * (1 + fee)
                    fees += qty * ex * fee
                    notional += qty * ex
                    units[j] += qty
            pending = None
        last_px = np.where(~np.isnan(c[i]), c[i], last_px)
        # 2) coins whose data ends here are sold at their final close
        for j in np.where((last_bar == i) & (units > 0) & (i < n - 1))[0]:
            ex = c[i, j] * (1 - slip)
            cash += units[j] * ex * (1 - fee)
            fees += units[j] * ex * fee
            notional += units[j] * ex
            units[j] = 0.0
        value = units * np.nan_to_num(last_px)
        equity[i] = cash + value.sum()
        held_w[i] = value / equity[i] if equity[i] > 0 else 0.0
        # 3) read the decision taken at this close
        w = W[i]
        if not np.isnan(w).all():
            w = np.where(np.isnan(w), held_w[i], np.clip(w, 0.0, None))
            w[last_bar <= i] = 0.0  # never buy a coin that has no future bars
            total = w.sum()
            if total > 1.0:
                w = w / total
            pending = w

    close_idx = idx + interval_to_timedelta(interval)
    eq = pd.Series(equity, index=close_idx, name="equity")
    return PortfolioResult(
        equity=eq,
        weights=pd.DataFrame(held_w, index=close_idx, columns=syms),
        fees_paid=fees,
        turnover=notional / max(float(np.mean(equity)), 1e-9),
        interval=interval,
        name=name,
    )


class PortfolioStrategy:
    """Base class for strategies that allocate between coins."""

    name = "portfolio"
    family = "portfolio"
    source = ""
    description = ""
    band = 0.02

    def weights(self, panel: dict[str, pd.DataFrame], interval: str) -> pd.DataFrame:  # pragma: no cover
        raise NotImplementedError

    def run(self, panel: dict[str, pd.DataFrame], interval: str, costs: Costs | None = None,
            initial_capital: float = 10_000.0) -> PortfolioResult:
        return run_portfolio_backtest(panel, self.weights(panel, interval), interval, costs, initial_capital,
                                      band=self.band, name=self.name)
