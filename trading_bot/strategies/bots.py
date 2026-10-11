"""Order-based retail bots that cannot be expressed as simple signals:

* **DCA bot** in the style of 3Commas / Gainium / OctoBot DCA mode
  (base order + safety-order ladder + take-profit on the average price).
* **Grid bot** in the style of Pionex / Binance Spot Grid / OctoBot grid mode.

Both simulate limit orders against each bar's high/low with conservative
ordering assumptions (an order filled inside a bar cannot be closed in the same bar).
"""

from __future__ import annotations


import numpy as np
import pandas as pd

from ..backtest import BacktestResult, Costs
from ..data import interval_to_timedelta
from .base import Strategy, add


class _Account:
    def __init__(self, capital: float, costs: Costs):
        self.cash = capital
        self.units = 0.0
        self.fee = costs.fee
        self.slip = costs.slippage
        self.fees_paid = 0.0
        self.notional = 0.0

    def buy_value(self, value: float, price: float, market: bool) -> tuple[float, float]:
        """Spend ``value`` (incl. fee) at ``price``; limit orders pay no slippage."""
        px = price * (1 + self.slip) if market else price
        value = min(value, self.cash)
        if value <= 0:
            return 0.0, px
        qty = value / (px * (1 + self.fee))
        cost = qty * px
        self.cash -= cost * (1 + self.fee)
        self.units += qty
        self.fees_paid += cost * self.fee
        self.notional += cost
        return qty, px

    def sell_qty(self, qty: float, price: float, market: bool) -> float:
        px = price * (1 - self.slip) if market else price
        qty = min(qty, self.units)
        proceeds = qty * px
        self.cash += proceeds * (1 - self.fee)
        self.units -= qty
        if self.units < 1e-12:
            self.units = 0.0
        self.fees_paid += proceeds * self.fee
        self.notional += proceeds
        return proceeds * (1 - self.fee)


def _result(df, interval, equity, exposure, trades, acct, capital, name) -> BacktestResult:
    idx = df.index + interval_to_timedelta(interval)
    return BacktestResult(
        equity=pd.Series(equity, index=idx, name="equity"),
        exposure=pd.Series(exposure, index=idx, name="exposure"),
        trades=pd.DataFrame(trades, columns=["entry_time", "exit_time", "side", "entry_price", "exit_price",
                                             "units", "return", "bars", "exit_reason"]),
        fees_paid=acct.fees_paid,
        turnover=acct.notional / max(float(np.mean(equity)), 1e-9),
        initial_capital=capital,
        interval=interval,
        name=name,
    )


class DCABot(Strategy):
    family = "bot"
    source = "3Commas/Gainium-DCA-Bot (Standard-Setup: TP 1.5 %, 6 Safety Orders, Abstand 2 %, Step 1.2, Volumen 1.5)"
    description = "Kauft eine Basis-Order, verbilligt mit wachsenden Safety-Orders und verkauft alles mit 1.5 % Gewinn."

    def __init__(self, take_profit=0.015, safety_orders=6, deviation=0.02, step_scale=1.2,
                 volume_scale=1.5, so_size=2.0, **kw):
        super().__init__(take_profit=take_profit, safety_orders=safety_orders, deviation=deviation,
                         step_scale=step_scale, volume_scale=volume_scale, so_size=so_size, **kw)
        devs, vols = [], [1.0]
        d, step, v = 0.0, deviation, so_size
        for _ in range(safety_orders):
            d += step
            devs.append(d)
            vols.append(v)
            step *= step_scale
            v *= volume_scale
        self.devs = devs
        self.weights = np.array(vols) / sum(vols)  # share of deal capital per order

    def generate(self, df, interval):  # pragma: no cover - simulated directly
        raise NotImplementedError("DCABot is simulated via simulate()")

    def simulate(self, df: pd.DataFrame, interval: str, costs: Costs, capital: float = 10_000.0) -> BacktestResult:
        tp = self.params["take_profit"]
        o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        n = len(df)
        acct = _Account(capital, costs)
        equity, exposure = np.empty(n), np.empty(n)
        trades = []
        in_deal = False
        deal_capital = base_price = 0.0
        next_so = 0
        spent = 0.0
        entry_bar = 0
        for i in range(n):
            if not in_deal:  # start a new deal at the open (start condition: ASAP)
                deal_capital = acct.cash
                qty, px = acct.buy_value(deal_capital * self.weights[0], o[i], market=True)
                if qty > 0:
                    in_deal, base_price, next_so, entry_bar = True, px, 0, i
                    spent = qty * px * (1 + acct.fee)
            filled_now = False
            while in_deal and next_so < len(self.devs):
                level = base_price * (1 - self.devs[next_so])
                if l[i] > level:
                    break
                fill_px = min(level, o[i]) if i > entry_bar else level
                qty, px = acct.buy_value(deal_capital * self.weights[next_so + 1], fill_px, market=False)
                spent += qty * px * (1 + acct.fee)
                next_so += 1
                filled_now = True
            if in_deal and not filled_now and acct.units > 0:
                avg = (spent / (1 + acct.fee)) / acct.units
                tp_px = avg * (1 + tp + 2 * acct.fee)
                if h[i] >= tp_px and (i > entry_bar or o[i] < tp_px):
                    fill = max(tp_px, o[i]) if i > entry_bar else tp_px
                    qty = acct.units
                    got = acct.sell_qty(qty, fill, market=False)
                    trades.append({"entry_time": df.index[entry_bar], "exit_time": df.index[i], "side": "long",
                                   "entry_price": avg, "exit_price": fill, "units": qty,
                                   "return": got / spent - 1.0, "bars": i - entry_bar + 1, "exit_reason": "take_profit"})
                    in_deal = False
            equity[i] = acct.cash + acct.units * c[i]
            exposure[i] = acct.units * c[i] / equity[i] if equity[i] > 0 else 0.0
        if in_deal and acct.units > 0:
            value = acct.units * c[-1] * (1 - acct.fee)
            trades.append({"entry_time": df.index[entry_bar], "exit_time": pd.NaT, "side": "long",
                           "entry_price": spent / acct.units, "exit_price": c[-1], "units": acct.units,
                           "return": value / spent - 1.0, "bars": n - entry_bar, "exit_reason": "open"})
        return _result(df, interval, equity, exposure, trades, acct, capital, self.name)


class GridBot(Strategy):
    family = "bot"
    source = "Pionex/Binance Spot-Grid-Bot (geometrisch, 20 Grids, ±15 %, Neustart außerhalb der Range)"
    description = "Verteilt Kauf-/Verkaufsorders auf ein Preisgitter und verdient an Schwankungen innerhalb der Range."

    def __init__(self, grids=20, range_pct=0.15, **kw):
        super().__init__(grids=grids, range_pct=range_pct, **kw)

    def generate(self, df, interval):  # pragma: no cover - simulated directly
        raise NotImplementedError("GridBot is simulated via simulate()")

    def simulate(self, df: pd.DataFrame, interval: str, costs: Costs, capital: float = 10_000.0) -> BacktestResult:
        n_grid, width = self.params["grids"], self.params["range_pct"]
        o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        n = len(df)
        acct = _Account(capital, costs)
        equity, exposure = np.empty(n), np.empty(n)
        trades = []
        levels = None
        slot_qty = slot_cost = slot_bar = None
        need_init = True
        for i in range(n):
            if need_init:
                p0 = o[i]
                ratio = ((1 + width) / (1 - width)) ** (1.0 / n_grid)
                levels = (p0 * (1 - width)) * ratio ** np.arange(n_grid + 1)
                slot_qty = np.zeros(n_grid)
                slot_cost = np.zeros(n_grid)
                slot_bar = np.full(n_grid, -1)
                per_slot = (acct.cash + acct.units * p0) / n_grid
                # slots above the current price start filled (coins to sell higher)
                for k in range(n_grid):
                    if levels[k] >= p0:
                        qty, px = acct.buy_value(per_slot, p0, market=True)
                        slot_qty[k], slot_cost[k], slot_bar[k] = qty, qty * px * (1 + acct.fee), i
                need_init = False
                slot_value = per_slot
            sold_now = np.zeros(n_grid, dtype=bool)
            # sells: filled slot k sells at level k+1
            for k in range(n_grid):
                if slot_qty[k] > 0 and slot_bar[k] < i and h[i] >= levels[k + 1]:
                    fill = max(levels[k + 1], o[i])
                    got = acct.sell_qty(slot_qty[k], fill, market=False)
                    trades.append({"entry_time": df.index[slot_bar[k]], "exit_time": df.index[i], "side": "long",
                                   "entry_price": slot_cost[k] / slot_qty[k], "exit_price": fill,
                                   "units": slot_qty[k], "return": got / slot_cost[k] - 1.0,
                                   "bars": i - slot_bar[k] + 1, "exit_reason": "grid"})
                    slot_qty[k] = slot_cost[k] = 0.0
                    sold_now[k] = True
            # buys: empty slot k buys at level k
            for k in range(n_grid - 1, -1, -1):
                if slot_qty[k] == 0 and not sold_now[k] and l[i] <= levels[k]:
                    fill = min(levels[k], o[i])
                    qty, px = acct.buy_value(slot_value, fill, market=False)
                    if qty > 0:
                        slot_qty[k], slot_cost[k], slot_bar[k] = qty, qty * px * (1 + acct.fee), i
            equity[i] = acct.cash + acct.units * c[i]
            exposure[i] = acct.units * c[i] / equity[i] if equity[i] > 0 else 0.0
            # price left the range -> close everything and rebuild the grid around the new price
            if c[i] > levels[-1] * (1 + width / n_grid) or c[i] < levels[0] * (1 - width / n_grid):
                if acct.units > 0:
                    qty_total = acct.units
                    cost_total = slot_cost.sum()
                    got = acct.sell_qty(qty_total, c[i], market=True)
                    trades.append({"entry_time": df.index[max(int(slot_bar.max()), 0)], "exit_time": df.index[i],
                                   "side": "long", "entry_price": cost_total / qty_total, "exit_price": c[i],
                                   "units": qty_total, "return": got / cost_total - 1.0 if cost_total else 0.0,
                                   "bars": 1, "exit_reason": "range_exit"})
                    equity[i] = acct.cash
                    exposure[i] = 0.0
                need_init = True
        return _result(df, interval, equity, exposure, trades, acct, capital, self.name)


add("dca_bot", DCABot)
add("grid_bot", GridBot)
