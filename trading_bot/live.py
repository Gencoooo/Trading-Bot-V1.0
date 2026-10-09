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
    quote: str = "USDT"

    def __post_init__(self):
        self.path = STATE_DIR / f"{self.name}.json"
        if self.path.exists():
            self.state = json.loads(self.path.read_text())
            self.quote = self.state.get("quote", self.quote)
        else:
            self.state = {"quote": self.quote, "start_capital": self.starting_cash,
                          "created": datetime.now(timezone.utc).isoformat(),
                          "balances": {self.quote: self.starting_cash}, "trades": [], "equity": []}
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
            bal[self.quote] = max(bal.get(self.quote, 0.0) - cost, 0.0)  # cost is capped to the cash above
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

    def __init__(self, exchange: str = "binance", testnet: bool = False, quote: str = "USDT"):
        self.quote = quote
        try:
            import ccxt
        except ImportError as exc:  # pragma: no cover
            raise SystemExit("Für Live-Trading wird ccxt benötigt: pip install ccxt") from exc
        key, secret = os.environ.get("TB_API_KEY"), os.environ.get("TB_API_SECRET")
        if not key or not secret:
            raise SystemExit("Bitte zuerst die Umgebungsvariablen TB_API_KEY und TB_API_SECRET setzen "
                             "(siehe ANLEITUNG.md, Teil 4).")
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
def _prices(broker: Broker, symbols: list[str]) -> dict[str, float]:
    """Current prices; symbols the exchange does not offer (e.g. on a testnet) are skipped."""
    out = {}
    for sym in symbols:
        try:
            out[sym] = broker.price(sym)
        except Exception as exc:  # unknown market, delisted, network hiccup
            log.warning("%s: kein Preis verfügbar (%s) - wird diesmal übersprungen", sym, exc)
    return out

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
    max_capital: float | None = None   # manage at most this much quote currency (USDT)

    def portfolio_value(self, prices: dict[str, float]) -> float:
        bal = self.broker.balances()
        value = bal.get(self.broker.quote, 0.0)
        for s, px in prices.items():
            value += bal.get(self.broker.base_asset(s), 0.0) * px
        return value

    def step(self) -> dict:
        """One decision cycle over all symbols (call after each candle close)."""
        prices = _prices(self.broker, self.symbols)
        total = self.portfolio_value(prices)
        if self.max_capital is not None:
            total = min(total, self.max_capital)
        sleeve = total / max(len(prices), 1)  # equal-weight sleeves, like the backtests
        report = {}
        start = pd.Timestamp.now(tz="UTC") - interval_to_timedelta(self.interval) * (self.history_bars + 2)
        for s in prices:
            df = fetch_klines(s, self.interval, start=start)
            if len(df) < 300:
                log.warning("%s: not enough history (%d bars)", s, len(df))
                continue
            want = max(0.0, min(1.0, target_exposure(self.strategy, df, self.interval, prices[s], self.costs)))
            held = self.broker.balances().get(self.broker.base_asset(s), 0.0)
            cur = held * prices[s] / sleeve if sleeve > 0 else 0.0
            delta_value = (want - cur) * sleeve
            action = "halten"
            if abs(want - cur) >= self.rebalance_band or (want == 0.0 and held > 0):
                qty = abs(delta_value) / prices[s]
                if abs(delta_value) >= self.min_order_value:
                    side = "buy" if delta_value > 0 else "sell"
                    if side == "sell" and want == 0.0:
                        qty = held
                    fill = self.broker.market_order(s, side, qty) or {}
                    filled = float(fill.get("qty", fill.get("filled", qty)) or qty)
                    action = f"{'Kauf' if side == 'buy' else 'Verkauf'} {filled:.6g}"
            report[s] = {"price": prices[s], "target": round(want, 3), "current": round(cur, 3), "action": action}
            log.info("%s Preis=%.6g Ziel=%.0f%% aktuell=%.0f%% -> %s", s, prices[s], want * 100, cur * 100, action)
        value = self.portfolio_value(prices)
        if isinstance(self.broker, PaperBroker):
            self.broker.record_equity(value)
        report["_equity"] = value
        return report

    def seconds_to_next_close(self) -> float:
        return seconds_to_next_close(self.interval)

    def run_forever(self) -> None:  # pragma: no cover - long running
        log.info("Bot %s gestartet: %s (%s)", self.strategy.name, ", ".join(self.symbols), self.interval)
        while True:
            try:
                report = self.step()
                log.info("Kontowert: %.2f %s", report["_equity"], self.broker.quote)
            except Exception:  # keep running through transient API errors
                log.exception("Schritt fehlgeschlagen - nächster Versuch zur nächsten Kerze")
            wait = seconds_to_next_close(self.interval)
            log.info("Nächste Entscheidung %s (in %s). Beenden mit Strg+C.", next_close_text(self.interval),
                     _duration(wait))
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
    max_capital: float | None = None   # manage at most this much quote currency (USDT)
    state_path: Path | None = None     # remembers the last executed decision

    def _last_applied(self) -> pd.Timestamp | None:
        if self.state_path is None or not self.state_path.exists():
            return None
        value = json.loads(self.state_path.read_text()).get("last_decision")
        return pd.Timestamp(value) if value else None

    def _mark_applied(self, ts: pd.Timestamp) -> None:
        if self.state_path is not None:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps({"last_decision": ts.isoformat()}))

    def target_weights(self, initial_sync: bool = False) -> dict[str, float] | None:
        """Weights of the most recent rebalancing decision that has not been executed yet.
        Missed runs are caught up: if the bot was offline on a rebalancing day, the decision
        is executed on the next run. ``initial_sync`` adopts the latest decision even without
        a stored state (fresh account)."""
        self._pending_decision = None
        now = pd.Timestamp.now(tz="UTC")
        step = interval_to_timedelta(self.interval)
        start = now - step * (self.history_bars + 2)
        panel = {s: fetch_klines(s, self.interval, start=start) for s in self.symbols}
        # skip coins without enough history or whose data stopped (delisted / halted)
        panel = {s: df for s, df in panel.items() if len(df) > 300 and df.index[-1] >= now - 3 * step}
        if not panel:
            log.warning("no symbol with fresh data - skipping this cycle")
            return None
        w = self.strategy.weights(panel, self.interval)
        decided = w.dropna(how="all")
        if decided.empty:
            return None
        ts, row = decided.index[-1], decided.iloc[-1]
        last = self._last_applied()
        fresh = last is None or ts > last
        if not (fresh and (last is not None or initial_sync or ts == w.index[-1])):
            return None  # nothing new to execute
        self._pending_decision = ts
        row = row.fillna(0.0).clip(lower=0.0)
        if row.sum() > 1.0:
            row = row / row.sum()
        return {s: float(row.get(s, 0.0)) for s in self.symbols}

    def step(self) -> dict:
        prices = _prices(self.broker, self.symbols)
        tradable = list(prices)
        bal = self.broker.balances()
        holdings = {s: bal.get(self.broker.base_asset(s), 0.0) * prices[s] for s in tradable}
        account = bal.get(self.broker.quote, 0.0) + sum(holdings.values())
        total = min(account, self.max_capital) if self.max_capital is not None else account
        target = self.target_weights(initial_sync=self._last_applied() is None)
        report = {"_equity": account, "_rebalanced": target is not None}
        if isinstance(self.broker, PaperBroker):
            self.broker.record_equity(account)
        if target is None or total <= 0:
            log.info("Kein neuer Umschichtungstermin - Positionen bleiben unverändert.")
            return report
        band = getattr(self.strategy, "band", 0.02)
        deltas = {s: target.get(s, 0.0) - holdings[s] / total for s in tradable}
        for s in sorted(tradable, key=lambda k: deltas[k]):  # sells first, then buys
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
            fill = self.broker.market_order(s, side, qty) or {}
            filled = float(fill.get("qty", fill.get("filled", qty)) or qty)
            report[s] = {"target": round(target[s], 3), "was": round(holdings[s] / total, 3), "action": side}
            log.info("%s Ziel=%.1f%% vorher=%.1f%% -> %s %.6g", s, target[s] * 100, holdings[s] / total * 100,
                     "Kauf" if side == "buy" else "Verkauf", filled)
        if self._pending_decision is not None:
            self._mark_applied(self._pending_decision)
        return report

    def run_forever(self) -> None:  # pragma: no cover - long running
        log.info("Portfolio-Bot %s gestartet: %d Coins (%s)", getattr(self.strategy, "name", "?"),
                 len(self.symbols), self.interval)
        while True:
            try:
                report = self.step()
                log.info("Kontowert: %.2f %s", report["_equity"], self.broker.quote)
            except Exception:
                log.exception("Schritt fehlgeschlagen - nächster Versuch zur nächsten Kerze")
            wait = seconds_to_next_close(self.interval)
            log.info("Nächste Prüfung %s (in %s). Beenden mit Strg+C.", next_close_text(self.interval),
                     _duration(wait))
            time.sleep(max(wait, 1.0))


def seconds_to_next_close(interval: str, delay: float = 10.0) -> float:
    """Seconds until a few seconds after the next candle close (candles are aligned to UTC)."""
    step = INTERVAL_MINUTES[interval] * 60
    return step - (time.time() % step) + delay


def next_close(interval: str) -> pd.Timestamp:
    """Close time of the candle that is currently forming (UTC)."""
    step = interval_to_timedelta(interval)
    return pd.Timestamp.now(tz="UTC").floor(step) + step


def _when(ts: pd.Timestamp) -> str:
    local = ts.tz_convert(datetime.now().astimezone().tzinfo)
    days = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    return f"{days[local.dayofweek]}, {local:%d.%m.%Y um %H:%M} Uhr Ortszeit ({ts:%H:%M} UTC)"


def next_close_text(interval: str) -> str:
    return _when(next_close(interval))


def next_rebalance_text(strategy, interval: str) -> str | None:
    """When a calendar-scheduled portfolio strategy trades next (None if not scheduled)."""
    days = getattr(strategy, "rebalance_days", None)
    if not days:
        return None
    from .portfolio_strategies import _rebalance_mask
    step = interval_to_timedelta(interval)
    first_open = next_close(interval) - step
    opens = pd.date_range(first_open, periods=int(days * 1440 / INTERVAL_MINUTES[interval]) + 2, freq=step)
    hit = opens[_rebalance_mask(opens, interval, days)]
    return _when(hit[0] + step) if len(hit) else None


def _duration(seconds: float) -> str:
    h, m = divmod(int(seconds) // 60, 60)
    return f"{h} h {m} min" if h else f"{m} min"


__all__ = ["BotRunner", "PortfolioBotRunner", "PaperBroker", "CCXTBroker", "target_exposure", "latest_price",
           "next_close_text", "next_rebalance_text"]
