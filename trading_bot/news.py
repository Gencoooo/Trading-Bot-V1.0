"""Live news tracker: crypto headlines, Fear & Greed index and Binance delisting notices.

News is used as a *risk filter* only - it can make the bot hold less, never more:

* a coin with a critical event (hack/exploit, delisting, insolvency, lawsuit, network outage)
  reported by at least ``MIN_SOURCES`` independent outlets within ``BLOCK_HOURS`` is not bought at
  the next rebalance - its weight stays in cash,
* if that event is fresh (first report less than ``SELL_HOURS`` ago) and confirmed by at least
  ``SELL_MIN_SOURCES`` outlets, a held position is sold right away, also between rebalances
  (``paper --news``, every 15 minutes with ``--guard-only``),
* an official Binance delisting notice for a coin counts on its own,
* critical news about the exchange itself (or the quote stablecoin) is only reported - selling
  into the same exchange's stablecoin would not help, that decision stays with you.

Headlines are scored with a transparent keyword list - no ML, no API key. A critical headline that
names an exchange is attributed to the exchange (and its token, BNB for Binance), not to every coin
it mentions, so "Bitcoin falls after Binance hack" does not mark Bitcoin as hacked. Coins named as
loot ("steals $50M in bitcoin"), as an ecosystem ("Solana-based protocol drained") or in a question
("Worried about crypto hacks? Buy bitcoin ...") are not the subject of the event either.

News is no crystal ball: prices usually move before the first headline (the Binance hack of
29.10.2026: BNB fell 744 -> 680 at 20:30 UTC, the first report came at 21:12). The filter is meant
for events that keep hurting for days - exchange collapses, lawsuits, delistings, chain halts.

Fear & Greed and the overall news mood are shown on the dashboard but not traded: a backtest
2018-2026 found no Fear & Greed rule that improved rotation_bot_v1 out of sample (ANLEITUNG.md).

On top of the filter, :mod:`trading_bot.forecast` turns the headlines into a short-term estimate per
coin; with ``--news-tilt`` it shifts the rebalance weights (see there).

Everything fetched is cached in ``state/news.json``; the dashboard reads that file. Network problems
never stop trading: without fresh news the bot trades exactly as before.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import math
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from . import forecast as fc

log = logging.getLogger("trading_bot.news")
NEWS_PATH = Path(__file__).resolve().parent.parent / "state" / "news.json"
FORECAST_LOG = NEWS_PATH.with_name("news_forecasts.jsonl")
TICKER_URL = "https://data-api.binance.vision/api/v3/ticker/price"

FEEDS = {
    "Cointelegraph": "https://cointelegraph.com/rss",
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Decrypt": "https://decrypt.co/feed",
    "The Block": "https://www.theblock.co/rss.xml",
    "CryptoSlate": "https://cryptoslate.com/feed/",
    "BeInCrypto": "https://beincrypto.com/feed/",
    "NewsBTC": "https://www.newsbtc.com/feed/",
}
FNG_URL = "https://api.alternative.me/fng/"
BINANCE_NOTICES = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
BINANCE_DELIST_CATALOG = 161
HEADERS = {"User-Agent": "Mozilla/5.0 (Trading-Bot-V1.0 news tracker)"}

MIN_SOURCES = 2        # independent outlets needed before a headline event blocks buys
SELL_MIN_SOURCES = 3   # ... and before it sells a held coin (a wrong sale costs more than a skipped buy)
BLOCK_HOURS = 72       # no buys for this long after the last critical report
SELL_HOURS = 24        # sell a held coin only while the event is this fresh
DELIST_DAYS = 14       # an official delisting notice blocks the coin this long
KEEP_DAYS = 7          # headline history kept in the cache
STALE_HOURS = 6        # older cache: news filter is skipped (trade as without news)

# Coin names: case-insensitive patterns and case-sensitive tickers / proper names.
COINS: dict[str, tuple[list[str], list[str]]] = {
    "BTC": ([r"bitcoin(?!\s+cash)"], ["BTC"]),
    "ETH": ([r"ethereum(?!\s+classic)", r"ether"], ["ETH"]),
    "BNB": ([r"bnb", r"binance coin"], []),
    "XRP": ([r"xrp", r"ripple(?!\s+effects?)"], []),
    "ADA": ([r"cardano"], ["ADA"]),
    "SOL": ([r"solana"], ["SOL"]),
    "DOGE": ([r"dogecoin", r"doge"], []),
    "LTC": ([r"litecoin"], ["LTC"]),
    "LINK": ([r"chainlink"], ["LINK"]),
    "TRX": ([r"tron"], ["TRX"]),
    "XLM": ([], ["Stellar", "XLM"]),
    "ETC": ([r"ethereum\s+classic"], ["ETC"]),
    "NEO": ([], ["NEO", "Neo"]),
    "IOTA": ([], ["IOTA", "Iota"]),
    "AVAX": ([], ["Avalanche", "AVAX"]),
    "BCH": ([r"bitcoin\s+cash"], ["BCH"]),
    "DOT": ([r"polkadot"], ["DOT"]),
    "USDC": ([r"usd\s+coin"], ["USDC"]),
    "USDT": ([r"tether"], ["USDT"]),
}
EXCHANGES = ("binance", "coinbase", "kraken", "okx", "bybit", "kucoin", "bitfinex", "gemini", "crypto.com",
             "htx", "gate.io", "upbit", "bitget", "bitstamp")
EXCHANGE_TOKEN = {"binance": "BNB"}
STABLECOINS = ("USDC", "USDT")

CRITICAL = {
    "hack": r"hack(?:s|ed|er|ers|ing)?|exploit(?:s|ed|er)?|drain(?:s|ed)?|breach(?:es|ed)?|heist|stolen|"
            r"attacker|51% attack",
    "delisting": r"delist(?:s|ed|ing)?",
    "insolvency": r"insolven(?:t|cy)|bankrupt(?:cy)?|(?:halts?|suspends?|pauses?|freezes?) withdrawals|"
                  r"withdrawals? (?:halted|suspended|paused|frozen)|depeg(?:s|ged)?",
    "legal": r"sues|sued|lawsuit|indict(?:ed|ment)|charged|fraud|seized|crackdown|banned|bans",
    "outage": r"outage|network (?:halt|halted|down)|stops? producing blocks|chain halt(?:ed)?",
}
CATEGORY_TEXT = {"hack": "Hack/Exploit", "delisting": "Delisting", "insolvency": "Insolvenz/Auszahlungsstopp",
                 "legal": "Klage/Verbot", "outage": "Netzwerk-Ausfall"}
# "SEC drops lawsuit against Ripple" is good news, not a legal threat
LEGAL_RELIEF = r"drops?|dropped|dismiss(?:es|ed)?|ends?|ended|settles?|settled|wins?|won|victory|cleared"
NEGATIVE = (r"plunge[sd]?|crash(?:es|ed)?|slump(?:s|ed)?|tumble[sd]?|dump(?:s|ed)?|sell-?off|drops?|dropped|"
            r"falls?|fell|slides?|slid|sinks?|sank|bearish|liquidat(?:ed|ions?)|fears?|warns?|warning|"
            r"risks?|lows?|loss(?:es)?|outflows?|collapse[sd]?|selling|pain|scam")
POSITIVE = (r"surge[sd]?|soar(?:s|ed)?|rall(?:y|ies|ied)|jumps?|jumped|gains?|climbs?|climbed|"
            r"rebound(?:s|ed)?|bullish|record high|all-time high|ATH|approv(?:al|es|ed)|adoption|partnership|"
            r"inflows?|upgrade[sd]?|rises?|rose|recover(?:s|ed|y)?|breakout|highs?")
# a coin right after these words is the loot or the ecosystem of an event, not its victim:
# "steals $50M in bitcoin", "$1.4 billion of ETH", "protocol on Solana"
LOOT_BEFORE = re.compile(r"(?:\b(?:of|in|on|worth|stolen|stole|steals?|drain(?:s|ed)?|launder(?:s|ed|ing)?|"
                         r"swap(?:s|ped)?|dump(?:s|ed)?|sells?|sold|moves?|moved)\s+"
                         r"(?:\$?[\d.,]+\s*(?:[kmb]n?|million|billion|thousand)?\s+(?:worth\s+of\s+|of\s+|in\s+)?)?)$",
                         re.IGNORECASE)
ECOSYSTEM_AFTER = re.compile(r"^(?:-based|\s+based|\s+(?:defi|dapp|ecosystem)\b)", re.IGNORECASE)


def _words(pattern: str, flags=re.IGNORECASE) -> re.Pattern:
    return re.compile(rf"(?<!\w)(?:{pattern})(?!\w)", flags)


_COIN_RX = {c: [_words(p) for p in ci] + [_words(re.escape(t), 0) for t in cs] for c, (ci, cs) in COINS.items()}
_EXCHANGE_RX = {e: _words(re.escape(e)) for e in EXCHANGES}
_CRITICAL_RX = {k: _words(v) for k, v in CRITICAL.items()}
_RELIEF_RX, _NEG_RX, _POS_RX = _words(LEGAL_RELIEF), _words(NEGATIVE), _words(POSITIVE)


def _is_victim(title: str, coin: str) -> bool:
    """True if at least one mention of ``coin`` is not loot ("$50M in bitcoin") or ecosystem
    ("Solana-based")."""
    for rx in _COIN_RX[coin]:
        for m in rx.finditer(title):
            if not LOOT_BEFORE.search(title[:m.start()]) and not ECOSYSTEM_AFTER.match(title[m.end():]):
                return True
    return False


def classify(title: str) -> dict:
    """Coins, exchanges, critical category and a mood score (-3 critical ... +2) of one headline."""
    coins = [c for c, rxs in _COIN_RX.items() if any(rx.search(title) for rx in rxs)]
    exchanges = [e for e, rx in _EXCHANGE_RX.items() if rx.search(title)]
    category = next((k for k, rx in _CRITICAL_RX.items() if rx.search(title)), None)
    if category == "legal" and _RELIEF_RX.search(title):
        category = None
    if category:
        # the subject of an exchange incident is the exchange, not the coins named alongside
        if exchanges and category != "delisting":
            subjects = [EXCHANGE_TOKEN[e] for e in exchanges if e in EXCHANGE_TOKEN]
        elif "?" in title or len(coins) > 2:  # opinion pieces and market round-ups
            subjects = []
        else:
            subjects = [c for c in coins if _is_victim(title, c)]
        return {"coins": coins, "exchanges": exchanges, "category": category, "subjects": subjects, "score": -3}
    mood = len(_POS_RX.findall(title)) - len(_NEG_RX.findall(title))
    return {"coins": coins, "exchanges": exchanges, "category": None, "subjects": [],
            "score": max(-2, min(2, mood))}


# --------------------------------------------------------------------------- #
# Fetching
# --------------------------------------------------------------------------- #
def _clean(text: str | None) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", "", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def _parse_time(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        ts = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            ts = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)


def parse_feed(source: str, xml_text: bytes | str) -> list[dict]:
    """Headlines of one RSS (or Atom) feed."""
    root = ET.fromstring(xml_text)
    out = []
    for node in [n for n in root.iter() if n.tag.rsplit("}", 1)[-1] in ("item", "entry")]:
        get = {}
        for child in node:  # first occurrence wins (media:title etc. come later)
            get.setdefault(child.tag.rsplit("}", 1)[-1], child)
        title = _clean(get["title"].text if "title" in get else "")
        link_node = get.get("link")
        link = (link_node.text or link_node.get("href", "")).strip() if link_node is not None else ""
        when = None
        for key in ("pubDate", "published", "updated", "date"):
            if key in get and (when := _parse_time(get[key].text)):
                break
        if title and when:
            out.append(item(source, title, link if link.startswith(("http://", "https://")) else "", when))
    return out


def item(source: str, title: str, link: str, when: datetime) -> dict:
    info = classify(title)
    key = hashlib.sha1(f"{source}|{title}".encode()).hexdigest()[:16]
    return {"id": key, "source": source, "title": title, "link": link, "time": when.isoformat(), **info,
            **fc.sentiment(title)}


def fetch_feeds(session: requests.Session, feeds: dict[str, str] = FEEDS) -> tuple[list[dict], dict]:
    items, status = [], {}
    for name, url in feeds.items():
        try:
            r = session.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            got = parse_feed(name, r.content)
            items += got
            status[name] = {"ok": True, "count": len(got)}
        except Exception as exc:  # one broken feed must not stop the others
            status[name] = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
            log.warning("News-Quelle %s nicht erreichbar: %s", name, exc)
    return items, status


def fetch_fear_greed(session: requests.Session, days: int = 30) -> list[dict]:
    r = session.get(FNG_URL, params={"limit": days}, headers=HEADERS, timeout=15)
    r.raise_for_status()
    rows = [{"time": datetime.fromtimestamp(int(x["timestamp"]), timezone.utc).isoformat(),
             "value": int(x["value"]), "label": x.get("value_classification", "")} for x in r.json()["data"]]
    return sorted(rows, key=lambda x: x["time"])


def fetch_prices(session: requests.Session, bases: list[str]) -> dict[str, float]:
    """Current USDT prices of ``bases`` (public Binance data, no key)."""
    symbols = json.dumps([f"{b}USDT" for b in bases], separators=(",", ":"))
    r = session.get(TICKER_URL, params={"symbols": symbols}, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return {x["symbol"][:-4]: float(x["price"]) for x in r.json()}


def parse_delistings(articles: list[dict]) -> list[dict]:
    """Spot delisting notices ("Binance Will Delist A, B and C on ...") - futures, margin and
    Alpha removals and pair-only removals are ignored."""
    out = []
    for a in articles:
        title = a.get("title", "")
        if not re.search(r"\bwill delist\b", title, re.I) or re.search(r"futures|margin|alpha|perpetual|options",
                                                                       title, re.I):
            continue
        coins = [c for c in COINS if re.search(rf"(?<![A-Z0-9]){c}(?![A-Z0-9])", title)]
        when = datetime.fromtimestamp(int(a["releaseDate"]) / 1000, timezone.utc)
        link = f"https://www.binance.com/en/support/announcement/detail/{a['code']}" if a.get("code") else ""
        out.append({"title": title, "time": when.isoformat(), "coins": coins, "link": link})
    return out


def fetch_binance_delistings(session: requests.Session) -> list[dict]:
    r = session.get(BINANCE_NOTICES, params={"type": 1, "catalogId": BINANCE_DELIST_CATALOG, "pageNo": 1,
                                             "pageSize": 20}, headers=HEADERS, timeout=15)
    r.raise_for_status()
    catalogs = (r.json().get("data") or {}).get("catalogs") or []
    return parse_delistings([a for c in catalogs for a in c.get("articles", [])])


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #
def load(path: Path = NEWS_PATH) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _save(cache: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(cache, indent=1))
    os.replace(tmp, path)  # atomic: the dashboard never reads a half-written file


def refresh(path: Path = NEWS_PATH, session: requests.Session | None = None, now: datetime | None = None,
            forecast_log: Path | None = None) -> dict:
    """Fetch all sources, merge with the cached history and save. Never raises for network errors."""
    session = session or requests.Session()
    now = now or datetime.now(timezone.utc)
    old = load(path) or {}
    items, status = fetch_feeds(session)
    cache = {"updated": now.isoformat(), "sources": status}
    for key, fetch in (("fear_greed", fetch_fear_greed), ("delistings", fetch_binance_delistings)):
        try:
            cache[key] = fetch(session)
            status[key] = {"ok": True, "count": len(cache[key])}
        except Exception as exc:
            cache[key] = old.get(key, [])
            status[key] = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
            log.warning("News-Quelle %s nicht erreichbar: %s", key, exc)
    if not any(s["ok"] for name, s in status.items() if name in FEEDS):
        cache["updated"] = old.get("updated")  # nothing new - keep the age of the old data honest
    # merge with the history (feeds only list their latest items), newest first, re-classified so
    # that keyword changes apply to old items too
    cutoff = now - timedelta(days=KEEP_DAYS)
    merged = {x["id"]: x for x in old.get("items", [])}
    merged.update({x["id"]: x for x in items})
    cache["items"] = sorted((item(x["source"], x["title"], x["link"], datetime.fromisoformat(x["time"]))
                             for x in merged.values() if datetime.fromisoformat(x["time"]) >= cutoff),
                            key=lambda x: x["time"], reverse=True)
    # the current assessment of every tracked coin, for readers without this module (the dashboard)
    bases = [c for c in COINS if c not in STABLECOINS]
    cache["signal"] = coin_signal(cache, bases, "binance", list(STABLECOINS), now)
    # record the forecast with today's prices (hourly) and score the ones that are 24 h old
    if path == NEWS_PATH or forecast_log is not None:
        log_path = forecast_log or FORECAST_LOG
        try:
            prices = fetch_prices(session, bases)
            fc.record(log_path, {b: c["forecast"] for b, c in cache["signal"]["coins"].items()}, prices, now)
        except Exception as exc:  # the forecast record is a nice-to-have
            log.warning("Kurse für die Prognose-Messung nicht abrufbar: %s", exc)
        cache["forecast_eval"] = fc.evaluate(log_path)
    cache["rules"] = {"min_sources": MIN_SOURCES, "sell_min_sources": SELL_MIN_SOURCES, "block_hours": BLOCK_HOURS,
                      "sell_hours": SELL_HOURS, "delist_days": DELIST_DAYS, "stale_hours": STALE_HOURS}
    _save(cache, path)
    return cache


# --------------------------------------------------------------------------- #
# Signal
# --------------------------------------------------------------------------- #
def coin_signal(cache: dict, bases: list[str], exchange: str = "binance", quote: str | list[str] | None = None,
                now: datetime | None = None) -> dict:
    """Per-coin news assessment plus alerts about the exchange and the quote currency (or currencies).

    Returns ``{"coins": {base: {...}}, "alerts": [...], "market": {...}}``; for every coin
    ``blocked`` (do not buy) and ``sell`` (sell a held position now) with a German ``reason``."""
    now = now or datetime.now(timezone.utc)
    items = [dict(x, age_h=(now - datetime.fromisoformat(x["time"])).total_seconds() / 3600)
             for x in cache.get("items", [])]
    items = [x for x in items if x["age_h"] >= -1]  # ignore items dated in the future
    forecasts = fc.coin_forecast(cache.get("items", []), bases, now)
    coins = {}
    for base in bases:
        mine = [x for x in items if (base in x["coins"] or base in x["subjects"]) and x["age_h"] <= 48]
        weights = [math.exp(-x["age_h"] / 24) for x in mine]
        mood = sum(w * x["score"] for w, x in zip(weights, mine)) / sum(weights) if mine else 0.0
        critical = [x for x in items if base in x["subjects"] and x["age_h"] <= BLOCK_HOURS]
        sources = {x["source"] for x in critical}
        info = {"mood": round(mood, 2), "headlines": len(mine), "blocked": False, "sell": False, "reason": "",
                "forecast": forecasts[base]}
        if len(sources) >= MIN_SOURCES:
            cats = sorted({x["category"] for x in critical}, key=lambda c: -sum(x["category"] == c for x in critical))
            onset = max(x["age_h"] for x in critical)
            info.update(blocked=True, sell=onset <= SELL_HOURS and len(sources) >= SELL_MIN_SOURCES,
                        reason=f"{CATEGORY_TEXT[cats[0]]} ({len(critical)} Meldungen, {len(sources)} Quellen, "
                               f"erste vor {onset:.0f} h)",
                        events=[{k: x[k] for k in ("source", "title", "link", "time")} for x in critical[:5]])
        for d in cache.get("delistings", []):
            age_h = (now - datetime.fromisoformat(d["time"])).total_seconds() / 3600
            if base in d["coins"] and age_h <= DELIST_DAYS * 24:
                info.update(blocked=True, sell=True, reason=f"Binance-Delisting angekündigt: {d['title']}")
        coins[base] = info
    alerts = []
    quotes = [quote] if isinstance(quote, str) else list(quote or [])
    watch = [(exchange.lower(), "Börse " + exchange.capitalize())] + [(q, q) for q in quotes]
    for key, label in watch:
        hits = [x for x in items if x["category"] not in (None, "delisting") and x["age_h"] <= SELL_HOURS
                and (key in x["exchanges"] or key in x["coins"])]
        if len({x["source"] for x in hits}) >= MIN_SOURCES:
            cat = CATEGORY_TEXT[hits[0]["category"]]
            first = min((x["time"] for x in items if x["category"] == hits[0]["category"]
                         and x["age_h"] <= BLOCK_HOURS and (key in x["exchanges"] or key in x["coins"])))
            alerts.append({"id": f"{key}:{hits[0]['category']}", "subject": label, "category": cat,
                           "count": len(hits), "title": hits[0]["title"], "link": hits[0]["link"],
                           "since": first})
    day = [x for x in items if x["age_h"] <= 24]
    fng = cache.get("fear_greed") or []
    market = {"mood": round(sum(x["score"] for x in day) / len(day), 2) if day else 0.0, "headlines_24h": len(day),
              "fear_greed": fng[-1] if fng else None}
    market["forecast"] = forecasts["_market"]
    return {"coins": coins, "alerts": alerts, "market": market}


@dataclass
class NewsGuard:
    """What the trading runner asks: refreshes the cache when it is older than ``max_age_minutes``."""

    exchange: str = "binance"
    quote: str | None = None
    path: Path = field(default_factory=lambda: NEWS_PATH)
    max_age_minutes: float = 30.0

    def signal(self, bases: list[str], now: datetime | None = None) -> dict | None:
        now = now or datetime.now(timezone.utc)
        cache = load(self.path)
        if age_hours(cache, now) * 60 > self.max_age_minutes:
            try:
                cache = refresh(self.path, now=now)
            except Exception as exc:
                log.warning("News konnten nicht aktualisiert werden: %s", exc)
        if age_hours(cache, now) > STALE_HOURS:
            log.warning("Keine aktuellen News (älter als %d h) - News-Filter diesmal aus.", STALE_HOURS)
            return None
        return coin_signal(cache, bases, self.exchange, self.quote, now)


def age_hours(cache: dict | None, now: datetime | None = None) -> float:
    if not cache or not cache.get("updated"):
        return math.inf
    now = now or datetime.now(timezone.utc)
    return (now - datetime.fromisoformat(cache["updated"])).total_seconds() / 3600


__all__ = ["NewsGuard", "classify", "coin_signal", "refresh", "load", "parse_feed", "parse_delistings"]
