"""Benchmark harness: run many strategies over many coins and timeframes, then
aggregate per-asset metrics and equal-weight portfolio metrics for the
in-sample (design) and out-of-sample (validation) periods."""

from __future__ import annotations

import os
import pickle
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ..backtest import BacktestResult, Costs, run_backtest
from ..data import DEFAULT_UNIVERSE, load_ohlcv
from ..metrics import compute_metrics, daily_equity, portfolio_equity
from ..strategies import Strategy, get_strategy, list_strategies

# Design decisions are made on the in-sample period only. The out-of-sample
# period is touched once, for the final validation.
OOS_START = "2024-01-01"
PERIODS = {
    "is": (None, OOS_START),
    "oos": (OOS_START, None),
    "full": (None, None),
}

SCRATCH = Path(__file__).resolve().parents[2] / "reports" / "_scratch"


def backtest_strategy(strategy: Strategy, df: pd.DataFrame, interval: str, costs: Costs | None = None,
                      capital: float = 10_000.0) -> BacktestResult:
    costs = costs or Costs()
    if hasattr(strategy, "simulate"):
        res = strategy.simulate(df, interval, costs, capital)
    else:
        res = run_backtest(df, strategy.generate(df, interval), interval, costs, capital, name=strategy.name)
    res.name = strategy.name
    return res


@dataclass
class Task:
    symbol: str
    interval: str
    strategies: list[str]
    costs: Costs


def _run_task(task: Task) -> tuple[list[dict], dict]:
    warnings.filterwarnings("ignore")
    os.environ.setdefault("TB_TORCH_THREADS", "1")
    try:  # one BLAS/OpenMP thread per worker process, otherwise 4 workers oversubscribe the CPU
        from threadpoolctl import threadpool_limits
        threadpool_limits(1)
    except ImportError:
        pass
    df = load_ohlcv(task.symbol, task.interval)
    rows: list[dict] = []
    curves: dict = {}
    for name in task.strategies:
        strat = get_strategy(name)
        t0 = time.time()
        res = backtest_strategy(strat, df, task.interval, task.costs)
        runtime = time.time() - t0
        for period, (start, end) in PERIODS.items():
            m = compute_metrics(res.equity, res.exposure, res.trades, res.fees_paid, start, end)
            if not m:
                continue
            rows.append({"strategy": name, "family": strat.family, "symbol": task.symbol,
                         "interval": task.interval, "period": period, "runtime": runtime, **m})
        curves[(name, task.symbol, task.interval)] = (
            daily_equity(res.equity).astype("float32"),
            daily_equity(res.exposure.clip(lower=-1, upper=1)).astype("float32"),
        )
    return rows, curves


def run_benchmark(
    strategies: list[str] | None = None,
    symbols: tuple[str, ...] | list[str] = DEFAULT_UNIVERSE,
    intervals: tuple[str, ...] | list[str] = ("1d", "4h", "1h"),
    costs: Costs | None = None,
    jobs: int = 4,
    tag: str = "benchmark",
    verbose: bool = True,
) -> tuple[pd.DataFrame, dict]:
    """Run every strategy on every (symbol, interval). Results are cached in
    reports/_scratch/<tag>.pkl so reports can be regenerated without re-running."""
    strategies = strategies or list_strategies()
    costs = costs or Costs()
    order = {"1h": 0, "4h": 1, "1d": 2}  # heavy tasks first for better load balancing
    tasks = [Task(s, i, list(strategies), costs) for i in sorted(intervals, key=lambda x: order.get(x, 3))
             for s in symbols]
    rows: list[dict] = []
    curves: dict = {}
    t0 = time.time()
    if jobs <= 1:
        for k, task in enumerate(tasks, 1):
            r, c = _run_task(task)
            rows += r
            curves.update(c)
            if verbose:
                print(f"[{k}/{len(tasks)}] {task.symbol} {task.interval} done ({time.time() - t0:.0f}s)", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(_run_task, t): t for t in tasks}
            for k, fut in enumerate(as_completed(futures), 1):
                task = futures[fut]
                r, c = fut.result()
                rows += r
                curves.update(c)
                if verbose:
                    print(f"[{k}/{len(tasks)}] {task.symbol} {task.interval} done ({time.time() - t0:.0f}s)",
                          flush=True)
    results = pd.DataFrame(rows)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with open(SCRATCH / f"{tag}.pkl", "wb") as fh:
        pickle.dump({"results": results, "curves": curves, "costs": costs}, fh)
    return results, curves


def load_benchmark(tag: str = "benchmark") -> tuple[pd.DataFrame, dict]:
    with open(SCRATCH / f"{tag}.pkl", "rb") as fh:
        blob = pickle.load(fh)
    return blob["results"], blob["curves"]


def merge_benchmarks(*tags: str, out_tag: str | None = None) -> tuple[pd.DataFrame, dict]:
    frames, curves = [], {}
    for t in tags:
        r, c = load_benchmark(t)
        frames.append(r)
        curves.update(c)
    results = pd.concat(frames, ignore_index=True).drop_duplicates(
        subset=["strategy", "symbol", "interval", "period"], keep="last")
    if out_tag:
        with open(SCRATCH / f"{out_tag}.pkl", "wb") as fh:
            pickle.dump({"results": results, "curves": curves}, fh)
    return results, curves


def portfolio_curves(curves: dict, strategy: str, interval: str, period: str = "full") -> tuple[pd.Series, pd.Series]:
    """Equal-weight portfolio equity and average exposure of one strategy on one timeframe."""
    start, end = PERIODS[period]
    eqs, exps = {}, {}
    for (name, sym, itv), (eq, ex) in curves.items():
        if name != strategy or itv != interval:
            continue
        if start is not None:
            eq, ex = eq[eq.index >= pd.Timestamp(start, tz="UTC")], ex[ex.index >= pd.Timestamp(start, tz="UTC")]
        if end is not None:
            eq, ex = eq[eq.index < pd.Timestamp(end, tz="UTC")], ex[ex.index < pd.Timestamp(end, tz="UTC")]
        if len(eq) > 1:
            eqs[sym] = eq.astype(float)
            exps[sym] = ex.astype(float)
    if not eqs:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    port = portfolio_equity(eqs)
    expo = pd.DataFrame(exps).mean(axis=1)
    return port, expo


def summarize(results: pd.DataFrame, curves: dict, period: str = "is") -> pd.DataFrame:
    """One row per (strategy, interval): portfolio metrics + cross-asset statistics."""
    res = results[results["period"] == period]
    bh = res[res["strategy"] == "buy_hold"].set_index(["symbol", "interval"])
    out = []
    for (name, itv), grp in res.groupby(["strategy", "interval"]):
        port, expo = portfolio_curves(curves, name, itv, period)
        if len(port) < 30:
            continue
        pm = compute_metrics(port)
        g = grp.set_index(["symbol", "interval"])
        common = g.index.intersection(bh.index)
        beat_sharpe = float((g.loc[common, "sharpe"] > bh.loc[common, "sharpe"]).mean()) if len(common) else np.nan
        beat_ret = float((g.loc[common, "total_return"] > bh.loc[common, "total_return"]).mean()) if len(common) else np.nan
        out.append({
            "strategy": name, "family": grp["family"].iloc[0], "interval": itv,
            "port_cagr": pm["cagr"], "port_sharpe": pm["sharpe"], "port_sortino": pm["sortino"],
            "port_maxdd": pm["max_drawdown"], "port_calmar": pm["calmar"], "port_vol": pm["volatility"],
            "port_psr": pm["psr"], "port_total": pm["total_return"],
            "med_sharpe": grp["sharpe"].median(), "mean_cagr": grp["cagr"].mean(),
            "med_maxdd": grp["max_drawdown"].median(), "exposure": float(expo.mean()),
            "trades_per_year": grp["trades_per_year"].mean(), "win_rate": grp["win_rate"].mean(),
            "beat_bh_sharpe": beat_sharpe, "beat_bh_return": beat_ret, "n_assets": len(grp),
        })
    return pd.DataFrame(out).sort_values(["interval", "port_sharpe"], ascending=[True, False]).reset_index(drop=True)


def run_portfolio_benchmark(names: list[str], intervals=("1d", "4h", "1h"), symbols=DEFAULT_UNIVERSE,
                            costs: Costs | None = None, jobs: int = 4, tag: str = "portfolio",
                            factories: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Run portfolio strategies (one account over all coins) on each timeframe.
    Rows use the same column names as :func:`summarize` so both can be ranked together."""
    tasks = [(n, i, tuple(symbols), costs or Costs()) for i in intervals for n in names]
    rows, curves = [], {}
    if jobs <= 1:
        outs = map(_run_portfolio_task, tasks)
    else:
        pool = ProcessPoolExecutor(max_workers=jobs)
        outs = pool.map(_run_portfolio_task, tasks)
    for name, itv, family, metrics, eq, ex, turnover in outs:
        for period, m in metrics.items():
            rows.append({"strategy": name, "family": family, "interval": itv, "period": period,
                         "port_cagr": m["cagr"], "port_sharpe": m["sharpe"], "port_sortino": m["sortino"],
                         "port_maxdd": m["max_drawdown"], "port_calmar": m["calmar"], "port_vol": m["volatility"],
                         "port_psr": m["psr"], "port_total": m["total_return"], "exposure": m["exposure"],
                         "turnover_per_year": turnover, "trades_per_year": np.nan, "beat_bh_sharpe": np.nan,
                         "beat_bh_return": np.nan, "n_assets": len(symbols)})
        curves[(name, itv)] = (eq, ex)
    if jobs > 1:
        pool.shutdown()
    out = pd.DataFrame(rows)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with open(SCRATCH / f"{tag}.pkl", "wb") as fh:
        pickle.dump({"rows": out, "curves": curves}, fh)
    return out, curves


def _run_portfolio_task(task) -> tuple:
    from ..portfolio import load_panel
    from ..portfolio_strategies import get_portfolio_strategy
    warnings.filterwarnings("ignore")
    name, interval, symbols, costs = task
    panel = load_panel(symbols, interval)
    strat = get_portfolio_strategy(name)
    res = strat.run(panel, interval, costs)
    metrics = {}
    for period, (start, end) in PERIODS.items():
        m = compute_metrics(res.equity, start=start, end=end)
        expo = res.exposure
        if start is not None:
            expo = expo[expo.index >= pd.Timestamp(start, tz="UTC")]
        if end is not None:
            expo = expo[expo.index < pd.Timestamp(end, tz="UTC")]
        m["exposure"] = float(expo.mean())
        metrics[period] = m
    years = (res.equity.index[-1] - res.equity.index[0]).days / 365.0
    return (name, interval, strat.family, metrics, daily_equity(res.equity).astype("float32"),
            daily_equity(res.exposure).astype("float32"), res.turnover / max(years, 1e-9))
