"""Telegram notifications: message content, silence when unconfigured, never crash the bot."""

import pytest

from trading_bot import cli, notify


@pytest.fixture
def sent(monkeypatch):
    messages = []
    monkeypatch.setattr(notify, "_post", lambda token, method, **data: messages.append(data["text"]) or {})
    return messages


PORTFOLIO_REPORT = {
    "_equity": 192.79, "_rebalanced": True, "_failed": ["AVAXUSDC"],
    "SOLUSDC": {"target": 0.273, "was": 0.0, "action": "buy"},
    "BTCUSDC": {"target": 0.0, "was": 0.2, "action": "sell"},
    "AVAXUSDC": {"target": 0.159, "was": 0.0, "action": "buy", "error": "insufficient balance"},
}


def test_portfolio_report_lists_trades_failures_and_equity():
    text = notify.format_report("LIVE · rotation_bot_v1", PORTFOLIO_REPORT, "USDC")
    assert "Kauf SOLUSDC (Ziel 27 %)" in text and "Verkauf BTCUSDC" in text
    assert "AVAXUSDC fehlgeschlagen: insufficient balance" in text
    assert "192.79 USDC" in text


def test_single_coin_report():
    report = {"_equity": 1000.0, "BTCUSDT": {"price": 1, "target": 1, "current": 0, "action": "Kauf 0.01"},
              "ETHUSDT": {"price": 1, "target": 0, "current": 0, "action": "halten"}}
    text = notify.format_report("PAPER · trend_bot_v1", report, "USDT")
    assert "BTCUSDT Kauf 0.01" in text and "ETHUSDT" not in text


def test_quiet_day_only_with_daily_option():
    report = {"_equity": 100.0, "_rebalanced": False}
    assert notify.format_report("x", report, "USDC") is None
    assert "Keine Orders" in notify.format_report("x", report, "USDC", daily=True)


def test_auth_error_gets_ip_hint():
    text = notify.format_error("LIVE", RuntimeError('binance {"code":-2015,"msg":"Invalid API-key, IP"}'))
    assert "IP" in text and "ifconfig.me" in text


def test_unconfigured_notifier_sends_nothing(sent):
    assert not notify.Notifier("x").send("hallo")
    assert sent == []


def test_send_failure_never_raises(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("offline")
    monkeypatch.setattr(notify, "_post", boom)
    assert notify.Notifier("x", "t", "1").send("hallo") is False


class _Runner:
    def __init__(self, result):
        self.result = result

    def step(self):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_each_step_is_reported(sent):
    runner = _Runner(PORTFOLIO_REPORT)
    cli._notify_each_step(runner, notify.Notifier("LIVE", "t", "1"), "USDC")
    assert runner.step() is PORTFOLIO_REPORT
    assert len(sent) == 1 and "SOLUSDC" in sent[0]


def test_crash_is_reported_once_and_reraised(sent):
    runner = _Runner(RuntimeError("Invalid API-key, IP, or permissions"))
    cli._notify_each_step(runner, notify.Notifier("LIVE", "t", "1"), "USDC")
    with pytest.raises(RuntimeError) as info:
        runner.step()
    assert info.value._tb_notified and len(sent) == 1 and "abgebrochen" in sent[0]


def test_paper_command_reports_startup_errors(sent, monkeypatch):
    monkeypatch.setenv("TB_TELEGRAM_TOKEN", "t")
    monkeypatch.setenv("TB_TELEGRAM_CHAT_ID", "1")
    monkeypatch.delenv("TB_API_KEY", raising=False)
    monkeypatch.delenv("TB_API_SECRET", raising=False)
    pytest.importorskip("ccxt")
    with pytest.raises(SystemExit):
        cli.main(["paper", "--live", "--i-understand-the-risks", "--once"])
    assert len(sent) == 1 and "TB_API_KEY" in sent[0]
