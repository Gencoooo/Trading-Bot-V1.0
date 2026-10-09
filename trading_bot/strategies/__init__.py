"""Strategy zoo: re-implementations of popular public trading & prediction bots,
plus this project's own bot (see ``ensemble.py``)."""

from .base import REGISTRY, Strategy, add, get_strategy, list_strategies

_LOADED = False


def load_all() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    import importlib
    for module in ("classic", "freqtrade", "tradingview", "bots", "ml", "ensemble"):
        importlib.import_module(f"{__name__}.{module}")  # modules register their strategies on import


__all__ = ["REGISTRY", "Strategy", "add", "get_strategy", "list_strategies", "load_all"]
