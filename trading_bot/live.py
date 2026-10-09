"""Paper and live trading.

The runner re-uses the backtest engine to decide what to hold: on every new
closed candle it replays the strategy over recent history and adopts the
position the backtest would hold right now. Live behaviour therefore matches
the tested behaviour by construction (same code path, no re-implementation).

* :class:`PaperBroker` simulates fills at the live price (fees + slippage) and
  keeps its state in ``state/<name>.json``. This is the default.
* :class:`CCXTBroker` sends real market orders through `ccxt`
  (``pip install ccxt``). It is only used with ``--live`` plus an explicit
  confirmation flag, and API keys come from environment variables.

Limitation: protective stops are evaluated on candle closes, not tick-by-tick.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .backtest import Costs, run_backtest
from .data import INTERVAL_MINUTES, fetch_klines, interval_to_timedelta
from .strategies import Strategy

log = logging.getLogger("trading_bot.live")
STATE_DIR = Path(__file__).resolve().parent.parent / "state"


def latest_price(symbol: str) -> float:
    for url in ("https://data-api.binance.vision/api/v3/ticker/price", "https://api.binance.com/api/v3/ticker/price"):
        try:
            r = requests.get(url, params={"symbol": symbol}, timeout=15)
            if r.ok:
                return float(r.json()["price"])
        except requests.RequestException:
            continue
    raise RuntimeError(f"no price for {symbol}")


def target_exposure(strategy: Strategy, df: pd.DataFrame, interval: str, price_now: float, costs: Costs) -> float:
    """Exposure the strategy wants to hold *now*, i.e. after executing the order
    decided at the last closed candle at the current price."""
    nxt = df.index[-1] + interval_to_timedelta(interval)
    row = pd.DataFrame({"open": [price_now], "high": [price_now], "low": [price_now], "close": [price_now],
                        "volume": [0.0], "quote_volume": [0.0], "trades": [0.0]}, index=pd.DatetimeIndex([nxt]))
    ext = pd.concat([df, row])
    if hasattr(strategy, "simulate"):
        res = strategy.simulate(ext, interval, costs)
    else:
        sig = strategy.generate(df, interval)
        # extend the signal arrays by one bar that holds the last decision
        def extend(x, fill):
            if x is None:
                return None
            arr = np.asarray(x, dtype=float)
            return np.append(arr, fill)
        sig.entries = None if sig.entries is None else extend(sig.entries, 0).astype(bool)
        sig.exits = None if sig.exits is None else extend(sig.exits, 0).astype(bool)
        sig.target = None if sig.target is None else extend(sig.target, np.nan)
        if not np.isscalar(sig.size):
            sig.size = extend(sig.size, 0.0)
        if sig.stop_distance is not None:
            sig.stop_distance = extend(sig.stop_distance, np.nan)
        res = run_backtest(ext, sig, interval, costs)
    return float(res.exposure.iloc[-1])


# --------------------------------------------------------------------------- #
# Brokers
# --------------------------------------------------------------------------- #
class Broker:
    quote = "USDT"

    def balances(self) -> dict[str, float]:  # pragma: no cover
        raise NotImplementedError

    def price(self, symbol: str) -> float:
        return latest_price(symbol)

    def market_order(self, symbol: str, side: str, qty: float) -> dict:  # pragma: no cover
        raise NotImplementedError

    def base_asset(self, symbol: str) -> str:
        return symbol[: -len(self.quote)] if symbol.endswith(self.quote) else symbol


@dataclass
class PaperBroker(Broker):
    name: str = "paper"
    starting_cash: float = 10_000.0
    costs: Costs = field(default_factory=Costs)
    state: dict = field(default_factory=dict)

    def __post_init__(self):
        self.path = STATE_DIR / f"{self.name}.json"
        if self.path.exists():
            self.state = json.loads(self.path.read_text())
        else:
            self.state = {"balances": {self.quote: self.starting_cash}, "trades": [], "equity": []}
            self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2, default=str))

    def balances(self) -> dict[str, float]:
        return dict(self.state["balances"])

    def market_order(self, symbol: str, side: str, qty: float) -> dict:
        px = self.price(symbol)
        base = self.base_asset(symbol)
        bal = self.state["balances"]
        if side == "buy":
            fill = px * (1 + self.costs.slippage)
            cost = qty * fill * (1 + self.costs.fee)
            if cost > bal.get(self.quote, 0.0) + 1e-9:
                qty = bal.get(self.quote, 0.0) / (fill * (1 + self.costs.fee))
                cost = qty * fill * (1 + self.costs.fee)
            bal[self.quote] = bal.get(self.quote, 0.0) - cost
            bal[base] = bal.get(base, 0.0) + qty
        else:
            qty = min(qty, bal.get(base, 0.0))
            fill = px * (1 - self.costs.slippage)
            bal[base] = bal.get(base, 0.0) - qty
            bal[self.quote] = bal.get(self.quote, 0.0) + qty * fill * (1 - self.costs.fee)
        trade = {"time": datetime.now(timezone.utc).isoformat(), "symbol": symbol, "side": side,
                 "qty": qty, "price": fill}
        self.state["trades"].append(trade)
        self._save()
        return trade

    def record_equity(self, value: float) -> None:
        self.state["equity"].append({"time": datetime.now(timezone.utc).isoformat(), "equity": value})
        self._save()


class CCXTBroker(Broker):
    """Real orders via ccxt. Keys: TB_API_KEY / TB_API_SECRET environment variables."""

    def __init__(self, exchange: str = "binance", testnet: bool = False):
        try:
            import ccxt
        except ImportError as exc:  # pragma: no cover
            raise SystemExit("Live trading needs ccxt: pip install ccxt") from exc
        key, secret = os.environ.get("TB_API_KEY"), os.environ.get("TB_API_SECRET")
        if not key or not secret:
            raise SystemExit("Set TB_API_KEY and TB_API_SECRET for live trading.")
        self.ex = getattr(ccxt, exchange)({"apiKey": key, "secret": secret, "enableRateLimit": True})
        if testnet:
            self.ex.set_sandbox_mode(True)
        self.ex.load_markets()

    def _market(self, symbol: str) -> str:
        return f"{self.base_asset(symbol)}/{self.quote}"

    def balances(self) -> dict[str, float]:
        bal = self.ex.fetch_balance()
        return {k: float(v) for k, v in bal.get("free", {}).items() if v}

    def price(self, symbol: str) -> float:
        return float(self.ex.fetch_ticker(self._market(symbol))["last"])

    def market_order(self, symbol: str, side: str, qty: float) -> dict:
        m = self._market(symbol)
        amount = float(self.ex.amount_to_precision(m, qty))
        if amount <= 0:
            return {}
        return self.ex.create_order(m, "market", side, amount)


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
@dataclass
class BotRunner:
    strategy: Strategy
    symbols: list[str]
    interval: str
    broker: Broker
    history_bars: int = 1500
    min_order_value: float = 10.0      # exchange minimum notional (Binance: ~5-10 USDT)
    rebalance_band: float = 0.05       # ignore exposure changes smaller than this
    costs: Costs = field(default_factory=Costs)

    def portfolio_value(self, prices: dict[str, float]) -> float:
        bal = self.broker.balances()
        value = bal.get(self.broker.quote, 0.0)
        for s in self.symbols:
            value += bal.get(self.broker.base_asset(s), 0.0) * prices[s]
        return value

    def step(self) -> dict:
        """One decision cycle over all symbols (call after each candle close)."""
        prices = {s: self.broker.price(s) for s in self.symbols}
        total = self.portfolio_value(prices)
        sleeve = total / len(self.symbols)  # equal-weight sleeves, like the backtests
        report = {}
        start = pd.Timestamp.now(tz="UTC") - interval_to_timedelta(self.interval) * (self.history_bars + 2)
        for s in self.symbols:
            df = fetch_klines(s, self.interval, start=start)
            if len(df) < 300:
                log.warning("%s: not enough history (%d bars)", s, len(df))
                continue
            want = max(0.0, min(1.0, target_exposure(self.strategy, df, self.interval, prices[s], self.costs)))
            held = self.broker.balances().get(self.broker.base_asset(s), 0.0)
            cur = held * prices[s] / sleeve if sleeve > 0 else 0.0
            delta_value = (want - cur) * sleeve
            action = "hold"
            if abs(want - cur) >= self.rebalance_band or (want == 0.0 and held > 0):
                qty = abs(delta_value) / prices[s]
                if abs(delta_value) >= self.min_order_value:
                    side = "buy" if delta_value > 0 else "sell"
                    if side == "sell" and want == 0.0:
                        qty = held
                    self.broker.market_order(s, side, qty)
                    action = f"{side} {qty:.6g}"
            report[s] = {"price": prices[s], "target": round(want, 3), "current": round(cur, 3), "action": action}
            log.info("%s price=%.6g target=%.2f current=%.2f -> %s", s, prices[s], want, cur, action)
        value = self.portfolio_value(prices)
        if isinstance(self.broker, PaperBroker):
            self.broker.record_equity(value)
        report["_equity"] = value
        return report

    def seconds_to_next_close(self) -> float:
        step = INTERVAL_MINUTES[self.interval] * 60
        now = time.time()
        return step - (now % step) + 5  # a few seconds after the candle closed

    def run_forever(self) -> None:  # pragma: no cover - long running
        log.info("Bot %s on %s (%s) started", self.strategy.name, ",".join(self.symbols), self.interval)
        while True:
            try:
                self.step()
            except Exception:  # keep running through transient API errors
                log.exception("step failed")
            wait = self.seconds_to_next_close()
            log.info("next decision in %.0f min", wait / 60)
            time.sleep(max(wait, 1.0))


@dataclass
class PortfolioBotRunner:
    """Runs a portfolio strategy (one account, capital allocated between coins)."""

    strategy: object                   # trading_bot.portfolio.PortfolioStrategy
    symbols: list[str]
    interval: str
    broker: Broker
    history_bars: int = 1500
    min_order_value: float = 10.0

    def target_weights(self) -> dict[str, float] | None:
        start = pd.Timestamp.now(tz="UTC") - interval_to_timedelta(self.interval) * (self.history_bars + 2)
        panel = {s: fetch_klines(s, self.interval, start=start) for s in self.symbols}
        panel = {s: df for s, df in panel.items() if len(df) > 300}
        w = self.strategy.weights(panel, self.interval)
        row = w.iloc[-1]
        if row.isna().all():
            return None  # no rebalance scheduled at this candle
        row = row.fillna(0.0).clip(lower=0.0)
        if row.sum() > 1.0:
            row = row / row.sum()
        return {s: float(row.get(s, 0.0)) for s in self.symbols}

    def step(self) -> dict:
        prices = {s: self.broker.price(s) for s in self.symbols}
        bal = self.broker.balances()
        holdings = {s: bal.get(self.broker.base_asset(s), 0.0) * prices[s] for s in self.symbols}
        total = bal.get(self.broker.quote, 0.0) + sum(holdings.values())
        target = self.target_weights()
        report = {"_equity": total, "_rebalanced": target is not None}
        if target is None or total <= 0:
            return report
        band = getattr(self.strategy, "band", 0.02)
        deltas = {s: target[s] - holdings[s] / total for s in self.symbols}
        for s in sorted(self.symbols, key=lambda k: deltas[k]):  # sells first, then buys
            d = deltas[s]
            if abs(d) < band and not (target[s] == 0 and holdings[s] > 0):
                continue
            value = abs(d) * total
            if value < self.min_order_value:
                continue
            side = "buy" if d > 0 else "sell"
            qty = value / prices[s]
            if side == "sell" and target[s] == 0:
                qty = bal.get(self.broker.base_asset(s), 0.0)
            self.broker.market_order(s, side, qty)
            report[s] = {"target": round(target[s], 3), "was": round(holdings[s] / total, 3), "action": side}
            log.info("%s target=%.3f was=%.3f -> %s %.6g", s, target[s], holdings[s] / total, side, qty)
        if isinstance(self.broker, PaperBroker):
            self.broker.record_equity(total)
        return report

    def run_forever(self) -> None:  # pragma: no cover - long running
        step = INTERVAL_MINUTES[self.interval] * 60
        while True:
            try:
                self.step()
            except Exception:
                log.exception("step failed")
            time.sleep(max(step - (time.time() % step) + 5, 1.0))


__all__ = ["BotRunner", "PortfolioBotRunner", "PaperBroker", "CCXTBroker", "target_exposure", "latest_price"]
