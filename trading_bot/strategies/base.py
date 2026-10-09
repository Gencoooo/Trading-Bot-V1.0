"""Strategy interface and registry."""

from __future__ import annotations

from typing import Callable

import pandas as pd

from ..backtest import Signals


class Strategy:
    """Base class. Subclasses implement :meth:`generate`.

    ``generate`` must be causal: the signal at bar ``t`` may only use candles up
    to and including ``t`` (enforced by tests/test_causality.py for every
    registered strategy).
    """

    name: str = "base"
    family: str = "other"       # benchmark | trend | breakout | mean_reversion | ml | bot | ensemble
    source: str = ""            # where the idea comes from (repo, script, paper)
    native_timeframe: str | None = None
    description: str = ""

    def __init__(self, **params):
        self.params = params

    def generate(self, df: pd.DataFrame, interval: str) -> Signals:  # pragma: no cover
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name})"


REGISTRY: dict[str, Callable[[], Strategy]] = {}


def add(name: str, cls: type[Strategy], *, description: str | None = None, source: str | None = None,
        native_timeframe: str | None = None, family: str | None = None, **params) -> None:
    """Register a (possibly parameterized) strategy variant under ``name``."""
    def make() -> Strategy:
        inst = cls(**params)
        inst.name = name
        if description is not None:
            inst.description = description
        if source is not None:
            inst.source = source
        if native_timeframe is not None:
            inst.native_timeframe = native_timeframe
        if family is not None:
            inst.family = family
        return inst
    if name in REGISTRY:
        raise ValueError(f"duplicate strategy name {name!r}")
    REGISTRY[name] = make


def get_strategy(name: str) -> Strategy:
    from . import load_all
    load_all()
    if name not in REGISTRY:
        raise KeyError(f"unknown strategy {name!r}. Available: {', '.join(sorted(REGISTRY))}")
    return REGISTRY[name]()


def list_strategies(families: set[str] | None = None, exclude_families: set[str] | None = None,
                    include_demo: bool = False) -> list[str]:
    """Registered strategy names. The deliberately leaky 'demo' family is excluded
    unless ``include_demo`` is set."""
    from . import load_all
    load_all()
    names = []
    for name, make in REGISTRY.items():
        fam = make().family
        if fam == "demo" and not include_demo:
            continue
        if families is not None and fam not in families:
            continue
        if exclude_families is not None and fam in exclude_families:
            continue
        names.append(name)
    return names
