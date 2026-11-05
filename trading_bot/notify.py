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

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

log = logging.getLogger("trading_bot.notify")
API = "https://api.telegram.org/bot{token}/{method}"
STATE_PATH = Path(__file__).resolve().parent.parent / "state" / "notify_state.json"
REPEAT_ERROR_HOURS = 6   # the same error (e.g. every 15 min from the news guard) at most this often


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
            why = f" wegen News: {info['news']}" if info.get("news") else f" (Ziel {info.get('target', 0) * 100:.0f} %)"
            done.append(f"{icon} {what} {sym}{why}")
        elif action.startswith("Kauf"):  # single-coin runner
            done.append(f"🟢 {sym} {action}")
        elif action.startswith("Verkauf"):
            done.append(f"🔴 {sym} {action}")
    return done, failed


def format_report(label: str, report: dict, quote: str, daily: bool = False) -> str | None:
    """Message for one run, or None when nothing worth reporting happened."""
    done, failed = _trades(report)
    news = _news_lines(report)
    equity = report.get("_equity")
    value = f"Kontowert: {equity:,.2f} {quote}".replace(",", "'") if equity is not None else ""
    if not done and not failed and not news:
        return f"✅ {label}\nKeine Orders heute. {value}".strip() if daily else None
    lines = [f"🤖 {label}"]
    if news:
        lines += news
    if done:
        lines += ([""] if news else []) + ["Ausgeführt:", *done]
    if failed:
        lines += ["", *failed, "Wird beim nächsten Lauf nachgeholt."]
    if value:
        lines += ["", value]
    return "\n".join(lines)


def _news_lines(report: dict) -> list[str]:
    """Exchange alerts and coins skipped at a rebalance because of news."""
    lines = []
    for a in report.get("_news_alerts") or []:
        lines.append(f"🚨 News-Warnung {a['subject']}: {a['category']} ({a['count']} Meldungen)\n{a['title']}")
    if lines:
        lines.append("Der Bot verkauft deswegen nichts automatisch - Guthaben auf der Börse selbst prüfen.")
    for sym, why in (report.get("_news_blocked") or {}).items():
        lines.append(f"📰 {sym} wegen News nicht gekauft: {why}")
    tilt = report.get("_news_tilt") or {}
    if tilt:
        lines.append("📈 News-Prognose: " + ", ".join(f"{s} {o * 100:.0f}→{n * 100:.0f} %" for s, (o, n) in tilt.items()))
    return lines


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
            text = str(exc).replace(self.token, "<TOKEN>")  # the token is part of the URL - keep it out of logs
            hint = " (Token prüfen)" if "404" in text or "401" in text else ""
            log.warning("Telegram-Nachricht konnte nicht gesendet werden%s: %s", hint, text)
            return False

    def report(self, report: dict, quote: str) -> bool:
        state = _load_state()
        if self.label in state.get("errors", {}) and self.enabled:  # it works again: say so once
            del state["errors"][self.label]
            _save_state(state)
            self.send(f"✅ {self.label}\nLäuft wieder normal.")
        return self.send(format_report(self.label, report, quote, daily=self.daily))

    def error(self, exc: BaseException | str) -> bool:
        """Send an error, but the same error of the same bot only every REPEAT_ERROR_HOURS."""
        text = format_error(self.label, exc)
        if not self.enabled:
            return False
        sig = hashlib.sha1(re.sub(r"\d{6,}", "#", text).encode()).hexdigest()[:12]  # ignore timestamps
        now = datetime.now(timezone.utc)
        state = _load_state()
        prev = state.setdefault("errors", {}).get(self.label)
        if prev and prev["sig"] == sig and now - datetime.fromisoformat(prev["time"]) < timedelta(hours=REPEAT_ERROR_HOURS):
            log.info("Gleicher Fehler wie zuletzt - keine neue Telegram-Nachricht.")
            return False
        sent = self.send(text + (f"\n\n(Gleicher Fehler wird höchstens alle {REPEAT_ERROR_HOURS} h gemeldet; "
                                 "Entwarnung kommt, sobald es wieder läuft.)"))
        if sent:
            state["errors"][self.label] = {"sig": sig, "time": now.isoformat()}
            _save_state(state)
        return sent


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(state, indent=1))
    os.replace(tmp, STATE_PATH)


IP_URLS = ("https://api.ipify.org", "https://ifconfig.me/ip", "https://ipv4.icanhazip.com")


def public_ip() -> str | None:
    for url in IP_URLS:
        try:
            r = requests.get(url, timeout=10)
            ip = r.text.strip()
            if r.ok and re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", ip):
                return ip
        except requests.RequestException:
            continue
    return None


def check_public_ip(notifier: "Notifier") -> tuple[str | None, str | None]:
    """(old, new) public IP; sends a Telegram message when it changed. Binance API keys are
    usually restricted to one IP, so a new IP stops the live bot until it is added there."""
    ip = public_ip()
    if ip is None:
        return None, None
    state = _load_state()
    old = state.get("public_ip")
    if old != ip:
        state["public_ip"] = ip
        state["public_ip_since"] = datetime.now(timezone.utc).isoformat()
        _save_state(state)
        if old:
            notifier.send(f"🌐 Öffentliche IP des Servers hat sich geändert: {old} → {ip}\n"
                          "Bitte bei Binance (API-Verwaltung → Key bearbeiten → IP-Zugriff) die neue IP eintragen, "
                          "sonst kann der Live-Bot nicht handeln.")
    return old, ip


def find_chat_ids(token: str) -> list[tuple[str, str]]:
    """(chat id, name) of everyone who has written to the bot recently."""
    out = {}
    for upd in _post(token, "getUpdates").get("result", []):
        chat = (upd.get("message") or upd.get("my_chat_member") or {}).get("chat") or {}
        if "id" in chat:
            name = chat.get("first_name") or chat.get("title") or chat.get("username") or ""
            out[str(chat["id"])] = name
    return list(out.items())
