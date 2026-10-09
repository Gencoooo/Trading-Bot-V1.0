"""Strategy zoo: re-implementations of popular public trading & prediction bots,
plus this project's own bot (see ``ensemble.py``)."""

from .base import REGISTRY, Strategy, add, get_strategy, list_strategies

_LOADED = False


def load_all() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    from . import classic, freqtrade, tradingview, bots, ml, ensemble  # noqa: F401


__all__ = ["REGISTRY", "Strategy", "add", "get_strategy", "list_strategies", "load_all"]
