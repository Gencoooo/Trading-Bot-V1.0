"""Command line interface: ``python -m trading_bot <command> ...``"""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from .backtest import Costs
from .data import DEFAULT_UNIVERSE, LIVE_UNIVERSE, load_ohlcv


def _costs(args) -> Costs:
    return Costs(fee=args.fee, slippage=args.slippage)


def cmd_fetch(args) -> None:
    for itv in args.intervals:
        for sym in args.symbols:
            df = load_ohlcv(sym, itv, update=True)
            print(f"{sym:10s} {itv:3s} {len(df):7d} Kerzen  {df.index[0]:%Y-%m-%d} -> {df.index[-1]:%Y-%m-%d %H:%M}")


def cmd_list(args) -> None:
    from .strategies import REGISTRY, load_all
    load_all()
    rows = []
    for name, make in REGISTRY.items():
        s = make()
        rows.append((s.family, name, s.native_timeframe or "-", s.source))
    for fam, name, tf, src in sorted(rows):
        print(f"{fam:15s} {name:24s} {tf:4s} {src}")


def cmd_backtest(args) -> None:
    from .metrics import compute_metrics
    from .research.benchmark import backtest_strategy
    from .strategies import get_strategy

    df = load_ohlcv(args.symbol, args.interval, update=args.update, start=args.start, end=args.end)
    strat = get_strategy(args.strategy)
    res = backtest_strategy(strat, df, args.interval, _costs(args), args.capital)
    bh = backtest_strategy(get_strategy("buy_hold"), df, args.interval, _costs(args), args.capital)
    m = compute_metrics(res.equity, res.exposure, res.trades, res.fees_paid)
    mb = compute_metrics(bh.equity)
    print(f"\n{strat.name} auf {args.symbol} {args.interval}  ({m['start']:%Y-%m-%d} -> {m['end']:%Y-%m-%d})")
    print(f"Quelle: {strat.source}\n")
    rows = [("Endkapital", f"{res.equity.iloc[-1]:,.2f}", f"{bh.equity.iloc[-1]:,.2f}"),
            ("Gesamtrendite", f"{m['total_return']:+.1%}", f"{mb['total_return']:+.1%}"),
            ("CAGR", f"{m['cagr']:+.1%}", f"{mb['cagr']:+.1%}"),
            ("Sharpe", f"{m['sharpe']:.2f}", f"{mb['sharpe']:.2f}"),
            ("Sortino", f"{m['sortino']:.2f}", f"{mb['sortino']:.2f}"),
            ("Max. Drawdown", f"{m['max_drawdown']:.1%}", f"{mb['max_drawdown']:.1%}"),
            ("Calmar", f"{m['calmar']:.2f}", f"{mb['calmar']:.2f}"),
            ("Zeit im Markt", f"{m['exposure']:.0%}", "100%"),
            ("Trades", f"{m['trades']}", "1"),
            ("Trefferquote", f"{m['win_rate']:.0%}" if m['trades'] else "-", "-"),
            ("Gebühren", f"{res.fees_paid:,.2f}", f"{bh.fees_paid:,.2f}")]
    print(f"{'':16s} {'Strategie':>14s} {'Buy & Hold':>14s}")
    for k, a, b in rows:
        print(f"{k:16s} {a:>14s} {b:>14s}")
    if args.trades and not res.trades.empty:
        print("\nLetzte Trades:")
        print(res.trades.tail(args.trades).to_string(index=False))


def cmd_portfolio(args) -> None:
    from .metrics import compute_metrics
    from .portfolio import load_panel
    from .portfolio_strategies import PORTFOLIO_REGISTRY, get_portfolio_strategy

    if args.strategy not in PORTFOLIO_REGISTRY:
        sys.exit(f"Unbekannte Portfolio-Strategie. Verfügbar: {', '.join(sorted(PORTFOLIO_REGISTRY))}")
    panel = load_panel(args.symbols, args.interval, update=args.update)
    res = get_portfolio_strategy(args.strategy).run(panel, args.interval, _costs(args), args.capital)
    ref = get_portfolio_strategy("pf_equal_weight").run(panel, args.interval, _costs(args), args.capital)
    print(f"\n{args.strategy} auf {len(panel)} Coins ({args.interval})\n")
    print(f"{'':16s} {'Strategie':>14s} {'Gleichgewicht':>14s}")
    for label, (start, end) in (("Gesamt", (None, None)), ("bis 2023", (None, "2024-01-01")),
                                ("ab 2024", ("2024-01-01", None))):
        m, mb = compute_metrics(res.equity, start=start, end=end), compute_metrics(ref.equity, start=start, end=end)
        print(f"-- {label}")
        for key, name, fmt in (("cagr", "CAGR", "{:+.1%}"), ("sharpe", "Sharpe", "{:.2f}"),
                               ("max_drawdown", "Max. Drawdown", "{:.1%}"), ("calmar", "Calmar", "{:.2f}")):
            print(f"{name:16s} {fmt.format(m[key]):>14s} {fmt.format(mb[key]):>14s}")
    # the last decision's targets, i.e. what paper/live trading holds right after its rebalance
    # (res.weights are the held weights, which have drifted with prices since then)
    decisions = get_portfolio_strategy(args.strategy).weights(panel, args.interval).dropna(how="all")
    w = decisions.iloc[-1].fillna(0.0).clip(lower=0.0)
    w = w / max(1.0, w.sum())
    print(f"\nAktuelle Zielgewichte (Entscheidung zum Schluss der Kerze vom {decisions.index[-1]:%d.%m.%Y}):")
    for sym, val in w[w > 0.001].sort_values(ascending=False).items():
        print(f"  {sym:10s} {val:6.1%}")
    print(f"  Cash       {max(0.0, 1 - w.sum()):6.1%}")


def cmd_benchmark(args) -> None:
    from .research.benchmark import run_benchmark, summarize
    from .strategies import list_strategies
    names = args.strategies or list_strategies()
    results, curves = run_benchmark(names, args.symbols, args.intervals, _costs(args), args.jobs, args.tag)
    pd.set_option("display.width", 200)
    for period in ("is", "oos"):
        summ = summarize(results, curves, period)
        print(f"\n=== {period.upper()} ===")
        cols = ["strategy", "interval", "port_cagr", "port_sharpe", "port_maxdd", "beat_bh_sharpe", "trades_per_year"]
        print(summ[cols].head(args.top).to_string(index=False, float_format=lambda v: f"{v:.3f}"))


def cmd_report(args) -> None:
    from .research.report import build_report
    path = build_report(args.tag)
    print(f"Report geschrieben: {path}")


def _paper_name(args, strat) -> str:
    return args.name or f"paper_{strat.name}_{args.interval}"


def cmd_paper(args) -> None:
    from .live import (STATE_DIR, BotRunner, CCXTBroker, PaperBroker, PortfolioBotRunner, next_close_text,
                       next_rebalance_text)
    from .portfolio_strategies import PORTFOLIO_REGISTRY, get_portfolio_strategy
    from .strategies import get_strategy
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%d.%m.%Y %H:%M:%S")
    is_portfolio = args.strategy in PORTFOLIO_REGISTRY
    strat = get_portfolio_strategy(args.strategy) if is_portfolio else get_strategy(args.strategy)
    quote = args.quote.upper()
    if args.symbols is None:
        bases = [s[:-4] for s in LIVE_UNIVERSE] if is_portfolio else ["BTC", "ETH"]
        args.symbols = [b + quote for b in bases]
    if args.live:
        if not args.i_understand_the_risks:
            sys.exit("Echtgeld-Handel erfordert zusätzlich --i-understand-the-risks.")
        broker = CCXTBroker(args.exchange, testnet=args.testnet, quote=quote)
        name = args.name or f"{'testnet' if args.testnet else 'live'}_{strat.name}_{args.interval}"
        mode = "TESTNET (Spielgeld an der Börse)" if args.testnet else "LIVE – ECHTES GELD"
    else:
        name = _paper_name(args, strat)
        if args.reset:
            for f in (STATE_DIR / f"{name}.json", STATE_DIR / f"{name}.runner.json"):
                if f.exists():
                    f.unlink()
            print(f"Paper-Konto '{name}' zurückgesetzt.")
        broker = PaperBroker(name=name, starting_cash=args.capital, costs=_costs(args), quote=quote)
        mode = f"PAPER (simuliert, Zustand in state/{name}.json)"
    if is_portfolio:
        runner = PortfolioBotRunner(strat, args.symbols, args.interval, broker, max_capital=args.max_capital,
                                    state_path=STATE_DIR / f"{name}.runner.json")
    else:
        runner = BotRunner(strat, args.symbols, args.interval, broker, costs=_costs(args),
                           max_capital=args.max_capital)
    print("=" * 72)
    print(f" Modus:      {mode}")
    print(f" Strategie:  {strat.name}  ({'Portfolio' if is_portfolio else 'je Coin'})")
    print(f" Zeitebene:  {args.interval}   Coins ({len(args.symbols)}): {', '.join(args.symbols)}")
    if args.max_capital:
        print(f" Budget:     höchstens {args.max_capital:,.2f} {quote}")
    print(f" Nächste Prüfung:      {next_close_text(args.interval)}")
    rebalance = next_rebalance_text(strat, args.interval) if is_portfolio else None
    if rebalance:
        print(f" Nächste Umschichtung: {rebalance}")
    print("=" * 72)
    if args.once:
        report = runner.step()
        print(f"Kontowert: {report['_equity']:,.2f} {quote}"
              + ("" if report.get("_rebalanced", True) else "  (heute kein Umschichtungstermin, keine Orders)"))
        if not args.live:
            print("Details: python -m trading_bot status")
    else:
        runner.run_forever()


def cmd_status(args) -> None:
    """Show the state of a paper-trading account."""
    import json

    from .live import STATE_DIR, latest_price
    files = sorted(f for f in STATE_DIR.glob("*.json") if not f.name.endswith(".runner.json")) \
        if STATE_DIR.exists() else []
    if args.name is None:
        if not files:
            sys.exit("Noch kein Paper-Konto vorhanden. Starte zuerst: python -m trading_bot paper ...")
        if len(files) > 1:
            print("Vorhandene Paper-Konten:", ", ".join(f.stem for f in files))
        path = max(files, key=lambda f: f.stat().st_mtime)
    else:
        path = STATE_DIR / f"{args.name}.json"
        if not path.exists():
            sys.exit(f"Kein Paper-Konto '{args.name}' in {STATE_DIR}.")
    state = json.loads(path.read_text())
    quote = state.get("quote", "USDT")
    bal = state.get("balances", {})
    rows, total = [], max(bal.get(quote, 0.0), 0.0)
    for asset, qty in bal.items():
        if asset == quote or qty <= 1e-12:
            continue
        try:
            px = latest_price(f"{asset}{quote}")
        except RuntimeError:
            px = float("nan")
        rows.append((asset, qty, px, qty * px))
        total += qty * px if px == px else 0.0
    equity = state.get("equity", [])
    start = state.get("start_capital") or (equity[0]["equity"] if equity else None)
    print(f"Paper-Konto: {path.stem}")
    print(f"Aktueller Wert: {total:,.2f} {quote}", end="")
    if start:
        print(f"   (Start {start:,.2f} {quote}, Veränderung {total / start - 1:+.2%})")
    else:
        print()
    print(f"\n{'Coin':8s} {'Menge':>16s} {'Preis':>14s} {'Wert ' + quote:>14s} {'Anteil':>8s}")
    for asset, qty, px, val in sorted(rows, key=lambda r: -r[3]):
        print(f"{asset:8s} {qty:16.6f} {px:14.6g} {val:14,.2f} {val / total:8.1%}")
    cash = max(bal.get(quote, 0.0), 0.0)
    print(f"{quote:8s} {cash:16.2f} {'':14s} {cash:14,.2f} {cash / total if total else 0:8.1%}")
    trades = state.get("trades", [])
    if trades:
        print(f"\nLetzte Trades (insgesamt {len(trades)}):")
        for t in trades[-args.trades:]:
            side = "Kauf   " if t["side"] == "buy" else "Verkauf"
            print(f"  {t['time'][:16].replace('T', ' ')} UTC  {side} {t['qty']:.6g} {t['symbol']} zu {t['price']:.6g}")
    if len(equity) > 1:
        print(f"\nWertverlauf: {len(equity)} Einträge seit {equity[0]['time'][:10]}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="trading_bot", description="Trading-Bot-V1.0 - Backtests, Benchmark, Paper/Live")
    p.add_argument("--fee", type=float, default=0.001, help="Gebühr pro Order (Standard 0.001 = 0.1 %%)")
    p.add_argument("--slippage", type=float, default=0.0005, help="Slippage pro Order (Standard 0.0005)")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="Marktdaten von Binance laden/aktualisieren")
    f.add_argument("--symbols", nargs="+", default=list(DEFAULT_UNIVERSE))
    f.add_argument("--intervals", nargs="+", default=["1d", "4h", "1h"])
    f.set_defaults(func=cmd_fetch)

    sub.add_parser("list", help="Alle Strategien anzeigen").set_defaults(func=cmd_list)

    b = sub.add_parser("backtest", help="Eine Strategie auf einem Markt testen")
    b.add_argument("--strategy", default="trend_bot_v1")
    b.add_argument("--symbol", default="BTCUSDT")
    b.add_argument("--interval", default="1d")
    b.add_argument("--start")
    b.add_argument("--end")
    b.add_argument("--capital", type=float, default=10_000.0)
    b.add_argument("--update", action="store_true", help="vorher neue Kerzen laden")
    b.add_argument("--trades", type=int, default=0, help="die letzten N Trades anzeigen")
    b.set_defaults(func=cmd_backtest)

    pf = sub.add_parser("portfolio", help="Portfolio-Strategie (Kapital zwischen Coins verteilt) testen")
    pf.add_argument("--strategy", default="rotation_bot_v1")
    pf.add_argument("--symbols", nargs="+", default=list(DEFAULT_UNIVERSE))
    pf.add_argument("--interval", default="1d")
    pf.add_argument("--capital", type=float, default=10_000.0)
    pf.add_argument("--update", action="store_true", help="vorher neue Kerzen laden")
    pf.set_defaults(func=cmd_portfolio)

    bm = sub.add_parser("benchmark", help="Viele Strategien über viele Märkte vergleichen")
    bm.add_argument("--strategies", nargs="+")
    bm.add_argument("--symbols", nargs="+", default=list(DEFAULT_UNIVERSE))
    bm.add_argument("--intervals", nargs="+", default=["1d", "4h", "1h"])
    bm.add_argument("--jobs", type=int, default=4)
    bm.add_argument("--tag", default="benchmark")
    bm.add_argument("--top", type=int, default=20)
    bm.set_defaults(func=cmd_benchmark)

    r = sub.add_parser("report", help="Markdown-Report aus einem Benchmark erzeugen")
    r.add_argument("--tag", default="benchmark")
    r.set_defaults(func=cmd_report)

    pp = sub.add_parser("paper", help="Paper-Trading (Standard) oder Live-Trading starten")
    pp.add_argument("--strategy", default="rotation_bot_v1")
    pp.add_argument("--symbols", nargs="+", default=None,
                    help="Standard: alle handelbaren Coins (Portfolio-Bots) bzw. BTC+ETH (Einzel-Coin-Bots)")
    pp.add_argument("--interval", default="1d")
    pp.add_argument("--capital", type=float, default=10_000.0)
    pp.add_argument("--name", help="Name der Paper-Session (Zustandsdatei in state/)")
    pp.add_argument("--once", action="store_true", help="nur einen Entscheidungsschritt ausführen")
    pp.add_argument("--live", action="store_true", help="ECHTE Orders über ccxt senden")
    pp.add_argument("--i-understand-the-risks", action="store_true")
    pp.add_argument("--exchange", default="binance")
    pp.add_argument("--testnet", action="store_true", help="Exchange-Testnet benutzen (wenn verfügbar)")
    pp.add_argument("--max-capital", type=float, default=None,
                    help="höchstens so viele USDT verwalten (der Rest des Kontos bleibt unberührt)")
    pp.add_argument("--reset", action="store_true", help="Paper-Konto vor dem Start zurücksetzen")
    pp.add_argument("--quote", default="USDT",
                    help="Quote-Währung der Handelspaare, z. B. USDC für EU-Konten (Standard: USDT)")
    pp.set_defaults(func=cmd_paper)

    st = sub.add_parser("status", help="Stand eines Paper-Kontos anzeigen")
    st.add_argument("--name", help="Name des Paper-Kontos (Standard: zuletzt benutztes)")
    st.add_argument("--trades", type=int, default=10, help="Anzahl der angezeigten Trades")
    st.set_defaults(func=cmd_status)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
