import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_notify_state(tmp_path, monkeypatch):
    """Tests must never touch the real state/notify_state.json (it silences repeated errors)."""
    from trading_bot import notify
    monkeypatch.setattr(notify, "STATE_PATH", tmp_path / "notify_state.json")
