"""Strategies that allocate capital *between* coins (run with the portfolio engine)."""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from . import indicators as ta
from .data import INTERVAL_MINUTES
from .portfolio import PortfolioStrategy, align_panel
from .strategies.ensemble import _bars, trend_votes

PORTFOLIO_REGISTRY: dict[str, Callable[[], PortfolioStrategy]] = {}


def add_portfolio(name: str, cls, description: str | None = None, **params) -> None:
    def make():
        inst = cls(**params)
        inst.name = name
        if description:
            inst.description = description
        return inst
    PORTFOLIO_REGISTRY[name] = make


def get_portfolio_strategy(name: str) -> PortfolioStrategy:
    return PORTFOLIO_REGISTRY[name]()


def _rebalance_mask(index: pd.DatetimeIndex, interval: str, every_days: float) -> np.ndarray:
    step = _bars(every_days, interval)
    # anchor on calendar time so that truncating the data never shifts the schedule
    minutes = np.asarray((index - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(minutes=1))
    return (minutes // INTERVAL_MINUTES[interval]) % step == step - 1


class EqualWeightHold(PortfolioStrategy):
    family = "benchmark"
    source = "Benchmark"
    description = "Alle verfügbaren Coins gleich gewichtet, täglich rebalanciert."

    def __init__(self, rebalance_days: float = 1.0):
        self.rebalance_days = rebalance_days

    def weights(self, panel, interval):
        close = align_panel(panel)["close"]
        avail = close.notna().astype(float)
        w = avail.div(avail.sum(axis=1).replace(0, np.nan), axis=0)
        mask = _rebalance_mask(close.index, interval, self.rebalance_days)
        w[~mask] = np.nan
        return w


class XSMomentum(PortfolioStrategy):
    family = "trend"
    source = "Cross-Sectional Momentum (Liu/Tsyvinski/Wu 2022, 'Rotation-Bots')"
    description = "Hält die K Coins mit der besten Rendite der letzten N Tage (nur wenn > 0), gleich gewichtet."

    def __init__(self, lookback_days=30, top_k=5, rebalance_days=7, absolute_filter=True):
        self.lookback_days, self.top_k = lookback_days, top_k
        self.rebalance_days, self.absolute_filter = rebalance_days, absolute_filter

    def weights(self, panel, interval):
        close = align_panel(panel)["close"]
        mom = close / close.shift(_bars(self.lookback_days, interval)) - 1
        rank = mom.rank(axis=1, ascending=False)
        sel = (rank <= self.top_k) & mom.notna()
        if self.absolute_filter:
            sel &= mom > 0
        w = sel.astype(float).div(self.top_k)
        mask = _rebalance_mask(close.index, interval, self.rebalance_days)
        w[~mask] = np.nan
        return w


class MomentumRotation(PortfolioStrategy):
    """Own bot: dual-momentum rotation.

    * relative momentum: rank coins by their average return over several lookbacks,
    * absolute momentum: only coins whose own momentum is positive are eligible,
    * hold the top-K, weighted equally or by inverse volatility (capped),
    * market regime: scale the book down when Bitcoin trades below its 200-day average,
    * rebalance on a fixed weekly calendar with a band to keep turnover (fees) low.
    """

    family = "ensemble"
    source = "Eigenentwicklung (Trading-Bot-V1.0): Dual Momentum nach Antonacci, für Krypto adaptiert"

    def __init__(self, lookbacks=(14, 30, 60), top_k=5, rebalance_days=7, weighting="equal", vol_days=30,
                 max_weight=0.35, btc_filter=True, btc_days=200, btc_scale=0.0, trend_days=None,
                 vol_target=None, band=0.02):
        self.lookbacks, self.top_k, self.rebalance_days = tuple(lookbacks), top_k, rebalance_days
        self.weighting, self.vol_days, self.max_weight = weighting, vol_days, max_weight
        self.btc_filter, self.btc_days, self.btc_scale = btc_filter, btc_days, btc_scale
        self.trend_days, self.vol_target, self.band = trend_days, vol_target, band

    def weights(self, panel, interval):
        close = align_panel(panel)["close"]
        idx = close.index
        moms = [close / close.shift(_bars(d, interval)) - 1 for d in self.lookbacks]
        score = sum(m.rank(axis=1, pct=True) for m in moms) / len(moms)   # relative momentum
        absolute = sum(moms) / len(moms)                                   # absolute momentum
        eligible = absolute.gt(0) & score.notna()
        if self.trend_days:
            eligible &= close > ta.sma(close, _bars(self.trend_days, interval))
        rank = score.where(eligible).rank(axis=1, ascending=False)
        sel = rank <= self.top_k
        if self.weighting == "inv_vol":
            per_year = 365 * 1440 / INTERVAL_MINUTES[interval]
            r = np.log(close).diff()
            vol = np.sqrt((r ** 2).ewm(span=_bars(self.vol_days, interval), adjust=False).mean() * per_year)
            raw = (1.0 / vol.replace(0, np.nan)).where(sel, 0.0).fillna(0.0)
            w = raw.div(raw.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
            w = w * (sel.sum(axis=1) / self.top_k).values[:, None]  # fewer picks -> more cash
            if self.vol_target:
                port_vol = np.sqrt(0.3 * ((w * vol.fillna(0)) ** 2).sum(axis=1)
                                   + 0.7 * (w * vol.fillna(0)).sum(axis=1) ** 2).replace(0, np.nan)
                w = w.mul((self.vol_target / port_vol).clip(upper=1.0).fillna(0.0), axis=0)
        else:
            w = sel.astype(float) / self.top_k
        w = w.clip(upper=self.max_weight)
        if self.btc_filter and "BTCUSDT" in close:
            btc = close["BTCUSDT"]
            risk_on = (btc > ta.sma(btc, _bars(self.btc_days, interval))).fillna(False)
            w = w.mul(np.where(risk_on, 1.0, self.btc_scale), axis=0)
        w = w.where(close.notna(), 0.0)
        w[~_rebalance_mask(idx, interval, self.rebalance_days)] = np.nan
        return w


class TrendPortfolio(PortfolioStrategy):
    """Own bot, portfolio edition: per-coin trend vote x inverse volatility, optional
    momentum top-K selection, portfolio volatility target and BTC regime filter."""

    family = "ensemble"
    source = "Eigenentwicklung (Trading-Bot-V1.0)"

    def __init__(self, components, vol_target=0.5, vol_days=30, top_k=None, mom_days=60, min_score=0.0,
                 max_weight=0.35, btc_filter=False, btc_days=200, btc_scale=0.5, rebalance_days=1.0,
                 corr=0.7, band=0.02):
        self.components, self.vol_target, self.vol_days = components, vol_target, vol_days
        self.top_k, self.mom_days, self.min_score, self.max_weight = top_k, mom_days, min_score, max_weight
        self.btc_filter, self.btc_days, self.btc_scale = btc_filter, btc_days, btc_scale
        self.rebalance_days, self.corr, self.band = rebalance_days, corr, band

    def weights(self, panel, interval):
        wide = align_panel(panel)
        close = wide["close"]
        idx = close.index
        per_year = 365 * 1440 / INTERVAL_MINUTES[interval]
        scores, vols = {}, {}
        for sym, df in panel.items():
            v = trend_votes(df, interval, self.components)
            scores[sym] = v.mean(axis=1).reindex(idx)
            r = np.log(df["close"]).diff()
            vols[sym] = np.sqrt((r ** 2).ewm(span=_bars(self.vol_days, interval), adjust=False).mean()
                                * per_year).reindex(idx)
        S, V = pd.DataFrame(scores), pd.DataFrame(vols)
        S = S.where(S > self.min_score, 0.0).where(close.notna())
        # market breadth: average trend score over all listed coins (before any selection)
        breadth = (S.sum(axis=1) / close.notna().sum(axis=1).replace(0, np.nan)).fillna(0.0)
        if self.top_k:
            mom = close / close.shift(_bars(self.mom_days, interval)) - 1
            rank = mom.where(S > 0).rank(axis=1, ascending=False)
            S = S.where(rank <= self.top_k, 0.0)
        raw = (S / V.replace(0, np.nan)).fillna(0.0)
        total_raw = raw.sum(axis=1)
        w = raw.div(total_raw.replace(0, np.nan), axis=0).fillna(0.0)
        # portfolio vol under a constant-correlation assumption
        sig = (w * V.fillna(0.0))
        port_var = (1 - self.corr) * (sig ** 2).sum(axis=1) + self.corr * sig.sum(axis=1) ** 2
        port_vol = np.sqrt(port_var).replace(0, np.nan)
        scale = (self.vol_target / port_vol).clip(upper=1.0).fillna(0.0)
        # weak breadth (fewer than half of the coins trending) scales the whole book down
        exposure = np.minimum(scale, 1.0) * np.minimum(1.0, breadth * 2)
        w = w.mul(exposure, axis=0).clip(upper=self.max_weight)
        if self.btc_filter and "BTCUSDT" in close:
            btc = close["BTCUSDT"]
            risk_on = (btc > ta.sma(btc, _bars(self.btc_days, interval))).reindex(idx).fillna(True)
            w = w.mul(np.where(risk_on, 1.0, self.btc_scale), axis=0)
        w = w.where(close.notna(), 0.0)
        mask = _rebalance_mask(idx, interval, self.rebalance_days)
        w[~mask] = np.nan
        return w


SMA3 = [("sma", 50), ("sma", 100), ("sma", 200)]
TS3 = [("tsmom", 30), ("tsmom", 90), ("tsmom", 180)]
MIX7 = SMA3 + TS3 + [("donchian", 55, 20)]

add_portfolio("pf_equal_weight", EqualWeightHold)
add_portfolio("pf_xs_momentum_30d_top5", XSMomentum, lookback_days=30, top_k=5, rebalance_days=7)
add_portfolio("pf_xs_momentum_90d_top5", XSMomentum, lookback_days=90, top_k=5, rebalance_days=7)

# Own portfolio bot. Parameters were chosen on in-sample data only (2017-08..2023-12) with the
# pre-registered rule in reports/ERGEBNISSE.md; the plain version is kept to show what the
# filters add.
add_portfolio("rotation_v0_plain", MomentumRotation, btc_filter=False,
              description="Dual Momentum ohne Filter: wöchentlich die 5 Coins mit dem besten 14/30/60-Tage-Momentum "
                          "(nur bei positivem Momentum), gleich gewichtet.")
add_portfolio("rotation_bot_v1", MomentumRotation,
              description="Wöchentlich die 5 Coins mit dem besten 14/30/60-Tage-Momentum, nur über ihrer 100-Tage-Linie, "
                          "gewichtet nach umgekehrter Volatilität (max. 35 %); Cash, wenn BTC unter der 200-Tage-Linie.",
              lookbacks=(14, 30, 60), top_k=5, rebalance_days=7,
              weighting="inv_vol", max_weight=0.35, btc_filter=True, btc_days=200, btc_scale=0.0,
              trend_days=100)
