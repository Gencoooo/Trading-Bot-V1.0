"""Performance metrics.

All risk/return statistics are computed on *daily* equity (crypto trades 365 days
a year), regardless of the bar size the strategy ran on, so 1h, 4h and 1d
backtests are directly comparable.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

DAYS_PER_YEAR = 365.0
EULER_GAMMA = 0.5772156649015329


def daily_equity(equity: pd.Series) -> pd.Series:
    if equity.empty:
        return equity
    return equity.resample("1D").last().ffill().dropna()


def slice_equity(equity: pd.Series, start=None, end=None) -> pd.Series:
    out = equity
    if start is not None:
        out = out[out.index >= pd.Timestamp(start, tz="UTC")]
    if end is not None:
        out = out[out.index < pd.Timestamp(end, tz="UTC")]
    return out


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float((equity / equity.cummax() - 1.0).min())


def max_drawdown_duration_days(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    underwater = equity < peak
    longest = 0.0
    start = None
    for ts, uw in underwater.items():
        if uw and start is None:
            start = ts
        elif not uw and start is not None:
            longest = max(longest, (ts - start).total_seconds() / 86400)
            start = None
    if start is not None:
        longest = max(longest, (equity.index[-1] - start).total_seconds() / 86400)
    return longest


def sharpe(daily_returns: pd.Series) -> float:
    sd = daily_returns.std(ddof=1)
    if not sd or np.isnan(sd) or sd < 1e-12:
        return 0.0
    return float(daily_returns.mean() / sd * math.sqrt(DAYS_PER_YEAR))


def sortino(daily_returns: pd.Series) -> float:
    downside = np.sqrt(np.mean(np.minimum(daily_returns.to_numpy(), 0.0) ** 2))
    if downside < 1e-12:
        return 0.0
    return float(daily_returns.mean() / downside * math.sqrt(DAYS_PER_YEAR))


def probabilistic_sharpe(daily_returns: pd.Series, sr_benchmark: float = 0.0) -> float:
    """PSR (Bailey & Lopez de Prado): probability that the true Sharpe exceeds the
    benchmark, accounting for sample length, skewness and fat tails.
    Sharpe values are annualized; they are converted to daily internally."""
    r = daily_returns.dropna().to_numpy()
    n = len(r)
    if n < 30 or r.std(ddof=1) < 1e-12:
        return float("nan")
    sr = r.mean() / r.std(ddof=1)
    sr_b = sr_benchmark / math.sqrt(DAYS_PER_YEAR)
    skew = stats.skew(r)
    kurt = stats.kurtosis(r, fisher=False)
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2
    if denom <= 0:
        return float("nan")
    return float(stats.norm.cdf((sr - sr_b) * math.sqrt(n - 1) / math.sqrt(denom)))


def expected_max_sharpe(n_trials: int, sharpe_std: float) -> float:
    """Expected maximum annualized Sharpe among ``n_trials`` skill-less strategies
    (used as the benchmark of the Deflated Sharpe Ratio)."""
    if n_trials < 2:
        return 0.0
    z1 = stats.norm.ppf(1.0 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    return float(sharpe_std * ((1.0 - EULER_GAMMA) * z1 + EULER_GAMMA * z2))


def deflated_sharpe(daily_returns: pd.Series, n_trials: int, sharpe_std: float) -> float:
    """DSR: PSR measured against the Sharpe you'd expect from the luckiest of
    ``n_trials`` random strategies. > 0.95 means the edge likely survives selection bias."""
    return probabilistic_sharpe(daily_returns, expected_max_sharpe(n_trials, sharpe_std))


def trade_stats(trades: pd.DataFrame) -> dict:
    if trades is None or trades.empty:
        return {"trades": 0, "win_rate": float("nan"), "avg_trade": float("nan"),
                "profit_factor": float("nan"), "avg_bars": float("nan")}
    r = trades["return"].astype(float)
    gains = r[r > 0].sum()
    losses = -r[r < 0].sum()
    return {
        "trades": int(len(r)),
        "win_rate": float((r > 0).mean()),
        "avg_trade": float(r.mean()),
        "profit_factor": float(gains / losses) if losses > 0 else float("inf") if gains > 0 else float("nan"),
        "avg_bars": float(trades["bars"].mean()),
    }


def compute_metrics(
    equity: pd.Series,
    exposure: pd.Series | None = None,
    trades: pd.DataFrame | None = None,
    fees_paid: float = 0.0,
    start=None,
    end=None,
) -> dict:
    """Full metric set for an equity curve, optionally restricted to [start, end)."""
    eq = slice_equity(equity, start, end)
    if len(eq) < 2:
        return {}
    d = daily_equity(eq)
    rets = d.pct_change().dropna()
    days = max((eq.index[-1] - eq.index[0]).total_seconds() / 86400, 1.0)
    total = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (DAYS_PER_YEAR / days) - 1.0) if eq.iloc[-1] > 0 else -1.0
    mdd = max_drawdown(d)
    out = {
        "start": eq.index[0], "end": eq.index[-1], "days": days,
        "total_return": total,
        "cagr": cagr,
        "volatility": float(rets.std(ddof=1) * math.sqrt(DAYS_PER_YEAR)) if len(rets) > 1 else 0.0,
        "sharpe": sharpe(rets),
        "sortino": sortino(rets),
        "max_drawdown": mdd,
        "calmar": float(cagr / abs(mdd)) if mdd < 0 else float("nan"),
        "max_dd_days": max_drawdown_duration_days(d),
        "psr": probabilistic_sharpe(rets),
    }
    if exposure is not None:
        out["exposure"] = float(slice_equity(exposure, start, end).abs().mean())
    if trades is not None:
        t = trades
        if start is not None or end is not None:
            et = pd.to_datetime(t["entry_time"], utc=True)
            mask = pd.Series(True, index=t.index)
            if start is not None:
                mask &= et >= pd.Timestamp(start, tz="UTC")
            if end is not None:
                mask &= et < pd.Timestamp(end, tz="UTC")
            t = t[mask]
        out.update(trade_stats(t))
        years = days / DAYS_PER_YEAR
        out["trades_per_year"] = out["trades"] / years if years > 0 else float("nan")
    out["fees_pct"] = fees_paid / float(equity.iloc[0]) if start is None and end is None else float("nan")
    return out


def portfolio_equity(equities: dict[str, pd.Series], initial: float = 1.0) -> pd.Series:
    """Equal-weight portfolio of strategy sleeves, rebalanced daily across the assets
    that have data on a given day (new listings join, delisted coins drop out)."""
    daily = {k: daily_equity(v) for k, v in equities.items() if len(v) > 1}
    if not daily:
        return pd.Series(dtype=float)
    rets = pd.DataFrame({k: v.pct_change() for k, v in daily.items()})
    port = rets.mean(axis=1, skipna=True).fillna(0.0)
    return initial * (1.0 + port).cumprod()
