"""Event-driven backtest engine.

Execution model (designed to avoid the usual backtest illusions):

* Strategies see a bar only after it has closed. A decision taken on bar ``t`` is
  executed at the **open of bar t+1**, never at the close that produced the signal.
* Every fill pays a proportional fee and slippage (both configurable).
* Protective exits (stop-loss, trailing stop, Freqtrade-style ROI table, time stop)
  are simulated intrabar with the bar's high/low. When a stop and a take-profit
  could both have been hit inside the same bar the stop is assumed to come first
  (pessimistic), and gaps through a stop fill at the open.
* No leverage: exposure is capped to the available equity.

Strategies talk to the engine through :class:`Signals`:

* **signal mode** - boolean ``entries`` / ``exits`` (Freqtrade ``enter_long`` /
  ``exit_long`` semantics: enter when flat and the entry condition is true).
* **target mode** - a float ``target`` exposure per bar (0 = flat, 1 = fully
  invested, negative = short if allowed). ``NaN`` keeps the current exposure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .data import INTERVAL_MINUTES, interval_to_timedelta


@dataclass
class Costs:
    fee: float = 0.001        # 0.10 % per side (Binance spot taker fee)
    slippage: float = 0.0005  # 0.05 % adverse price move per fill


@dataclass
class ExitRules:
    """Protective exits handled by the engine (Freqtrade-compatible semantics)."""

    stop_loss: float | None = None        # e.g. 0.10 -> exit at -10 % from entry
    trailing_stop: float | None = None    # trailing distance once activated
    trailing_offset: float = 0.0          # profit needed before trailing_stop activates
    trail_stop_loss: bool = False         # stop_loss itself trails the high-water mark
    roi: dict[int, float] | None = None   # {minutes in trade: minimum profit to take}
    max_bars: int | None = None           # time stop
    rearm_after_stop: bool = True         # target mode: wait for target<=0 after a stop

    def active(self) -> bool:
        return any(v is not None for v in (self.stop_loss, self.trailing_stop, self.roi, self.max_bars))


@dataclass
class Signals:
    entries: np.ndarray | pd.Series | None = None
    exits: np.ndarray | pd.Series | None = None
    target: np.ndarray | pd.Series | None = None
    size: float | np.ndarray | pd.Series = 1.0
    rules: ExitRules = field(default_factory=ExitRules)
    # Optional per-bar stop distance (fraction of price, e.g. 2*ATR/close). The value
    # of the signal bar is frozen when a trade opens and overrides rules.stop_loss.
    stop_distance: np.ndarray | pd.Series | None = None
    min_rebalance: float = 0.05           # target mode: ignore exposure changes smaller than this

    @property
    def mode(self) -> str:
        return "target" if self.target is not None else "signal"


@dataclass
class BacktestResult:
    equity: pd.Series                    # account value at each bar close
    exposure: pd.Series                  # position value / equity at each bar close
    trades: pd.DataFrame
    fees_paid: float
    turnover: float                      # traded notional / average equity
    initial_capital: float
    interval: str
    name: str = ""
    symbol: str = ""

    @property
    def returns(self) -> pd.Series:
        return self.equity.pct_change().fillna(0.0)


def _as_array(x, n: int, dtype=float, fill=None) -> np.ndarray | None:
    if x is None:
        return None
    if isinstance(x, (pd.Series, pd.DataFrame)):
        x = x.to_numpy()
    if np.isscalar(x):
        return np.full(n, x, dtype=dtype)
    arr = np.asarray(x)
    if arr.shape[0] != n:
        raise ValueError(f"signal length {arr.shape[0]} != data length {n}")
    if dtype is bool:
        return np.nan_to_num(arr.astype(float), nan=0.0).astype(bool)
    arr = arr.astype(dtype)
    if fill is not None:
        arr = np.where(np.isnan(arr), fill, arr)
    return arr


def _roi_schedule(roi: dict[int, float] | None) -> list[tuple[float, float]]:
    if not roi:
        return []
    return sorted(((float(k), float(v)) for k, v in roi.items()), key=lambda kv: kv[0])


def _roi_threshold(schedule: list[tuple[float, float]], minutes: float) -> float | None:
    level = None
    for start, value in schedule:
        if minutes >= start:
            level = value
        else:
            break
    return level


def run_backtest(
    df: pd.DataFrame,
    signals: Signals,
    interval: str,
    costs: Costs | None = None,
    initial_capital: float = 10_000.0,
    allow_short: bool = False,
    name: str = "",
    symbol: str = "",
) -> BacktestResult:
    costs = costs or Costs()
    n = len(df)
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    lo = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)

    mode = signals.mode
    entries = _as_array(signals.entries, n, bool)
    exits = _as_array(signals.exits, n, bool)
    target = _as_array(signals.target, n, float)
    size = _as_array(signals.size, n, float, fill=0.0)
    stop_dist = _as_array(signals.stop_distance, n, float)
    if mode == "signal" and entries is None:
        raise ValueError("signal mode requires entries")
    if exits is None:
        exits = np.zeros(n, dtype=bool)

    rules = signals.rules
    schedule = _roi_schedule(rules.roi)
    bar_minutes = INTERVAL_MINUTES[interval]
    fee, slip = costs.fee, costs.slippage
    min_reb = signals.min_rebalance
    has_rules = rules.active() or stop_dist is not None

    cash = float(initial_capital)
    units = 0.0
    equity = np.empty(n)
    exposure = np.empty(n)
    fees_paid = 0.0
    traded_notional = 0.0

    # trade bookkeeping
    entry_bar = -1
    avg_entry = 0.0
    high_water = 0.0
    low_water = 0.0
    trade_stop = None     # stop distance frozen at entry
    buy_flow = 0.0        # cash paid for buys during the trade (incl. fees)
    sell_flow = 0.0       # cash received from sells during the trade (net of fees)
    trade_entry_time = None
    trade_entry_price = 0.0
    stopped_side = 0.0    # target mode: side of the last protective exit, waiting to re-arm
    pending: float | None = None  # exposure to establish at next open
    trades: list[dict] = []
    times = df.index

    def fill(qty: float, price: float) -> None:
        """Buy (qty>0) or sell (qty<0) at a reference price, paying slippage and fee."""
        nonlocal cash, units, fees_paid, traded_notional, avg_entry, buy_flow, sell_flow
        if qty == 0.0:
            return
        exec_price = price * (1.0 + slip) if qty > 0 else price * (1.0 - slip)
        notional = abs(qty) * exec_price
        f = notional * fee
        fees_paid += f
        traded_notional += notional
        prev_units = units
        if qty > 0:
            cash -= notional + f
            buy_flow += notional + f
        else:
            cash += notional - f
            sell_flow += notional - f
        units = prev_units + qty
        if abs(units) < 1e-12:
            units = 0.0
        if (prev_units >= 0 and qty > 0) or (prev_units <= 0 and qty < 0):  # opening / adding
            new_abs = abs(units)
            avg_entry = (avg_entry * abs(prev_units) + exec_price * abs(qty)) / new_abs if new_abs else 0.0

    def trade_return(side: float) -> float:
        if side > 0:
            return sell_flow / buy_flow - 1.0 if buy_flow else 0.0
        return (sell_flow - buy_flow) / sell_flow if sell_flow else 0.0

    def close_trade(i: int, price: float, reason: str) -> None:
        nonlocal entry_bar, buy_flow, sell_flow, avg_entry
        side = 1.0 if units > 0 else -1.0
        start_units = units
        fill(-units, price)
        ret = trade_return(side)
        trades.append({
            "entry_time": trade_entry_time, "exit_time": times[i], "side": "long" if side > 0 else "short",
            "entry_price": trade_entry_price, "exit_price": price, "units": abs(start_units),
            "return": ret, "bars": i - entry_bar + 1, "exit_reason": reason,
        })
        entry_bar = -1
        buy_flow = sell_flow = 0.0
        avg_entry = 0.0

    def rebalance(i: int, desired: float) -> None:
        """Move to `desired` exposure at the open of bar i."""
        nonlocal entry_bar, high_water, low_water, trade_entry_time, trade_entry_price, trade_stop
        price = o[i]
        eq = cash + units * price
        if eq <= 0:
            return
        if not allow_short:
            desired = max(desired, 0.0)
        desired = max(min(desired, 1.0), -1.0)
        cur_exp = units * price / eq
        if desired == 0.0:
            if units != 0.0:
                close_trade(i, price, "signal")
            return
        if units != 0.0 and math.copysign(1.0, desired) != math.copysign(1.0, units):
            close_trade(i, price, "signal")  # flip: close first, then open the other side
            eq = cash
            cur_exp = 0.0
        if units != 0.0 and abs(desired - cur_exp) < min_reb:
            return
        target_value = desired * eq
        delta_value = target_value - units * price
        if delta_value > 0:
            qty = delta_value / (price * (1.0 + slip) * (1.0 + fee))
        else:
            qty = delta_value / (price * (1.0 - slip))
        was_flat = units == 0.0
        fill(qty, price)
        if was_flat and units != 0.0:
            entry_bar = i
            trade_entry_time = times[i]
            trade_entry_price = avg_entry
            high_water = avg_entry
            low_water = avg_entry
            trade_stop = rules.stop_loss
            if stop_dist is not None and i > 0 and not np.isnan(stop_dist[i - 1]):
                trade_stop = float(stop_dist[i - 1])

    for i in range(n):
        # 1) execute the order decided at the previous close
        if pending is not None:
            rebalance(i, pending)
            pending = None

        # 2) protective exits inside the bar
        if has_rules and units != 0.0:
            exit_price = None
            reason = ""
            if units > 0:
                stop = -math.inf
                if trade_stop is not None:
                    base = high_water if rules.trail_stop_loss else avg_entry
                    stop = base * (1.0 - trade_stop)
                if rules.trailing_stop is not None and high_water >= avg_entry * (1.0 + rules.trailing_offset):
                    stop = max(stop, high_water * (1.0 - rules.trailing_stop))
                if o[i] <= stop and i > entry_bar:
                    exit_price, reason = o[i], "stop_loss"
                elif lo[i] <= stop:
                    exit_price, reason = min(stop, o[i]), "stop_loss"
                elif schedule:
                    roi = _roi_threshold(schedule, (i - entry_bar) * bar_minutes)
                    if roi is not None:
                        roi_price = avg_entry * (1.0 + roi + 2.0 * fee)
                        if h[i] >= roi_price:
                            exit_price, reason = max(roi_price, o[i]) if i > entry_bar else roi_price, "roi"
                if exit_price is None:
                    high_water = max(high_water, h[i])
            else:  # short position
                stop = math.inf
                if trade_stop is not None:
                    base = low_water if rules.trail_stop_loss else avg_entry
                    stop = base * (1.0 + trade_stop)
                if rules.trailing_stop is not None and low_water <= avg_entry * (1.0 - rules.trailing_offset):
                    stop = min(stop, low_water * (1.0 + rules.trailing_stop))
                if o[i] >= stop and i > entry_bar:
                    exit_price, reason = o[i], "stop_loss"
                elif h[i] >= stop:
                    exit_price, reason = max(stop, o[i]), "stop_loss"
                elif schedule:
                    roi = _roi_threshold(schedule, (i - entry_bar) * bar_minutes)
                    if roi is not None:
                        roi_price = avg_entry * (1.0 - roi - 2.0 * fee)
                        if lo[i] <= roi_price:
                            exit_price, reason = min(roi_price, o[i]) if i > entry_bar else roi_price, "roi"
                if exit_price is None:
                    low_water = min(low_water, lo[i])
            if exit_price is None and rules.max_bars is not None and i - entry_bar + 1 >= rules.max_bars:
                exit_price, reason = c[i], "time"
            if exit_price is not None:
                side = 1.0 if units > 0 else -1.0
                close_trade(i, exit_price, reason)
                if mode == "target" and rules.rearm_after_stop and reason != "time":
                    stopped_side = side

        # 3) mark to market and decide the next order
        equity[i] = cash + units * c[i]
        exposure[i] = units * c[i] / equity[i] if equity[i] > 0 else 0.0
        if equity[i] <= 0:  # account blown (only possible with shorts) -> stop trading
            equity[i:] = equity[i]
            exposure[i:] = 0.0
            break

        if mode == "signal":
            if units == 0.0:
                if entries[i] and not exits[i] and size[i] != 0.0:
                    pending = size[i]
            elif exits[i]:
                pending = 0.0
        else:
            t = target[i]
            if not np.isnan(t):
                if stopped_side != 0.0:
                    if t * stopped_side <= 0.0:  # target left the stopped side -> re-armed
                        stopped_side = 0.0
                    else:
                        t = 0.0
                pending = t

    # open trade at the end is reported with its mark-to-market return
    if units != 0.0 and entry_bar >= 0:
        value = abs(units) * c[-1]
        if units > 0:
            sell_flow += value * (1 - fee)
            ret = trade_return(1.0)
        else:
            buy_flow += value * (1 + fee)
            ret = trade_return(-1.0)
        trades.append({
            "entry_time": trade_entry_time, "exit_time": pd.NaT, "side": "long" if units > 0 else "short",
            "entry_price": trade_entry_price, "exit_price": c[-1], "units": abs(units),
            "return": ret, "bars": n - entry_bar, "exit_reason": "open",
        })

    close_index = df.index + interval_to_timedelta(interval)
    eq_series = pd.Series(equity, index=close_index, name="equity")
    avg_eq = float(np.mean(equity)) if n else initial_capital
    return BacktestResult(
        equity=eq_series,
        exposure=pd.Series(exposure, index=close_index, name="exposure"),
        trades=pd.DataFrame(trades, columns=[
            "entry_time", "exit_time", "side", "entry_price", "exit_price", "units",
            "return", "bars", "exit_reason"]),
        fees_paid=fees_paid,
        turnover=traded_notional / avg_eq if avg_eq else 0.0,
        initial_capital=initial_capital,
        interval=interval,
        name=name,
        symbol=symbol,
    )
