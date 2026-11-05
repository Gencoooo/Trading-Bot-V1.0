"""News forecast: a short-term price estimate per coin from headlines, and how well it did.

Every headline gets a sentiment score from a weighted keyword list (-3 ... +3). Per coin the
headlines of the last 48 hours are averaged (newer ones count more, half-life ~8 h) and shrunk
towards zero when there are few of them or they all come from one outlet. Headlines about the
market as a whole add a little to every coin. The result is a score from -1 to +1 and a rough
expected 24 h move (``score * EST_SCALE`` percent).

The expected move is NOT calibrated - there is no news history to fit it on. That is why every
forecast is recorded with the price (``state/news_forecasts.jsonl``, hourly) and compared with the
price 24 hours later; the hit rate is shown on the dashboard. Price recaps ("Bitcoin falls 5%")
describe what already happened and count only a little.

``tilt_weights`` lets the forecast shift the weights of a rebalance: within the coins the strategy
picked, by at most ``strength`` (0.5 = between half and one and a half times the weight), without
changing how much is invested in total and without buying anything the strategy did not pick.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

EST_SCALE = 3.0          # % expected 24 h move at score +-1 (uncalibrated guess)
WINDOW_HOURS = 48
HALF_LIFE_HOURS = 8.0
NEUTRAL = 0.15           # |score| below this is "neutral"
RECORD_EVERY_MIN = 55
HORIZON_HOURS = 24
KEEP_DAYS = 60

# (pattern, weight). Matched case-insensitively on word boundaries; every pattern counts once.
LEXICON: list[tuple[str, float]] = [
    # clearly good for a coin
    (r"etfs? (?:approval|approved|launch(?:es|ed)?|inflows?)|approves? (?:\w+ ){0,2}etfs?", 2.0),
    (r"(?:lists?|listed|listing|adds?|added)(?: \w+){0,3} on (?:coinbase|binance|robinhood|kraken|upbit)|"
     r"(?:coinbase|binance|robinhood|kraken|upbit) (?:lists?|listed|adds?|added|to list)", 1.5),
    (r"(?:replenish(?:es|ed)?|reimburs\w*|resum(?:es|ed|ing) withdrawals|recover(?:s|ed)? (?:funds|assets)|"
     r"returns? (?:the )?stolen)", 1.5),
    (r"(?:dismiss(?:es|ed)?|drops?|dropped|ends?|ended|wins?|won|settles?|settled) (?:\w+ ){0,2}"
     r"(?:lawsuit|case|charges|suit)", 1.5),
    (r"partner(?:s|ship)? with|partnership|integrat(?:es|ed|ion)|adopt(?:s|ed|ion)|"
     r"(?:taps|chooses|chose|selects|selected|picks|picked) \w+", 1.0),
    (r"(?:buys?|bought|accumulat\w*|purchase[sd]?|adds?) (?:\$?[\d.,]+\s*(?:[kmb]n?|million|billion)?\s*)?"
     r"(?:more |of |in |worth of )*(?:bitcoin|btc|ether|eth|solana|sol|xrp|bnb|tokens?|coins?)", 1.0),
    (r"inflows?", 1.0), (r"bullish|rate cuts?|stimulus", 1.0),
    (r"upgrade[sd]?|mainnet|goes live|launch(?:es|ed)?", 0.5),
    # clearly bad
    (r"hack(?:s|ed|er|ers)?|exploit(?:s|ed)?|drain(?:s|ed)?|breach(?:es|ed)?|heist|stolen", -2.0),
    (r"delist(?:s|ed|ing)?|insolven(?:t|cy)|bankrupt(?:cy)?|depeg(?:s|ged)?", -2.0),
    (r"(?:halts?|pauses?|suspends?|freezes?) (?:\w+ )?withdrawals|outage|network halt", -1.5),
    (r"sues|sued|lawsuit|charged|indict(?:ed|ment)|subpoena|probe|investigat(?:es|ed|ion)", -1.5),
    (r"bans?|banned|crackdown|scam|fraud|rug ?pull", -1.5),
    (r"outflows?|sell-?off|selling pressure|bearish|rate hikes?|dump(?:s|ed|ing)?", -1.0),
    (r"liquidat(?:ed|ions?)|unlocks?|warns?|warning|fears?|concerns?|risks?", -0.5),
    # price recaps (lagging) - also mark the headline as a recap
    (r"surge[sd]?|soar(?:s|ed)?|rall(?:y|ies|ied)|jumps?|jumped|climbs?|climbed|rebound(?:s|ed)?|"
     r"gains?|rises?|rose|record high|all-time high|new high", 0.5),
    (r"plunge[sd]?|crash(?:es|ed)?|tumble[sd]?|slump(?:s|ed)?|falls?|fell|drops?|dropped|slides?|slid|"
     r"sinks?|sank|lows?|losses", -0.5),
]
_LEX = [(re.compile(rf"(?<!\w)(?:{p})(?!\w)", re.IGNORECASE), w) for p, w in LEXICON]
# good news about an incident ("stolen funds replenished", "lawsuit dismissed") outweighs the
# incident words in the same headline: pattern index of the relief -> indices it cancels
_RELIEF = {2: (9, 10, 11), 3: (12,)}
_RECAP = re.compile(r"(?<!\w)(?:surge|soar|rall|jump|climb|rebound|gain|rise|rose|plunge|crash|tumble|slump|fall|"
                    r"fell|drop|slide|slid|sink|sank)\w*(?!\w).*?(?:\d+(?:\.\d+)?\s?%|\$[\d.,]+)|"
                    r"(?:\d+(?:\.\d+)?\s?%|\$[\d.,]+[kmb]?).*?(?<!\w)(?:surge|soar|rall|jump|climb|rebound|gain|"
                    r"rise|rose|plunge|crash|tumble|slump|fall|fell|drop|slide|slid|sink|sank)\w*", re.IGNORECASE)
_NEGATION = re.compile(r"(?<!\w)(?:no|not|denies|denied|won't|fails? to|without|despite)(?!\w)", re.IGNORECASE)


def sentiment(title: str) -> dict:
    """Score (-3 ... +3) of one headline and whether it is only a price recap."""
    hit = {i for i, (rx, _) in enumerate(_LEX) if rx.search(title)}
    for relief, cancelled in _RELIEF.items():
        if relief in hit:
            hit -= set(cancelled)
    score = sum(_LEX[i][1] for i in hit)
    if _NEGATION.search(title):
        score *= 0.5  # "not hacked", "despite the selloff": the keywords say less than usual
    return {"sentiment": round(max(-3.0, min(3.0, score)), 2), "recap": bool(_RECAP.search(title)),
            "question": "?" in title}


def _weight(x: dict) -> float:
    w = math.exp(-math.log(2) * max(x["age_h"], 0) / HALF_LIFE_HOURS)
    if x.get("recap"):
        w *= 0.3
    if x.get("question"):
        w *= 0.5
    return w


def coin_forecast(items: list[dict], bases: list[str], now: datetime) -> dict:
    """``{base: {"score", "est_pct", "direction", "confidence", "headlines"}}`` plus ``"_market"``.
    ``items`` are cache items (with ``coins``, ``subjects``, ``source``, ``time``, ``sentiment``)."""
    rows = []
    for x in items:
        age = (now - datetime.fromisoformat(x["time"])).total_seconds() / 3600
        if -1 <= age <= WINDOW_HOURS and "sentiment" in x:
            rows.append(dict(x, age_h=age))
    market = [x for x in rows if not x.get("coins") and not x.get("subjects")]
    mw = [_weight(x) for x in market]
    market_raw = sum(w * x["sentiment"] for w, x in zip(mw, market)) / (sum(mw) + 2.0)  # shrunk to 0
    out = {"_market": {"score": round(max(-1.0, min(1.0, market_raw / 3)), 3), "headlines": len(market)}}
    for base in bases:
        mine = [x for x in rows if base in (x.get("coins") or []) or base in (x.get("subjects") or [])]
        ws = [_weight(x) for x in mine]
        raw = sum(w * x["sentiment"] for w, x in zip(ws, mine)) / (sum(ws) + 1.0) if mine else 0.0
        confidence = min(1.0, len({x["source"] for x in mine}) / 3)
        score = max(-1.0, min(1.0, (raw * confidence + 0.25 * market_raw) / 3))
        out[base] = {"score": round(score, 3), "est_pct": round(score * EST_SCALE, 2),
                     "direction": "steigt" if score > NEUTRAL else "fällt" if score < -NEUTRAL else "neutral",
                     "confidence": round(confidence, 2), "headlines": len(mine)}
    return out


def tilt_weights(target: dict[str, float], scores: dict[str, float], strength: float) -> tuple[dict, dict]:
    """Shift rebalance weights by the forecast: weight * (1 + strength * score) for the coins the
    strategy picked, renormalised to the same invested total. Returns (new target, changes)."""
    picked = {s: w for s, w in target.items() if w > 0}
    if strength <= 0 or not picked:
        return dict(target), {}
    invested = sum(picked.values())
    raw = {s: w * max(0.0, 1 + strength * max(-1.0, min(1.0, scores.get(s, 0.0)))) for s, w in picked.items()}
    total = sum(raw.values())
    if total <= 0:
        return dict(target), {}
    new = dict(target)
    changes = {}
    for s, w in raw.items():
        new[s] = w / total * invested
        if abs(new[s] - target[s]) >= 0.005:
            changes[s] = [round(target[s], 4), round(new[s], 4)]
    return new, changes


# --------------------------------------------------------------------------- #
# Recording and evaluation
# --------------------------------------------------------------------------- #
def _read(path: Path) -> list[dict]:
    try:
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    except (OSError, ValueError):
        return []


def record(path: Path, forecast: dict, prices: dict[str, float], now: datetime) -> bool:
    """Append one record (at most every RECORD_EVERY_MIN minutes); drops records older than KEEP_DAYS."""
    rows = _read(path)
    if rows and now - datetime.fromisoformat(rows[-1]["time"]) < timedelta(minutes=RECORD_EVERY_MIN):
        return False
    if not prices:
        return False
    rows.append({"time": now.isoformat(), "prices": prices,
                 "f": {b: v["score"] for b, v in forecast.items() if not b.startswith("_") and b in prices}})
    cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat()
    rows = [r for r in rows if r["time"] >= cutoff]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
    tmp.replace(path)
    return True


def evaluate(path: Path, horizon_h: float = HORIZON_HOURS) -> dict:
    """How the forecasts did: each record vs the record ~``horizon_h`` later (±90 min)."""
    rows = _read(path)
    times = [datetime.fromisoformat(r["time"]) for r in rows]
    pairs = []  # (score, realised return %)
    for i, r in enumerate(rows):
        want = times[i] + timedelta(hours=horizon_h)
        j = min(range(len(rows)), key=lambda k: abs(times[k] - want), default=None)
        if j is None or j <= i or abs(times[j] - want) > timedelta(minutes=90):
            continue
        for base, score in r["f"].items():
            p0, p1 = r["prices"].get(base), rows[j]["prices"].get(base)
            if p0 and p1:
                pairs.append((score, (p1 / p0 - 1) * 100))
    calls = [(s, r) for s, r in pairs if abs(s) > NEUTRAL]
    hits = sum(1 for s, r in calls if (s > 0) == (r > 0))
    up = [r for s, r in calls if s > 0]
    down = [r for s, r in calls if s < 0]
    corr = None
    if len(pairs) >= 10:
        xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
        sy = math.sqrt(sum((y - my) ** 2 for y in ys))
        corr = round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy), 3) if sx and sy else None
    return {"pairs": len(pairs), "calls": len(calls), "hit_rate": round(hits / len(calls), 3) if calls else None,
            "avg_after_up": round(sum(up) / len(up), 3) if up else None,
            "avg_after_down": round(sum(down) / len(down), 3) if down else None,
            "avg_all": round(sum(r for _, r in pairs) / len(pairs), 3) if pairs else None,
            "corr": corr, "records": len(rows), "since": rows[0]["time"] if rows else None,
            "horizon_h": horizon_h}


__all__ = ["sentiment", "coin_forecast", "tilt_weights", "record", "evaluate"]
