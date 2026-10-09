"""Phone notifications via Telegram.

Enabled when both environment variables are set:

* ``TB_TELEGRAM_TOKEN``   - bot token from @BotFather
* ``TB_TELEGRAM_CHAT_ID`` - your chat id (``python -m trading_bot notify`` finds it)

Optional: ``TB_NOTIFY_DAILY=1`` also sends a short message on days without
trades, so you notice when the bot did not run at all.

Sending never raises: a missing network or a wrong token only logs a warning,
the bot itself keeps working.
"""

from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger("trading_bot.notify")
API = "https://api.telegram.org/bot{token}/{method}"


def _post(token: str, method: str, **data) -> dict:
    r = requests.post(API.format(token=token, method=method), data=data, timeout=10)
    r.raise_for_status()
    return r.json()


def _trades(report: dict) -> tuple[list[str], list[str]]:
    """(executed trades, failed orders) as text lines, for both runner types."""
    done, failed = [], []
    for sym, info in report.items():
        if sym.startswith("_") or not isinstance(info, dict):
            continue
        action = str(info.get("action", ""))
        if "error" in info:
            what = "Kauf" if action == "buy" else "Verkauf"
            failed.append(f"⚠️ {what} {sym} fehlgeschlagen: {info['error'][:150]}")
        elif action in ("buy", "sell"):  # portfolio runner
            icon, what = ("🟢", "Kauf") if action == "buy" else ("🔴", "Verkauf")
            done.append(f"{icon} {what} {sym} (Ziel {info.get('target', 0) * 100:.0f} %)")
        elif action.startswith("Kauf"):  # single-coin runner
            done.append(f"🟢 {sym} {action}")
        elif action.startswith("Verkauf"):
            done.append(f"🔴 {sym} {action}")
    return done, failed


def format_report(label: str, report: dict, quote: str, daily: bool = False) -> str | None:
    """Message for one run, or None when nothing worth reporting happened."""
    done, failed = _trades(report)
    equity = report.get("_equity")
    value = f"Kontowert: {equity:,.2f} {quote}".replace(",", "'") if equity is not None else ""
    if not done and not failed:
        return f"✅ {label}\nKeine Orders heute. {value}".strip() if daily else None
    lines = [f"🤖 {label}"]
    if done:
        lines += ["Ausgeführt:", *done]
    if failed:
        lines += ["", *failed, "Wird beim nächsten Lauf nachgeholt."]
    if value:
        lines += ["", value]
    return "\n".join(lines)


def format_error(label: str, exc: BaseException | str) -> str:
    text = exc if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
    msg = f"❌ {label}\nLauf abgebrochen:\n{str(text)[:500]}"
    if "-2015" in str(text) or "Invalid API-key" in str(text):
        msg += "\n\nTipp: API-Key, Rechte oder IP-Freigabe prüfen. Hat sich deine IP geändert? curl -4 -s ifconfig.me"
    return msg


class Notifier:
    def __init__(self, label: str, token: str | None = None, chat_id: str | None = None, daily: bool = False):
        self.label, self.token, self.chat_id, self.daily = label, token, chat_id, daily

    @classmethod
    def from_env(cls, label: str) -> "Notifier":
        return cls(label, os.environ.get("TB_TELEGRAM_TOKEN"), os.environ.get("TB_TELEGRAM_CHAT_ID"),
                   os.environ.get("TB_NOTIFY_DAILY", "").strip() not in ("", "0", "false", "no"))

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str | None) -> bool:
        if not text or not self.enabled:
            return False
        try:
            _post(self.token, "sendMessage", chat_id=self.chat_id, text=text)
            return True
        except Exception as exc:  # never let a notification break trading
            log.warning("Telegram-Nachricht konnte nicht gesendet werden: %s", exc)
            return False

    def report(self, report: dict, quote: str) -> bool:
        return self.send(format_report(self.label, report, quote, daily=self.daily))

    def error(self, exc: BaseException | str) -> bool:
        return self.send(format_error(self.label, exc))


def find_chat_ids(token: str) -> list[tuple[str, str]]:
    """(chat id, name) of everyone who has written to the bot recently."""
    out = {}
    for upd in _post(token, "getUpdates").get("result", []):
        chat = (upd.get("message") or upd.get("my_chat_member") or {}).get("chat") or {}
        if "id" in chat:
            name = chat.get("first_name") or chat.get("title") or chat.get("username") or ""
            out[str(chat["id"])] = name
    return list(out.items())
