"""Charts and Markdown tables for the benchmark report."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .benchmark import OOS_START, load_benchmark, portfolio_curves, summarize  # noqa: E402

REPORTS = Path(__file__).resolve().parents[2] / "reports"
FIGURES = REPORTS / "figures"

# Palette (light theme): categorical slots in fixed order + chart chrome.
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
DISPLAY_NAMES = {"buy_hold": "Buy & Hold"}
INACTIVE_EXPOSURE = 0.02  # bots invested less than 2 % of the time are flagged/hidden in rankings
FAMILY_COLORS = {
    "trend": SLOTS[0], "breakout": SLOTS[1], "mean_reversion": SLOTS[2], "ml": SLOTS[3],
    "bot": SLOTS[4], "benchmark": SLOTS[5], "ensemble": SLOTS[6],
}
FAMILY_DE = {
    "trend": "Trendfolge", "breakout": "Ausbruch", "mean_reversion": "Mean Reversion", "ml": "ML-Vorhersage",
    "bot": "DCA/Grid-Bot", "benchmark": "Buy & Hold", "ensemble": "Eigener Bot", "demo": "Demo (absichtlich fehlerhaft)",
    "portfolio": "Portfolio",
}


def _style(ax, grid_axis="y"):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8, linestyle="-")
    ax.set_axisbelow(True)


def _fig(w=10, h=5.5):
    fig, ax = plt.subplots(figsize=(w, h), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    return fig, ax


def _title(ax, title, subtitle=None):
    ax.set_title(title, loc="left", fontsize=13, color=INK, pad=26 if subtitle else 10, fontweight="bold")
    if subtitle:
        ax.annotate(subtitle, xy=(0, 1), xycoords="axes fraction", xytext=(0, 8), textcoords="offset points",
                    fontsize=9.5, color=INK2, va="bottom", ha="left")


def plot_equity(series: dict[str, pd.Series], path: Path, title: str, subtitle: str | None = None,
                colors: dict[str, str] | None = None, split: str | None = OOS_START) -> Path:
    fig, ax = _fig(10, 5.5)
    _style(ax, "both")
    colors = colors or {}
    ends = []
    for k, (label, s) in enumerate(series.items()):
        s = s.dropna()
        if s.empty:
            continue
        s = s / s.iloc[0]
        c = colors.get(label, SLOTS[k % len(SLOTS)])
        ax.plot(s.index, s.values, color=c, linewidth=2.2 if k == 0 else 1.5, label=label, zorder=3 - 0.1 * k)
        ends.append((float(s.iloc[-1]), s.index[-1], _de(f"{s.iloc[-1]:.1f}x"), c))
    ax.set_yscale("log")
    # end-of-line value labels, pushed apart so they never overlap (log space)
    if ends:
        lo, hi = ax.get_ylim()
        span = np.log10(hi) - np.log10(lo)
        gap = 0.045 * span
        ends.sort(key=lambda e: e[0])
        ys = [np.log10(e[0]) for e in ends]
        for i in range(1, len(ys)):
            ys[i] = max(ys[i], ys[i - 1] + gap)
        fig.canvas.draw()
        for (val, x, text, c), y in zip(ends, ys):
            xd = matplotlib.dates.date2num(x)
            p0 = ax.transData.transform((xd, val))
            p1 = ax.transData.transform((xd, 10 ** y))
            dy = (p1[1] - p0[1]) * 72.0 / fig.dpi
            ax.annotate(text, (x, val), xytext=(9, dy), textcoords="offset points", fontsize=8.5, color=INK2,
                        va="center", ha="left", annotation_clip=False)
            ax.plot([x], [val], marker="o", markersize=4.5, color=c, zorder=4)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _de(f"{v:g}x")))
    if split:
        ts = pd.Timestamp(split, tz="UTC")
        ax.axvline(ts, color=AXIS, linewidth=1)
        ax.text(ts, 1.0, "  Out-of-Sample →", transform=ax.get_xaxis_transform(), fontsize=8.5,
                color=INK2, va="top")
    ax.legend(frameon=False, fontsize=9, loc="upper left", labelcolor=INK2)
    _title(ax, title, subtitle)
    ax.margins(x=0.02)
    fig.subplots_adjust(right=0.82)
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_metric_bars(summary: pd.DataFrame, metric: str, path: Path, title: str, subtitle: str | None = None,
                     fmt: str = "{:.2f}", highlight: tuple[str, ...] = ()) -> Path:
    df = summary[summary["exposure"] >= INACTIVE_EXPOSURE].sort_values(metric)
    h = max(4.0, 0.22 * len(df) + 1.2)
    fig, ax = _fig(9, h)
    _style(ax, "x")
    y = np.arange(len(df))
    colors = [FAMILY_COLORS.get(f, MUTED) for f in df["family"]]
    ax.barh(y, df[metric], color=colors, height=0.72, edgecolor=SURFACE, linewidth=1)
    ax.set_yticks(y)
    labels = [f"{n} ({i})" if "interval" in df and len(set(df["interval"])) > 1 else n
              for n, i in zip(df["strategy"], df.get("interval", [""] * len(df)))]
    ax.set_yticklabels(labels, fontsize=8)
    for tick, name in zip(ax.get_yticklabels(), df["strategy"]):
        if name in highlight:
            tick.set_fontweight("bold")
            tick.set_color(INK)
    ax.xaxis.set_major_formatter(_DE_TICKS)
    for yi, v in zip(y, df[metric]):
        ax.text(v + (0.01 if v >= 0 else -0.01) * (abs(df[metric]).max() or 1), yi, _de(fmt.format(v)),
                va="center", ha="left" if v >= 0 else "right", fontsize=7.5, color=INK2)
    ax.axvline(0, color=AXIS, linewidth=0.8)
    fams = [f for f in FAMILY_COLORS if f in set(df["family"])]
    handles = [matplotlib.patches.Patch(color=FAMILY_COLORS[f], label=FAMILY_DE[f]) for f in fams]
    ax.legend(handles=handles, frameon=False, fontsize=8.5, loc="lower right", labelcolor=INK2)
    _title(ax, title, subtitle)
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_risk_return(summary: pd.DataFrame, path: Path, title: str, subtitle: str | None = None,
                     highlight: dict[str, str] | None = None, label_top: int = 6) -> Path:
    """CAGR vs. max drawdown. Zoo in muted gray; highlighted strategies in color."""
    highlight = highlight or {}
    fig, ax = _fig(9, 6)
    _style(ax, "both")
    summary = summary[summary["exposure"] >= INACTIVE_EXPOSURE]
    base = summary[~summary["strategy"].isin(highlight)]
    ax.scatter(-base["port_maxdd"] * 100, base["port_cagr"] * 100, s=34, color=AXIS, edgecolor=SURFACE,
               linewidth=1.5, zorder=2, label="Andere Bots")
    top = base.sort_values("port_sharpe", ascending=False).head(label_top)
    for _, r in top.iterrows():
        ax.annotate(r["strategy"], (-r["port_maxdd"] * 100, r["port_cagr"] * 100), xytext=(5, 3),
                    textcoords="offset points", fontsize=7.5, color=INK2)
    for k, (name, color) in enumerate(highlight.items()):
        r = summary[summary["strategy"] == name]
        if r.empty:
            continue
        r = r.iloc[0]
        shown = DISPLAY_NAMES.get(name, name)
        ax.scatter(-r["port_maxdd"] * 100, r["port_cagr"] * 100, s=90, color=color, edgecolor=SURFACE,
                   linewidth=2, zorder=4, label=shown)
        ax.annotate(shown, (-r["port_maxdd"] * 100, r["port_cagr"] * 100), xytext=(7, -3),
                    textcoords="offset points", fontsize=9, color=INK, fontweight="bold")
    ax.axhline(0, color=AXIS, linewidth=0.8)
    ax.xaxis.set_major_formatter(_DE_TICKS)
    ax.yaxis.set_major_formatter(_DE_TICKS)
    ax.set_xlabel("Maximaler Drawdown (%)", color=INK2, fontsize=9)
    ax.set_ylabel("CAGR (% p.a.)", color=INK2, fontsize=9)
    ax.legend(frameon=False, fontsize=8.5, loc="upper right", labelcolor=INK2)
    _title(ax, title, subtitle)
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_heatmap(matrix: pd.DataFrame, path: Path, title: str, subtitle: str | None = None,
                 fmt: str = "{:.2f}", limit: float | None = None) -> Path:
    """Diverging blue (good) <-> red (bad) heatmap around 0 with a gray midpoint."""
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    cmap = LinearSegmentedColormap.from_list("div", ["#c0392b", "#e88a84", "#f0efec", "#86b6ef", "#1c5cab"])
    vals = matrix.to_numpy(float)
    lim = limit or np.nanmax(np.abs(vals)) or 1.0
    fig, ax = _fig(1.6 + 1.3 * matrix.shape[1], 0.9 + 0.42 * matrix.shape[0])
    ax.imshow(vals, cmap=cmap, norm=TwoSlopeNorm(0.0, -lim, lim), aspect="auto")
    ax.set_xticks(range(matrix.shape[1]))
    ax.set_xticklabels(matrix.columns, fontsize=9, color=INK2)
    ax.set_yticks(range(matrix.shape[0]))
    ax.set_yticklabels(matrix.index, fontsize=9, color=INK2)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            v = vals[i, j]
            if not np.isnan(v):
                ax.text(j, i, _de(fmt.format(v)), ha="center", va="center", fontsize=8.5,
                        color="#ffffff" if abs(v) > 0.6 * lim else INK)
    ax.set_xticks(np.arange(-.5, matrix.shape[1]), minor=True)
    ax.set_yticks(np.arange(-.5, matrix.shape[0]), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=2)
    ax.tick_params(which="minor", length=0)
    _title(ax, title, subtitle)
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_lines(df: pd.DataFrame, path: Path, title: str, xlabel: str, ylabel: str, subtitle: str | None = None,
               colors: dict[str, str] | None = None, xfmt: str = "{:g}") -> Path:
    """One line per column, x = index (e.g. fee level)."""
    fig, ax = _fig(9, 5)
    _style(ax, "both")
    colors = colors or {}
    for k, col in enumerate(df.columns):
        c = colors.get(col, SLOTS[k % len(SLOTS)])
        ax.plot(df.index, df[col], color=c, linewidth=2, marker="o", markersize=5, label=col)
        ax.annotate(col, (df.index[-1], df[col].iloc[-1]), xytext=(6, 0), textcoords="offset points",
                    fontsize=8.5, color=INK2, va="center")
    ax.axhline(0, color=AXIS, linewidth=0.8)
    ax.set_xticks(df.index)
    ax.set_xticklabels([xfmt.format(v) for v in df.index], fontsize=9)
    ax.set_xlabel(xlabel, color=INK2, fontsize=9)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK2)
    _title(ax, title, subtitle)
    fig.subplots_adjust(right=0.8)
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return path


def _de(text: str) -> str:
    """German number format: decimal comma, typographic minus."""
    return text.replace(".", ",").replace("-", "−")


def fmt_pct(v: float, digits: int = 1) -> str:
    return "–" if v is None or (isinstance(v, float) and np.isnan(v)) else _de(f"{v * 100:+.{digits}f} %")


def fmt_num(v: float, digits: int = 2) -> str:
    return "–" if v is None or (isinstance(v, float) and np.isnan(v)) else _de(f"{v:.{digits}f}")


_DE_TICKS = matplotlib.ticker.FuncFormatter(lambda v, _: _de(f"{v:g}"))


def ranking_table(summary: pd.DataFrame, top: int | None = None) -> str:
    cols = ["#", "Bot", "Familie", "CAGR", "Sharpe", "Max. DD", "Calmar", "Zeit im Markt", "Trades/Jahr",
            "schlägt B&H (Sharpe)"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    active = summary["exposure"] >= INACTIVE_EXPOSURE
    df = pd.concat([summary[active].sort_values("port_sharpe", ascending=False),
                    summary[~active].sort_values("port_sharpe", ascending=False)])
    if top:
        df = df.head(top)
    for k, (_, r) in enumerate(df.iterrows(), 1):
        name = f"**{r['strategy']}**" if r["family"] in ("ensemble", "benchmark") else r["strategy"]
        if r["exposure"] < INACTIVE_EXPOSURE:
            name += " †"
        lines.append("| " + " | ".join([
            str(k), name, FAMILY_DE.get(r["family"], r["family"]), fmt_pct(r["port_cagr"]),
            fmt_num(r["port_sharpe"]), fmt_pct(r["port_maxdd"]), fmt_num(r["port_calmar"]),
            f"{r['exposure'] * 100:.0f} %",
            "–" if pd.isna(r["trades_per_year"]) else f"{r['trades_per_year']:.0f}",
            "–" if pd.isna(r["beat_bh_sharpe"]) else f"{r['beat_bh_sharpe'] * 100:.0f} %"]) + " |")
    if (~active).any():
        lines.append("\n† weniger als 2 % der Zeit investiert – die Kennzahlen beruhen auf sehr wenigen Trades "
                     "und sind kaum aussagekräftig.")
    return "\n".join(lines)


def build_report(tag: str = "benchmark") -> Path:
    """Auto-generated appendix with the complete rankings (IS and OOS, all timeframes)."""
    results, curves = load_benchmark(tag)
    FIGURES.mkdir(parents=True, exist_ok=True)
    parts = [f"# Benchmark-Anhang: vollständige Ranglisten (`{tag}`)\n",
             "Equal-Weight-Portfolio über alle Coins, Kosten 0,1 % Gebühr + 0,05 % Slippage pro Order. "
             f"In-Sample = bis {OOS_START}, Out-of-Sample = ab {OOS_START}.\n"]
    for period, label in (("is", "In-Sample (Design-Zeitraum)"), ("oos", "Out-of-Sample (Validierung)")):
        summ = summarize(results, curves, period)
        for itv in ("1d", "4h", "1h"):
            sub = summ[summ["interval"] == itv]
            if sub.empty:
                continue
            parts.append(f"\n## {label} – {itv}\n")
            parts.append(ranking_table(sub))
    path = REPORTS / f"{tag}_rankings.md"
    path.write_text("\n".join(parts) + "\n")
    return path


__all__ = ["plot_equity", "plot_metric_bars", "plot_risk_return", "plot_heatmap", "plot_lines",
           "ranking_table", "build_report", "portfolio_curves", "FAMILY_COLORS", "FAMILY_DE", "SLOTS"]


def strategy_catalog() -> str:
    """Markdown table of every registered strategy with its origin."""
    from ..strategies import REGISTRY, load_all
    load_all()
    order = ["benchmark", "trend", "breakout", "mean_reversion", "bot", "ml", "ensemble"]
    rows = []
    for name, make in REGISTRY.items():
        s = make()
        rows.append((order.index(s.family) if s.family in order else 99, s.family, name, s))
    lines = ["| Bot | Familie | Original-Zeitebene | Vorbild / Quelle | Logik |", "|---|---|---|---|---|"]
    for _, fam, name, s in sorted(rows, key=lambda r: (r[0], r[2])):
        lines.append(f"| `{name}` | {FAMILY_DE.get(fam, fam)} | {s.native_timeframe or '–'} | {s.source} | "
                     f"{s.description} |")
    from ..portfolio_strategies import PORTFOLIO_REGISTRY
    lines += ["", "**Portfolio-Bots** (verteilen das Kapital zwischen den Coins):", "",
              "| Bot | Familie | Vorbild / Quelle | Logik |", "|---|---|---|---|"]
    for name, make in PORTFOLIO_REGISTRY.items():
        p = make()
        desc = (p.description or (type(p).__doc__ or "").strip().splitlines()[0]).strip()
        lines.append(f"| `{name}` | {FAMILY_DE.get(p.family, p.family)} | {p.source} | {desc} |")
    return "\n".join(lines)


def yearly_returns(equity: pd.Series) -> pd.Series:
    """Calendar-year returns of a daily equity curve (partial first/last years included)."""
    eq = equity.dropna()
    if eq.empty:
        return pd.Series(dtype=float)
    year_end = eq.groupby(eq.index.year).last()
    prev = year_end.shift(1)
    prev.iloc[0] = eq.iloc[0]
    return year_end / prev - 1.0
