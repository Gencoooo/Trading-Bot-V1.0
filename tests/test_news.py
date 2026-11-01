"""News tracker: headline classification, per-coin signal and how the runner acts on it."""

import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from trading_bot import cli, live, news, notify
from trading_bot.backtest import Costs
from trading_bot.data import synthetic_ohlcv

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def subjects(title):
    return news.classify(title)["subjects"]


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("title, expected", [
    # an exchange incident belongs to the exchange (and its token), not the coins named alongside
    ("Binance hit by $6.3B hack, the largest in cryptocurrency history", ["BNB"]),
    ("Bitcoin slides below $77,000, BNB drops amid Binance hack", ["BNB"]),
    ("Coinbase leads crypto stock selloff following $6.3B Binance hack", ["BNB"]),
    ("Bybit drained of $1.4 billion in ETH", []),                    # exchange without a token we hold
    # the coin itself is the victim
    ("Solana network suffers outage as validators stop producing blocks", ["SOL"]),
    ("SEC sues Ripple over XRP sales", ["XRP"]),
    ("Ethereum Classic hit by 51% attack", ["ETC"]),
    ("Robinhood delists Solana after SEC pressure", ["SOL"]),
    # loot, ecosystem, opinion pieces and round-ups are not the coin's problem
    ("Hacker steals $50 million in bitcoin from DeFi lender", []),
    ("Attacker launders $20M of ETH through mixer after exploit", []),
    ("Solana-based lending protocol drained of $10M", []),
    ("DeFi protocol on Ethereum exploited for $8M", []),
    ("Worried About Crypto Hacks? Buy Bitcoin Proxies in Stock Market Instead", []),
    ("Bitcoin, Ether, XRP and Solana slide as hack fears grow", []),
])
def test_critical_headlines_are_attributed_to_the_right_coin(title, expected):
    assert news.classify(title)["category"] is not None
    assert subjects(title) == expected


@pytest.mark.parametrize("title", [
    "SEC drops lawsuit against Ripple",
    "Judge dismisses lawsuit over Cardano staking",
    "Bitcoin surges to a record high as ETF inflows jump",
])
def test_good_news_is_not_critical(title):
    assert news.classify(title)["category"] is None


def test_mood_score_and_coin_names():
    assert news.classify("Bitcoin surges to record high")["score"] > 0
    assert news.classify("Bitcoin plunges as liquidations mount")["score"] < 0
    assert news.classify("Ripple effects of the selloff reach DeFi")["coins"] == []
    assert news.classify("Tether and Circle freeze stolen funds")["coins"] == ["USDT"]
    assert news.classify("Ethereum Classic rallies")["coins"] == ["ETC"]  # not ETH


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Binance hit by &lt;b&gt;$6.3B&lt;/b&gt; hack</title><link>https://example.com/a</link>
<pubDate>Sat, 31 Oct 2026 09:12:00 GMT</pubDate></item>
<item><title>No date here</title><link>https://example.com/b</link></item>
<item><title>Bad link</title><link>javascript:alert(1)</link><pubDate>Thu, 29 Oct 2026 21:00:00 +0000</pubDate></item>
</channel></rss>"""
ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Solana network halted</title><link href="https://example.com/s"/>
<updated>2026-10-30T08:00:00Z</updated></entry></feed>"""


def test_parse_rss_and_atom():
    rss = news.parse_feed("Src", RSS)
    assert [x["title"] for x in rss] == ["Binance hit by $6.3B hack", "Bad link"]
    assert rss[0]["time"] == "2026-10-31T09:12:00+00:00" and rss[0]["subjects"] == ["BNB"]
    assert rss[1]["link"] == ""  # only http(s) links reach the dashboard
    atom = news.parse_feed("Atom", ATOM)
    assert atom[0]["link"] == "https://example.com/s" and atom[0]["subjects"] == ["SOL"]


def test_parse_binance_delistings_only_spot():
    articles = [
        {"title": "Binance Will Delist IOTA, NEO on 2026-11-10", "releaseDate": 1793000000000, "code": "abc"},
        {"title": "Binance Futures Will Delist USDⓈ-M DOTUSDT Perpetual", "releaseDate": 1793000000000},
        {"title": "Binance Will Delist ETHFI Margin Pairs", "releaseDate": 1793000000000},
        {"title": "Binance Adds New Trading Pairs", "releaseDate": 1793000000000},
    ]
    out = news.parse_delistings(articles)
    assert len(out) == 1 and out[0]["coins"] == ["NEO", "IOTA"]
    assert out[0]["link"].endswith("/abc")


# --------------------------------------------------------------------------- #
# Signal
# --------------------------------------------------------------------------- #
def headline(source, title, hours_ago):
    return news.item(source, title, "https://example.com", NOW - timedelta(hours=hours_ago))


def cache_with(*items, delistings=(), fng=None):
    return {"updated": NOW.isoformat(), "items": list(items), "delistings": list(delistings),
            "fear_greed": fng or []}


def test_two_sources_block_three_sources_sell():
    two = cache_with(headline("A", "Solana network outage halts trading", 5),
                     headline("B", "Solana suffers outage", 4))
    c = news.coin_signal(two, ["SOL", "BTC"], now=NOW)["coins"]
    assert c["SOL"]["blocked"] and not c["SOL"]["sell"]
    assert not c["BTC"]["blocked"]
    assert "Netzwerk-Ausfall" in c["SOL"]["reason"]
    three = cache_with(*two["items"], headline("C", "Solana outage: validators stop producing blocks", 3))
    assert news.coin_signal(three, ["SOL"], now=NOW)["coins"]["SOL"]["sell"]


def test_single_source_and_old_events_do_nothing():
    one = cache_with(headline("A", "Solana network outage", 2), headline("A", "Solana outage update", 1))
    assert not news.coin_signal(one, ["SOL"], now=NOW)["coins"]["SOL"]["blocked"]
    old = cache_with(*(headline(s, "Solana network outage", 80) for s in "ABC"))
    assert not news.coin_signal(old, ["SOL"], now=NOW)["coins"]["SOL"]["blocked"]


def test_late_event_blocks_but_does_not_sell():
    """Once the first report is older than SELL_HOURS the price has reacted - only stop buying."""
    late = cache_with(*(headline(s, "SEC sues Ripple over XRP sales", 30 - i) for i, s in enumerate("ABC")))
    c = news.coin_signal(late, ["XRP"], now=NOW)["coins"]["XRP"]
    assert c["blocked"] and not c["sell"]


def test_official_delisting_blocks_and_sells_on_its_own():
    d = {"title": "Binance Will Delist NEO on 2026-11-10", "time": (NOW - timedelta(days=2)).isoformat(),
         "coins": ["NEO"], "link": ""}
    c = news.coin_signal(cache_with(delistings=[d]), ["NEO", "BTC"], now=NOW)["coins"]
    assert c["NEO"]["blocked"] and c["NEO"]["sell"] and "Delisting" in c["NEO"]["reason"]
    assert not c["BTC"]["blocked"]
    d["time"] = (NOW - timedelta(days=20)).isoformat()  # long done
    assert not news.coin_signal(cache_with(delistings=[d]), ["NEO"], now=NOW)["coins"]["NEO"]["blocked"]


def test_exchange_and_stablecoin_alerts():
    cache = cache_with(headline("A", "Binance hit by $6.3B hack", 3), headline("B", "Binance hack drains wallets", 2),
                       headline("A", "USDC depegs after reserve scare", 1),
                       headline("B", "USDC depeg spreads to DeFi", 1))
    sig = news.coin_signal(cache, ["BNB", "BTC"], "binance", ["USDC", "USDT"], now=NOW)
    assert {a["subject"] for a in sig["alerts"]} == {"Börse Binance", "USDC"}
    assert next(a for a in sig["alerts"] if a["subject"] == "USDC")["since"] == (NOW - timedelta(hours=1)).isoformat()
    assert sig["coins"]["BNB"]["blocked"] and not sig["coins"]["BTC"]["blocked"]


def test_market_summary():
    fng = [{"time": "2026-10-30T00:00:00+00:00", "value": 30, "label": "Fear"}]
    sig = news.coin_signal(cache_with(headline("A", "Bitcoin surges", 1), fng=fng), ["BTC"], now=NOW)
    assert sig["market"]["fear_greed"]["value"] == 30 and sig["market"]["headlines_24h"] == 1


class _Response:
    def __init__(self, content=b"", data=None, fail=False):
        self.content, self._data, self.fail = content, data, fail

    def raise_for_status(self):
        if self.fail:
            raise OSError("down")

    def json(self):
        return self._data


class _Session:
    def __init__(self, broken=()):
        self.broken = set(broken)

    def get(self, url, **kw):
        if url in self.broken:
            return _Response(fail=True)
        if url == news.FNG_URL:
            return _Response(data={"data": [{"timestamp": str(int(NOW.timestamp())), "value": "25",
                                             "value_classification": "Extreme Fear"}]})
        if url == news.BINANCE_NOTICES:
            return _Response(data={"data": {"catalogs": [{"articles": []}]}})
        return _Response(content=RSS)


def test_refresh_merges_history_and_survives_broken_sources(tmp_path):
    path = tmp_path / "news.json"
    old = {"updated": (NOW - timedelta(hours=1)).isoformat(),
           "items": [headline("Old", "Solana outage", 20), headline("Old", "Ancient news", 24 * 9)]}
    path.write_text(json.dumps(old))
    broken = {news.FEEDS["Decrypt"]}
    cache = news.refresh(path, _Session(broken), now=NOW)
    assert not cache["sources"]["Decrypt"]["ok"] and cache["sources"]["CoinDesk"]["ok"]
    titles = {x["title"] for x in cache["items"]}
    assert "Solana outage" in titles and "Ancient news" not in titles  # KEEP_DAYS
    assert cache["fear_greed"][-1]["value"] == 25
    # the stored assessment for the dashboard: every feed reports the hack -> BNB blocked + alert
    assert cache["signal"]["coins"]["BNB"]["blocked"]
    assert any(a["subject"] == "Börse Binance" for a in cache["signal"]["alerts"])
    assert json.loads(path.read_text())["updated"] == NOW.isoformat()


def test_refresh_without_any_feed_keeps_the_old_age(tmp_path):
    path = tmp_path / "news.json"
    path.write_text(json.dumps({"updated": "2026-10-30T00:00:00+00:00", "items": []}))
    cache = news.refresh(path, _Session(set(news.FEEDS.values())), now=NOW)
    assert cache["updated"] == "2026-10-30T00:00:00+00:00"


def test_guard_switches_itself_off_without_fresh_news(tmp_path, monkeypatch):
    path = tmp_path / "news.json"
    path.write_text(json.dumps({"updated": (NOW - timedelta(hours=10)).isoformat(), "items": []}))
    monkeypatch.setattr(news, "refresh", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    assert news.NewsGuard(path=path).signal(["BTC"], now=NOW) is None
    path.write_text(json.dumps({"updated": (NOW - timedelta(minutes=5)).isoformat(), "items": []}))
    assert news.NewsGuard(path=path).signal(["BTC"], now=NOW)["coins"]["BTC"]["blocked"] is False


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
class FakeNews:
    def __init__(self, coins=None, alerts=(), fail=False):
        self.coins, self.alerts, self.fail = coins or {}, list(alerts), fail

    def signal(self, bases):
        if self.fail:
            raise RuntimeError("feed parser exploded")
        return {"coins": {b: self.coins.get(b, {"blocked": False, "sell": False, "reason": ""}) for b in bases},
                "alerts": self.alerts, "market": {}}


BAD = {"blocked": True, "sell": True, "reason": "Hack/Exploit (5 Meldungen, 3 Quellen, erste vor 1 h)"}


@pytest.fixture
def market(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "STATE_DIR", tmp_path)
    start = (pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=899)).strftime("%Y-%m-%d")
    data = {"AAAUSDT": synthetic_ohlcv(n=900, interval="1d", seed=11, start=start),
            "BBBUSDT": synthetic_ohlcv(n=900, interval="1d", seed=12, start=start)}
    monkeypatch.setattr(live, "fetch_klines", lambda s, *a, **k: data[s])
    monkeypatch.setattr(live, "latest_price", lambda s: float(data[s]["close"].iloc[-1]))
    return data


def _runner(tmp_path, news_guard, name="n"):
    from trading_bot.portfolio_strategies import EqualWeightHold
    broker = live.PaperBroker(name=name, starting_cash=1000.0, costs=Costs(fee=0.0, slippage=0.0))
    return live.PortfolioBotRunner(EqualWeightHold(), ["AAAUSDT", "BBBUSDT"], "1d", broker,
                                   state_path=tmp_path / f"{name}.runner.json", news=news_guard)


def test_rebalance_skips_coins_with_critical_news(tmp_path, market):
    runner = _runner(tmp_path, FakeNews({"AAA": dict(BAD, sell=False)}))
    report = runner.step()
    bal = runner.broker.balances()
    assert bal.get("AAA", 0) == 0 and bal["BBB"] > 0
    assert bal["USDT"] == pytest.approx(500, rel=1e-6)  # AAA's half stays in cash
    assert "AAAUSDT" in report["_news_blocked"]


def test_guard_sells_held_coin_with_fresh_critical_news(tmp_path, market):
    guard = FakeNews()
    runner = _runner(tmp_path, guard)
    runner.step()  # normal rebalance into both coins
    bbb = runner.broker.balances()["BBB"]
    guard.coins = {"AAA": BAD}
    report = runner.step(guard_only=True)
    bal = runner.broker.balances()
    assert bal["AAA"] == 0 and bal["BBB"] == pytest.approx(bbb)  # only the affected coin is sold
    assert report["_news_sold"] == ["AAAUSDT"] and report["AAAUSDT"]["news"].startswith("Hack")
    again = runner.step(guard_only=True)  # nothing left to sell
    assert not again.get("_news_sold") and runner.broker.balances()["BBB"] == pytest.approx(bbb)


def test_guard_without_news_does_nothing(tmp_path, market):
    runner = _runner(tmp_path, FakeNews())
    runner.step()
    before = runner.broker.balances()
    report = runner.step(guard_only=True)
    assert runner.broker.balances() == before and report["_news_ok"] and not report["_rebalanced"]


def test_broken_news_never_stops_trading(tmp_path, market):
    runner = _runner(tmp_path, FakeNews(fail=True))
    report = runner.step()
    assert report["_rebalanced"] and not report["_news_ok"]
    assert runner.broker.balances()["AAA"] > 0 and runner.broker.balances()["BBB"] > 0


def test_exchange_alert_is_reported_once_a_day(tmp_path, market):
    alert = {"id": "binance:hack", "subject": "Börse Binance", "category": "Hack/Exploit", "count": 9,
             "title": "Binance hit by hack", "link": "", "since": NOW.isoformat()}
    runner = _runner(tmp_path, FakeNews(alerts=[alert]))
    assert runner.step(guard_only=True)["_news_alerts"] == [alert]
    assert runner.step(guard_only=True)["_news_alerts"] == []
    assert runner.broker.balances()["USDT"] == 1000.0  # an exchange alert alone never trades


def test_account_lock_lets_one_run_at_a_time(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "STATE_DIR", tmp_path)
    with live.account_lock("acc") as first:
        assert first
        with live.account_lock("acc", wait=False) as second:
            assert not second
        with live.account_lock("other", wait=False) as other:
            assert other
    with live.account_lock("acc", wait=False) as later:
        assert later


def test_guard_snapshot_keeps_the_daily_report(tmp_path, market):
    runner = _runner(tmp_path, FakeNews())
    path = tmp_path / "n.snapshot.json"
    live.save_snapshot(path, runner.broker, runner.symbols, runner.step(), name="n", news=True)
    daily = json.loads(path.read_text())
    live.save_snapshot(path, runner.broker, runner.symbols, runner.step(guard_only=True), guard_only=True, news=True)
    snap = json.loads(path.read_text())
    assert snap["last_report"] == daily["last_report"] and snap.get("log") == daily.get("log")
    assert snap["guard"]["news_ok"] and len(snap["equity"]) == 2


def test_equity_history_is_compacted_not_cut():
    now = datetime(2026, 10, 31, tzinfo=timezone.utc)
    pts = [{"time": (now - timedelta(minutes=15 * i)).isoformat(), "equity": float(i)} for i in range(96 * 40)][::-1]
    out = live._compact_equity(pts, now)
    assert out[0]["time"][:10] == pts[0]["time"][:10]          # the oldest day survives
    assert len(out) < 96 * 15 + 30 and out[-1] == pts[-1]
    assert [p["time"] for p in out] == sorted(p["time"] for p in out)


# --------------------------------------------------------------------------- #
# Notifications and CLI
# --------------------------------------------------------------------------- #
def test_notification_explains_news_trades_and_alerts():
    report = {"_equity": 160.0, "_news_sold": ["BNBUSDC"],
              "BNBUSDC": {"target": 0.0, "was": 0.27, "action": "sell", "news": "Hack/Exploit (3 Quellen)"},
              "_news_alerts": [{"subject": "Börse Binance", "category": "Hack/Exploit", "count": 40,
                                "title": "Binance hit by $6.3B hack"}],
              "_news_blocked": {"SOLUSDC": "Netzwerk-Ausfall"}}
    text = notify.format_report("LIVE", report, "USDC")
    assert "Verkauf BNBUSDC wegen News: Hack/Exploit" in text
    assert "News-Warnung Börse Binance" in text and "SOLUSDC wegen News nicht gekauft" in text
    assert notify.format_report("LIVE", {"_equity": 1.0, "_news_ok": True}, "USDC") is None  # quiet guard run


def test_guard_summary_line():
    assert "verkauft: BNBUSDC" in cli._guard_summary({"_news_ok": True, "_news_sold": ["BNBUSDC"], "_failed": []})
    assert "nichts geprüft" in cli._guard_summary({"_news_ok": False})
    assert "keine kritischen" in cli._guard_summary({"_news_ok": True})


def test_guard_only_needs_news_and_once():
    with pytest.raises(SystemExit, match="--guard-only braucht"):
        cli.main(["paper", "--strategy", "rotation_bot_v1", "--guard-only"])
    with pytest.raises(SystemExit, match="nur für Portfolio"):
        cli.main(["paper", "--strategy", "golden_cross_50_200", "--news", "--once"])


def test_value_with_missing_prices_is_not_recorded(tmp_path, market, monkeypatch):
    """A network outage must not draw a fake crash into the value history."""
    runner = _runner(tmp_path, FakeNews())
    path = tmp_path / "n.snapshot.json"
    live.save_snapshot(path, runner.broker, runner.symbols, runner.step(), news=True)
    good = float(market["AAAUSDT"]["close"].iloc[-1])
    monkeypatch.setattr(live, "latest_price", lambda s: good if s == "AAAUSDT" else (_ for _ in ()).throw(OSError("dns")))
    report = runner.step(guard_only=True)
    assert not report["_equity_complete"]
    live.save_snapshot(path, runner.broker, runner.symbols, report, guard_only=True, news=True)
    assert len(json.loads(path.read_text())["equity"]) == 1


def test_telegram_wrapper_passes_guard_only_through(tmp_path, market, monkeypatch):
    """Live runs have Telegram on: the notification wrapper must not break the news guard."""
    monkeypatch.setattr(notify, "_post", lambda token, method, **data: {})
    guard = FakeNews()
    runner = _runner(tmp_path, guard)
    runner.step()
    guard.coins = {"AAA": BAD}
    cli._notify_each_step(runner, notify.Notifier("LIVE", "t", "c"), "USDT")
    report = runner.step(guard_only=True)
    assert report["_news_sold"] == ["AAAUSDT"]
