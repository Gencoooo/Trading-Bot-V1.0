"""Markdown tables for the results report, generated from the cached benchmark runs.

    python -m trading_bot.research.tables      -> reports/tables/*.md
"""

from __future__ import annotations

import pickle

import pandas as pd

from ..metrics import compute_metrics, daily_equity
from .benchmark import OOS_START, SCRATCH, load_benchmark, portfolio_curves, summarize
from .final_report import evolution_table, fee_table, ml_accuracy_table, native_5m_table
from .report import FAMILY_DE, INACTIVE_EXPOSURE, REPORTS, fmt_num, fmt_pct, yearly_returns

TABLES = REPORTS / "tables"
OWN_VERSIONS = ["buy_hold", "own_v01_all_bots", "own_v02_follow_best", "own_v03_slow_trend", "own_v04_vol_target",
                "own_v05_fast_trend", "trend_bot_v1"]
PF_VERSIONS = ["pf_equal_weight", "pf_xs_momentum_30d_top5", "rotation_v0_plain", "rotation_bot_v1"]


def _row(label, m, expo=None) -> str:
    return (f"| {label} | {fmt_pct(m['cagr'])} | {fmt_num(m['sharpe'])} | {fmt_pct(m['max_drawdown'])} | "
            f"{fmt_num(m['calmar'])} | {'–' if expo is None else f'{expo * 100:.0f} %'} |")


def headline(zoo_res, zoo_curves, own_curves, pf) -> str:
    out = []
    for itv in ("1d", "4h", "1h"):
        out.append(f"\n**Zeitebene {itv}**\n")
        out.append("| Bot | CAGR | Sharpe | Max. Drawdown | Calmar | Zeit im Markt |\n|---|---|---|---|---|---|")
        for period in ("oos", "is"):
            start, end = (OOS_START, None) if period == "oos" else (None, OOS_START)
            tag = "OOS 2024–26" if period == "oos" else "IS 2017–23"
            eq = pf["curves"][("rotation_bot_v1", itv)][0].astype(float)
            ex = pf["curves"][("rotation_bot_v1", itv)][1].astype(float)
            sl = (eq.index >= pd.Timestamp(start, tz="UTC")) if start else (eq.index < pd.Timestamp(end, tz="UTC"))
            out.append(_row(f"**rotation_bot_v1** ({tag})", compute_metrics(eq[sl]), float(ex[sl].mean())))
            c, e = portfolio_curves(own_curves, "trend_bot_v1", itv, period)
            out.append(_row(f"**trend_bot_v1** ({tag})", compute_metrics(c), float(e.mean())))
            s = summarize(zoo_res, zoo_curves, period)
            s = s[(s["interval"] == itv) & (s["exposure"] >= INACTIVE_EXPOSURE) & (s["family"] != "benchmark")]
            best = s.sort_values("port_sharpe", ascending=False).iloc[0]
            c, e = portfolio_curves(zoo_curves, best["strategy"], itv, period)
            out.append(_row(f"Bester Internet-Bot {tag}: `{best['strategy']}`", compute_metrics(c), float(e.mean())))
            c, e = portfolio_curves(zoo_curves, "buy_hold", itv, period)
            out.append(_row(f"Buy & Hold, 20 Coins gleich gewichtet ({tag})", compute_metrics(c), 1.0))
            btc = [eq for (n, sym, i), (eq, _) in zoo_curves.items() if n == "buy_hold" and sym == "BTCUSDT" and i == itv]
            b = btc[0].astype(float)
            b = b[b.index >= pd.Timestamp(start, tz="UTC")] if start else b[b.index < pd.Timestamp(end, tz="UTC")]
            out.append(_row(f"Buy & Hold nur Bitcoin ({tag})", compute_metrics(b), 1.0))
    return "\n".join(out)


def zoo_top_bottom(zoo_res, zoo_curves, period="is", top=10, bottom=5) -> str:
    s = summarize(zoo_res, zoo_curves, period)
    parts = []
    for itv in ("1d", "4h", "1h"):
        sub = s[(s["interval"] == itv) & (s["exposure"] >= INACTIVE_EXPOSURE)].sort_values("port_sharpe",
                                                                                          ascending=False)
        bh = s[(s["interval"] == itv) & (s["strategy"] == "buy_hold")].iloc[0]
        parts.append(f"\n**{itv}** – Buy & Hold: Sharpe {fmt_num(bh['port_sharpe'])}, CAGR {fmt_pct(bh['port_cagr'])}, "
                     f"Max. DD {fmt_pct(bh['port_maxdd'])}\n")
        parts.append("| Rang | Bot | Familie | Sharpe | CAGR | Max. DD | Trades/Jahr je Coin |\n|---|---|---|---|---|---|---|")
        rows = list(sub.head(top).iterrows()) + [(None, None)] + list(sub.tail(bottom).iterrows())
        for k, (_, r) in enumerate(rows, 1):
            if r is None:
                parts.append("| … | | | | | | |")
                continue
            rank = k if k <= top else len(sub) - (len(rows) - k)
            parts.append(f"| {rank} | `{r['strategy']}` | {FAMILY_DE.get(r['family'], r['family'])} | "
                         f"{fmt_num(r['port_sharpe'])} | {fmt_pct(r['port_cagr'])} | {fmt_pct(r['port_maxdd'])} | "
                         f"{r['trades_per_year']:.0f} |")
    return "\n".join(parts)


def yearly_table(zoo_curves, own_curves, pf, itv="1d") -> str:
    series = {
        "rotation_bot_v1": pf["curves"][("rotation_bot_v1", itv)][0].astype(float),
        "trend_bot_v1": portfolio_curves(own_curves, "trend_bot_v1", itv, "full")[0],
        "Buy & Hold 20 Coins": portfolio_curves(zoo_curves, "buy_hold", itv, "full")[0],
        "Buy & Hold BTC": [eq for (n, s, i), (eq, _) in zoo_curves.items()
                           if n == "buy_hold" and s == "BTCUSDT" and i == itv][0].astype(float),
    }
    yr = pd.DataFrame({k: yearly_returns(daily_equity(v)) for k, v in series.items()})
    lines = ["| Jahr | " + " | ".join(yr.columns) + " |", "|---" * (len(yr.columns) + 1) + "|"]
    for year, r in yr.iterrows():
        flag = " (OOS)" if year >= 2024 else ""
        lines.append(f"| {year}{flag} | " + " | ".join(fmt_pct(v, 0) for v in r.values) + " |")
    return "\n".join(lines)


def main() -> dict:
    TABLES.mkdir(parents=True, exist_ok=True)
    zoo_res, zoo_curves = load_benchmark("zoo_v1")
    own_res, own_curves = load_benchmark("own_final")
    with open(SCRATCH / "portfolio_final.pkl", "rb") as fh:
        pf = pickle.load(fh)
    own_sum = pd.concat([summarize(own_res, own_curves, p).assign(period=p) for p in ("is", "oos")])
    pf_rows = pf["rows"]
    tables = {
        "headline": headline(zoo_res, zoo_curves, own_curves, pf),
        "zoo_is": zoo_top_bottom(zoo_res, zoo_curves, "is"),
        "zoo_oos": zoo_top_bottom(zoo_res, zoo_curves, "oos"),
        "evolution_coin": evolution_table(own_sum, OWN_VERSIONS),
        "evolution_portfolio": evolution_table(pf_rows, PF_VERSIONS),
        "yearly_1d": yearly_table(zoo_curves, own_curves, pf, "1d"),
        "native_5m": native_5m_table(),
        "ml_accuracy": ml_accuracy_table(),
        "fees": fee_table()[0],
    }
    for name, md in tables.items():
        (TABLES / f"{name}.md").write_text(md + "\n")
    sig = SCRATCH / "significance.json"
    if sig.exists():
        (REPORTS / "significance.json").write_text(sig.read_text())
    return tables


if __name__ == "__main__":
    for k, v in main().items():
        print(f"\n######## {k}\n{v}")


__all__ = ["main"]
