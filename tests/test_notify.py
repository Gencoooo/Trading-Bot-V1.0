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


def test_token_is_not_written_to_the_log(monkeypatch, caplog):
    def boom(token, method, **data):
        raise RuntimeError(f"404 Client Error: Not Found for url: https://api.telegram.org/bot{token}/sendMessage")
    monkeypatch.setattr(notify, "_post", boom)
    with caplog.at_level("WARNING"):
        notify.Notifier("x", "123:SECRET", "1").send("hallo")
    assert "SECRET" not in caplog.text and "<TOKEN>" in caplog.text


def test_same_error_is_sent_once_and_recovery_is_announced(sent, tmp_path, monkeypatch):
    monkeypatch.setattr(notify, "STATE_PATH", tmp_path / "n.json")
    n = notify.Notifier("LIVE", "t", "c")
    err = 'AuthenticationError: binance {"code":-2015,"msg":"Invalid API-key, IP"} ts=1793418000123'
    assert n.error(err)
    assert not n.error(err.replace("1793418000123", "1793418900456"))  # 15 min later, same error
    assert n.error("NetworkError: timeout")                              # a different error is sent
    n.report({"_equity": 1.0}, "USDC")
    assert any("Läuft wieder normal" in m for m in sent)
    assert n.error(err)                                                  # after recovery: report again


def test_ip_change_is_reported(sent, tmp_path, monkeypatch):
    monkeypatch.setattr(notify, "STATE_PATH", tmp_path / "n.json")
    ips = iter(["1.2.3.4", "1.2.3.4", "5.6.7.8"])
    monkeypatch.setattr(notify, "public_ip", lambda: next(ips))
    n = notify.Notifier("Server", "t", "c")
    assert notify.check_public_ip(n) == (None, "1.2.3.4") and not sent   # first run only stores
    notify.check_public_ip(n)
    assert notify.check_public_ip(n) == ("1.2.3.4", "5.6.7.8")
    assert len(sent) == 1 and "5.6.7.8" in sent[0]
