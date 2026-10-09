"""Figures, tables and key numbers for the results report (reports/ERGEBNISSE.md).

    python -m trading_bot.research.final_report

Reads the cached benchmark runs from reports/_scratch (zoo, own per-coin versions,
portfolio bots, fee sweep, 5m check, ML hit rates) and writes figures to
reports/figures and Markdown tables to reports/tables.
"""

from __future__ import annotations

import json
import pickle

import numpy as np
import pandas as pd

from ..metrics import daily_equity, deflated_sharpe, expected_max_sharpe, probabilistic_sharpe
from .benchmark import SCRATCH, merge_benchmarks, portfolio_curves, summarize
from .report import (FAMILY_DE, FIGURES, MUTED, REPORTS, SLOTS, fmt_num, fmt_pct, plot_equity, plot_heatmap,
                     plot_lines, plot_metric_bars, plot_risk_return, ranking_table, yearly_returns)

TABLES = REPORTS / "tables"
PERIOD_DE = {"is": "In-Sample 2017–2023", "oos": "Out-of-Sample 2024–2026", "full": "Gesamt 2017–2026"}


def _load(tag: str):
    path = SCRATCH / f"{tag}.pkl"
    if not path.exists():
        return None
    with open(path, "rb") as fh:
        return pickle.load(fh)


def family_table(summary: pd.DataFrame) -> pd.DataFrame:
    g = summary.groupby(["family", "interval"])["port_sharpe"].median().unstack("interval")
    g = g[[c for c in ("1d", "4h", "1h") if c in g.columns]]
    order = ["benchmark", "trend", "breakout", "mean_reversion", "bot", "ml", "ensemble"]
    g = g.reindex([o for o in order if o in g.index])
    g.index = [FAMILY_DE.get(i, i) for i in g.index]
    return g


def metrics_row(label: str, r: pd.Series) -> str:
    return (f"| {label} | {fmt_pct(r['port_cagr'])} | {fmt_num(r['port_sharpe'])} | {fmt_pct(r['port_maxdd'])} | "
            f"{fmt_num(r['port_calmar'])} | {r['exposure'] * 100:.0f} % |")


def comparison_table(rows: list[tuple[str, pd.Series]]) -> str:
    head = "| Bot | CAGR | Sharpe | Max. Drawdown | Calmar | Zeit im Markt |\n|---|---|---|---|---|---|"
    return head + "\n" + "\n".join(metrics_row(lbl, r) for lbl, r in rows)


def build(zoo_tags=("zoo_v1",), own_tag="own_final", portfolio_tag="portfolio_final",
          final_coin="trend_bot_v1", final_portfolio="rotation_bot_v1", versions=()) -> dict:
    FIGURES.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    tags = list(zoo_tags) + ([own_tag] if (SCRATCH / f"{own_tag}.pkl").exists() else [])
    results, curves = merge_benchmarks(*tags, out_tag="all")
    summ = {p: summarize(results, curves, p) for p in ("is", "oos", "full")}
    pf = _load(portfolio_tag)
    pf_rows = pf["rows"] if pf else pd.DataFrame()
    facts: dict = {}

    def combined(period: str) -> pd.DataFrame:
        s = summ[period]
        if pf_rows.empty:
            return s
        extra = pf_rows[(pf_rows["period"] == period) & (pf_rows["strategy"] != "pf_equal_weight")]
        return pd.concat([s, extra[s.columns.intersection(extra.columns)]], ignore_index=True)

    for p in ("is", "oos", "full"):
        combined(p).to_csv(REPORTS / f"summary_{p}.csv", index=False, float_format="%.5f")

    # ------------------------------------------------------------------ rankings
    zoo_mask = lambda s: ~s["strategy"].isin([v for v in versions if v != final_coin])  # noqa: E731
    for itv in ("1d", "4h", "1h"):
        for p in ("is", "oos"):
            sub = combined(p)
            sub = sub[(sub["interval"] == itv) & zoo_mask(sub)]
            plot_metric_bars(sub, "port_sharpe", FIGURES / f"sharpe_{p}_{itv}.png",
                             f"Sharpe Ratio aller Bots – {itv}, {PERIOD_DE[p]}",
                             "Portfolio über 20 Coins, nach Kosten (0,1 % Gebühr + 0,05 % Slippage pro Order)",
                             highlight=(final_coin, final_portfolio, "buy_hold"))
            plot_risk_return(sub, FIGURES / f"risk_return_{p}_{itv}.png",
                             f"Rendite vs. maximaler Drawdown – {itv}, {PERIOD_DE[p]}",
                             "Grau: alle nachgebauten Bots · farbig: eigene Bots und Buy & Hold",
                             highlight={final_portfolio: SLOTS[0], final_coin: SLOTS[2], "buy_hold": SLOTS[1]})
    plot_heatmap(family_table(summ["is"][zoo_mask(summ["is"])]), FIGURES / "family_heatmap_is.png",
                 "Median-Sharpe je Bot-Familie und Zeitebene", "In-Sample 2017–2023, Portfolio über 20 Coins")
    plot_heatmap(family_table(summ["oos"][zoo_mask(summ["oos"])]), FIGURES / "family_heatmap_oos.png",
                 "Median-Sharpe je Bot-Familie und Zeitebene", "Out-of-Sample 2024–2026, Portfolio über 20 Coins")

    appendix = ["# Anhang: vollständige Ranglisten\n",
                "Portfolio = alle 20 Coins gleich gewichtet (täglich rebalanciert); Portfolio-Bots verteilen ihr "
                "Kapital selbst. Kosten 0,1 % Gebühr + 0,05 % Slippage pro Order.\n"]
    for p in ("is", "oos"):
        for itv in ("1d", "4h", "1h"):
            sub = combined(p)
            appendix.append(f"\n## {PERIOD_DE[p]} – {itv}\n")
            appendix.append(ranking_table(sub[sub["interval"] == itv]))
    (REPORTS / "ANHANG_RANGLISTEN.md").write_text("\n".join(appendix) + "\n")

    # ------------------------------------------------------------------ flagship equity chart
    for itv in ("1d", "4h", "1h"):
        series = {}
        if pf and (final_portfolio, itv) in pf["curves"]:
            series[f"{final_portfolio}"] = pf["curves"][(final_portfolio, itv)][0]
        coin_curve, _ = portfolio_curves(curves, final_coin, itv, "full")
        if not coin_curve.empty:
            series[final_coin] = coin_curve
        bh, _ = portfolio_curves(curves, "buy_hold", itv, "full")
        series["Buy & Hold (20 Coins)"] = bh
        btc = [eq for (n, s, i), (eq, _) in curves.items() if n == "buy_hold" and s == "BTCUSDT" and i == itv]
        if btc:
            series["Buy & Hold BTC"] = btc[0].astype(float)
        best = summ["is"][(summ["is"]["interval"] == itv) & ~summ["is"]["family"].isin(["benchmark", "ensemble"])]
        if not best.empty:
            b = best.sort_values("port_sharpe", ascending=False).iloc[0]["strategy"]
            series[f"Bester Internet-Bot IS ({b})"], _ = portfolio_curves(curves, b, itv, "full")
        colors = {final_portfolio: SLOTS[0], final_coin: SLOTS[2], "Buy & Hold (20 Coins)": SLOTS[1],
                  "Buy & Hold BTC": MUTED}
        for k in series:
            if k.startswith("Bester"):
                colors[k] = SLOTS[6]
        plot_equity(series, FIGURES / f"equity_{itv}.png", f"Kapitalverlauf (log) – {itv}",
                    "Start = 1, nach Kosten · links der Linie: Entwicklung, rechts: unberührte Validierung",
                    colors=colors)

    # ------------------------------------------------------------------ significance
    all_is = combined("is")
    n_trials = int((all_is["family"] != "benchmark").sum())
    sr_std = float(all_is["port_sharpe"].std())
    facts.update({"n_trials": n_trials, "sr_std": sr_std, "expected_max_sr": expected_max_sharpe(n_trials, sr_std)})
    for name in (final_portfolio, final_coin):
        for itv in ("1d", "4h", "1h"):
            if name == final_portfolio and pf and (name, itv) in pf["curves"]:
                eq = pf["curves"][(name, itv)][0].astype(float)
                eq_is = eq[eq.index < pd.Timestamp("2024-01-01", tz="UTC")]
                eq_oos = eq[eq.index >= pd.Timestamp("2024-01-01", tz="UTC")]
            else:
                eq_is, _ = portfolio_curves(curves, name, itv, "is")
                eq_oos, _ = portfolio_curves(curves, name, itv, "oos")
            if len(eq_is) < 30:
                continue
            r_is = daily_equity(eq_is).pct_change().dropna()
            r_oos = daily_equity(eq_oos).pct_change().dropna()
            facts[f"{name}_{itv}_dsr_is"] = deflated_sharpe(r_is, n_trials, sr_std)
            facts[f"{name}_{itv}_psr_oos"] = probabilistic_sharpe(r_oos)
            facts[f"{name}_{itv}_years"] = {str(k): float(v) for k, v in yearly_returns(daily_equity(
                pd.concat([eq_is, eq_oos]))).items()}
    (REPORTS / "facts.json").write_text(json.dumps(facts, indent=2, default=float))
    return {"summ": summ, "combined": combined, "facts": facts, "curves": curves, "pf": pf}


__all__ = ["build", "family_table", "comparison_table", "metrics_row", "plot_lines", "np"]


def native_5m_table() -> str:
    """Freqtrade scalpers on their native 5m candles (6 coins, 2023-01..2026-10)."""
    blob = _load("native_5m")
    if blob is None:
        return ""
    from ..metrics import compute_metrics
    rows = blob["rows"]
    lines = ["| Bot | CAGR (Standard-Kosten) | Sharpe | Max. DD | CAGR (Maker+BNB 0,075 %) | Sharpe | "
             "Trefferquote | Trades/Jahr je Coin |", "|---|---|---|---|---|---|---|---|"]
    order = (rows[rows["costs"] == "standard"].groupby("strategy")["sharpe"].median()
             .sort_values(ascending=False).index)
    for name in order:
        cells = [f"`{name}`" if name != "buy_hold" else "**Buy & Hold**"]
        for costs in ("standard", "maker_bnb"):
            m = compute_metrics(blob["curves"][(costs, name)])
            cells += [fmt_pct(m["cagr"]), fmt_num(m["sharpe"])]
            if costs == "standard":
                cells.append(fmt_pct(m["max_drawdown"]))
        std = rows[(rows["costs"] == "standard") & (rows["strategy"] == name)]
        cells += [f"{std['win_rate'].mean() * 100:.0f} %" if name != "buy_hold" else "–",
                  f"{std['trades_per_year'].mean():.0f}" if name != "buy_hold" else "–"]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def ml_accuracy_table() -> str:
    df = _load("ml_accuracy")
    if df is None:
        return ""
    g = df.groupby(["model", "interval", "period"])["hit_rate"].mean().unstack(["interval", "period"])
    base = df.groupby(["interval", "period"])["majority_baseline"].mean()
    cols = [(i, p) for i in ("1d", "4h") for p in ("is", "oos") if (i, p) in g.columns]
    head = "| Modell | " + " | ".join(f"{i} {'IS' if p == 'is' else 'OOS'}" for i, p in cols) + " |"
    lines = [head, "|" + "---|" * (len(cols) + 1)]
    for model in g.index:
        lines.append(f"| `{model}` | " + " | ".join(f"{g.loc[model, c] * 100:.1f} %" for c in cols) + " |")
    lines.append("| *Immer die häufigere Richtung tippen* | " +
                 " | ".join(f"{base[c] * 100:.1f} %" for c in cols) + " |")
    return "\n".join(lines)


def fee_table() -> tuple[str, pd.DataFrame | None]:
    blob = _load("fee_sensitivity")
    if blob is None:
        return "", None
    df = blob if isinstance(blob, pd.DataFrame) else blob.get("rows")
    piv = df[df["period"] == "is"].pivot_table(index=["interval", "strategy"], columns="fee", values="port_sharpe")
    lines = ["| Zeitebene | Bot | " + " | ".join(f"{f * 100:.2f} %" for f in piv.columns) + " |",
             "|" + "---|" * (len(piv.columns) + 2)]
    for (itv, name), r in piv.iterrows():
        lines.append(f"| {itv} | `{name}` | " + " | ".join(fmt_num(v) for v in r.values) + " |")
    return "\n".join(lines), piv
