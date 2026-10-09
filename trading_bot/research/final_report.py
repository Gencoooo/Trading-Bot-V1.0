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
from .report import (FAMILY_DE, FIGURES, MUTED, REPORTS, SLOTS, _de, fmt_num, fmt_pct, plot_equity, plot_heatmap,
                     plot_metric_bars, plot_risk_return, ranking_table)

TABLES = REPORTS / "tables"
PERIOD_DE = {"is": "In-Sample 2017–2023", "oos": "Out-of-Sample 2024–2026", "full": "Gesamt 2017–2026"}


def _load(tag: str):
    path = SCRATCH / f"{tag}.pkl"
    if not path.exists():
        return None
    with open(path, "rb") as fh:
        return pickle.load(fh)


def family_table(summary: pd.DataFrame, own: tuple[str, ...] = ()) -> pd.DataFrame:
    """Median Sharpe per bot family (zoo only) plus one row per own bot."""
    zoo = summary[summary["family"] != "ensemble"]
    g = zoo.groupby(["family", "interval"])["port_sharpe"].median().unstack("interval")
    order = ["benchmark", "trend", "breakout", "mean_reversion", "bot", "ml"]
    g = g.reindex([o for o in order if o in g.index])
    g.index = [FAMILY_DE.get(i, i) for i in g.index]
    for name in own:
        row = summary[summary["strategy"] == name].set_index("interval")["port_sharpe"]
        if not row.empty:
            g.loc[f"Eigener Bot: {name}"] = row
    return g[[c for c in ("1d", "4h", "1h") if c in g.columns]]


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
    results, curves = merge_benchmarks(*tags)
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
                             "Portfolio über 20 Coins, nach Kosten (0,1 % Gebühr + 0,05 % Slippage pro Order); "
                             "Bots mit < 2 % Zeit im Markt ausgeblendet",
                             highlight=(final_coin, final_portfolio, "buy_hold"))
            plot_risk_return(sub, FIGURES / f"risk_return_{p}_{itv}.png",
                             f"Rendite vs. maximaler Drawdown – {itv}, {PERIOD_DE[p]}",
                             "Grau: alle nachgebauten Bots · farbig: eigene Bots und Buy & Hold",
                             highlight={final_portfolio: SLOTS[0], final_coin: SLOTS[2], "buy_hold": SLOTS[1]})
    for p in ("is", "oos"):
        tab = family_table(combined(p), own=(final_portfolio, final_coin))
        tab.to_csv(TABLES / f"family_{p}.csv", float_format="%.3f")
        plot_heatmap(tab, FIGURES / f"family_heatmap_{p}.png", "Sharpe je Bot-Familie (Median) und Zeitebene",
                     f"{PERIOD_DE[p]}, Portfolio über 20 Coins · Farbskala bei ±2 gekappt", limit=2.0)

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
    facts.update(significance(curves, pf, final_coin, final_portfolio))
    (REPORTS / "significance.json").write_text(json.dumps(facts, indent=2, default=float))
    return {"summ": summ, "combined": combined, "facts": facts, "curves": curves, "pf": pf}


__all__ = ["build", "family_table", "comparison_table", "metrics_row", "evolution_table",
           "native_5m_table", "ml_accuracy_table", "fee_table", "VERSION_LABELS"]


def significance(curves: dict, pf: dict | None, final_coin: str, final_portfolio: str,
                 explore_tags=("explore_v1", "explore_v2"), explore_portfolio_tag="explore_portfolio") -> dict:
    """Deflated Sharpe of the in-sample result against two trial sets (our own 43 design
    variants; those plus every zoo bot on 1d) and the out-of-sample PSR."""
    own = []
    for tag in explore_tags:
        blob = _load(tag)
        if blob is None:
            continue
        s = summarize(blob["results"], blob["curves"], "is")
        own += list(s[s["strategy"] != "buy_hold"].groupby("strategy")["port_sharpe"].mean().values)
    blob = _load(explore_portfolio_tag)
    if blob is not None:
        r = blob["rows"]
        r = r[(r["period"] == "is") & r["strategy"].str.startswith("x_")]
        own += list(r.groupby("strategy")["port_sharpe"].mean().values)
    own = np.array(own)
    zoo = _load("zoo_v1")
    zoo_1d = np.array([])
    if zoo is not None:
        zs = summarize(zoo["results"], zoo["curves"], "is")
        zoo_1d = zs[(zs["interval"] == "1d") & (zs["strategy"] != "buy_hold")]["port_sharpe"].values
    every = np.concatenate([zoo_1d, own])
    out = {"n_own": len(own), "std_own": float(own.std(ddof=1)) if len(own) > 1 else np.nan,
           "n_all": len(every), "std_all": float(every.std(ddof=1)) if len(every) > 1 else np.nan}
    out["emax_own"] = expected_max_sharpe(out["n_own"], out["std_own"])
    out["emax_all"] = expected_max_sharpe(out["n_all"], out["std_all"])
    split = pd.Timestamp("2024-01-01", tz="UTC")
    for name in (final_portfolio, final_coin):
        for itv in ("1d", "4h", "1h"):
            if pf is not None and (name, itv) in pf["curves"]:
                eq = pf["curves"][(name, itv)][0].astype(float)
                eq_is, eq_oos = eq[eq.index < split], eq[eq.index >= split]
            else:
                eq_is, _ = portfolio_curves(curves, name, itv, "is")
                eq_oos, _ = portfolio_curves(curves, name, itv, "oos")
            if len(eq_is) < 30:
                continue
            r_is = daily_equity(eq_is).pct_change().dropna()
            r_oos = daily_equity(eq_oos).pct_change().dropna()
            out[f"{name}_{itv}"] = {"dsr_own": deflated_sharpe(r_is, out["n_own"], out["std_own"]),
                                    "dsr_all": deflated_sharpe(r_is, out["n_all"], out["std_all"]),
                                    "psr_oos": probabilistic_sharpe(r_oos)}
    return out


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
        lines.append(f"| `{model}` | " + " | ".join(_de(f"{g.loc[model, c] * 100:.1f} %") for c in cols) + " |")
    lines.append("| *Immer die häufigere Richtung tippen* | " +
                 " | ".join(_de(f"{base[c] * 100:.1f} %") for c in cols) + " |")
    return "\n".join(lines)


def fee_table() -> tuple[str, pd.DataFrame | None]:
    blob = _load("fee_sensitivity")
    if blob is None:
        return "", None
    df = blob if isinstance(blob, pd.DataFrame) else blob.get("rows")
    piv = df[df["period"] == "is"].pivot_table(index=["interval", "strategy"], columns="fee", values="port_sharpe")
    lines = ["| Zeitebene | Bot | " + " | ".join(_de(f"{f * 100:.2f} %") for f in piv.columns) + " |",
             "|" + "---|" * (len(piv.columns) + 2)]
    for (itv, name), r in piv.iterrows():
        lines.append(f"| {itv} | `{name}` | " + " | ".join(fmt_num(v) for v in r.values) + " |")
    return "\n".join(lines), piv


VERSION_LABELS = {
    "buy_hold": "Buy & Hold (jeder Coin)",
    "own_v01_all_bots": "v0.1 – Mittelwert aller Internet-Bots",
    "own_v02_follow_best": "v0.2 – den 3 besten Bots der letzten 180 Tage folgen",
    "own_v03_slow_trend": "v0.3 – Abstimmung langsamer Trendregeln (50–200 Tage)",
    "own_v04_vol_target": "v0.4 – v0.3 + Volatilitäts-Targeting",
    "own_v05_fast_trend": "v0.5 – Abstimmung von 8 Top-Regeln des Benchmarks",
    "trend_bot_v1": "**v1.0 – trend_bot_v1** (Mehrheitsentscheid der 8 Regeln)",
    "pf_equal_weight": "Buy & Hold, gleich gewichtet (Portfolio)",
    "pf_xs_momentum_30d_top5": "Momentum-Rotation 30 Tage (Referenz aus der Literatur)",
    "rotation_v0_plain": "Rotation v0 – Dual Momentum ohne Filter",
    "rotation_bot_v1": "**rotation_bot_v1** (Dual Momentum + Trend- & BTC-Filter + Risiko-Gewichtung)",
}


def evolution_table(rows: pd.DataFrame, names: list[str]) -> str:
    """Mean Sharpe over the 3 timeframes plus 1d details, for IS and OOS."""
    head = ("| Version | Sharpe IS (Ø 1d/4h/1h) | Sharpe OOS (Ø) | CAGR IS (1d) | CAGR OOS (1d) | "
            "Max. DD IS (1d) | Max. DD OOS (1d) |\n|---|---|---|---|---|---|---|")
    lines = [head]
    for n in names:
        sub = rows[rows["strategy"] == n]
        if sub.empty:
            continue
        def val(period, col, itv=None):
            s = sub[sub["period"] == period]
            if itv:
                s = s[s["interval"] == itv]
            return s[col].mean() if not s.empty else np.nan
        lines.append(f"| {VERSION_LABELS.get(n, n)} | {fmt_num(val('is', 'port_sharpe'))} | "
                     f"{fmt_num(val('oos', 'port_sharpe'))} | {fmt_pct(val('is', 'port_cagr', '1d'))} | "
                     f"{fmt_pct(val('oos', 'port_cagr', '1d'))} | {fmt_pct(val('is', 'port_maxdd', '1d'))} | "
                     f"{fmt_pct(val('oos', 'port_maxdd', '1d'))} |")
    return "\n".join(lines)
