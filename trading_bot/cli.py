"""Command line interface: ``python -m trading_bot <command> ...``"""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from .backtest import Costs
from .data import DEFAULT_UNIVERSE, load_ohlcv


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
    print("\nAktuelle Zielgewichte:")
    w = res.weights.iloc[-1]
    for sym, val in w[w > 0.001].sort_values(ascending=False).items():
        print(f"  {sym:10s} {val:6.1%}")
    print(f"  Cash       {1 - w.sum():6.1%}")


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


def cmd_paper(args) -> None:
    from .live import BotRunner, CCXTBroker, PaperBroker, PortfolioBotRunner
    from .portfolio_strategies import PORTFOLIO_REGISTRY, get_portfolio_strategy
    from .strategies import get_strategy
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    is_portfolio = args.strategy in PORTFOLIO_REGISTRY
    strat = get_portfolio_strategy(args.strategy) if is_portfolio else get_strategy(args.strategy)
    if args.live:
        if not args.i_understand_the_risks:
            sys.exit("Echtgeld-Handel erfordert zusätzlich --i-understand-the-risks.")
        broker = CCXTBroker(args.exchange, testnet=args.testnet)
    else:
        broker = PaperBroker(name=args.name or f"paper_{strat.name}_{args.interval}",
                             starting_cash=args.capital, costs=_costs(args))
    if is_portfolio:
        runner = PortfolioBotRunner(strat, args.symbols, args.interval, broker)
    else:
        runner = BotRunner(strat, args.symbols, args.interval, broker, costs=_costs(args))
    if args.once:
        report = runner.step()
        for k, v in report.items():
            print(k, v)
    else:
        runner.run_forever()


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
    pf.add_argument("--strategy", default="trend_rotation_v1")
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
    pp.add_argument("--strategy", default="trend_bot_v1")
    pp.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    pp.add_argument("--interval", default="1d")
    pp.add_argument("--capital", type=float, default=10_000.0)
    pp.add_argument("--name", help="Name der Paper-Session (Zustandsdatei in state/)")
    pp.add_argument("--once", action="store_true", help="nur einen Entscheidungsschritt ausführen")
    pp.add_argument("--live", action="store_true", help="ECHTE Orders über ccxt senden")
    pp.add_argument("--i-understand-the-risks", action="store_true")
    pp.add_argument("--exchange", default="binance")
    pp.add_argument("--testnet", action="store_true", help="Exchange-Testnet benutzen (wenn verfügbar)")
    pp.set_defaults(func=cmd_paper)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
