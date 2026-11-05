"""News forecast: headline sentiment, per-coin estimate, weight tilt and the hit-rate measurement."""

from datetime import datetime, timedelta, timezone

import pytest

from trading_bot import forecast, live, news, notify
from trading_bot.backtest import Costs
from trading_bot.data import synthetic_ohlcv

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("title, sign", [
    ("SEC approves spot Solana ETF", 1),
    ("Coinbase lists Chainlink staking", 1),
    ("Binance says 90% of stolen assets replenished, targets Sunday withdrawals", 1),
    ("Judge dismisses lawsuit against Ripple", 1),
    ("MicroStrategy buys $500 million more bitcoin", 1),
    ("Hanwha Chooses Chainlink Data for Global Tokenization Platform", 1),
    ("Binance hit by $6.3B hack", -1),
    ("SEC sues Kraken over staking", -1),
    ("Bitcoin ETF outflows hit record as investors pull funds", -1),
    ("Polkadot faces token unlock fears", -1),
])
def test_sentiment_direction(title, sign):
    s = forecast.sentiment(title)["sentiment"]
    assert s * sign > 0


def test_recaps_and_questions_are_flagged():
    assert forecast.sentiment("Bitcoin falls 5% to $77,000")["recap"]
    assert forecast.sentiment("XRP surges 12% after court ruling")["recap"]
    assert not forecast.sentiment("SEC approves spot Solana ETF")["recap"]
    assert forecast.sentiment("Will Solana flip Ethereum?")["question"]
    assert abs(forecast.sentiment("Exchange denies it was hacked")["sentiment"]) < 2


def item(source, title, hours_ago, coins=None):
    x = news.item(source, title, "", NOW - timedelta(hours=hours_ago))
    if coins is not None:
        x["coins"] = coins
    return x


def test_coin_forecast_direction_confidence_and_decay():
    good = [item(s, "SEC approves spot Solana ETF", 1) for s in "ABC"]
    f = forecast.coin_forecast(good, ["SOL", "BTC"], NOW)
    assert f["SOL"]["direction"] == "steigt" and f["SOL"]["confidence"] == 1.0
    assert f["SOL"]["est_pct"] == pytest.approx(f["SOL"]["score"] * forecast.EST_SCALE, abs=0.01)
    assert f["BTC"]["direction"] == "neutral" and f["BTC"]["headlines"] == 0
    one_source = forecast.coin_forecast(good[:1], ["SOL"], NOW)["SOL"]["score"]
    assert 0 < one_source < f["SOL"]["score"]  # one outlet is worth less than three
    old = [item(s, "SEC approves spot Solana ETF", 40) for s in "ABC"]
    assert forecast.coin_forecast(old, ["SOL"], NOW)["SOL"]["score"] < f["SOL"]["score"]  # news fade
    gone = [item(s, "SEC approves spot Solana ETF", 60) for s in "ABC"]
    assert forecast.coin_forecast(gone, ["SOL"], NOW)["SOL"]["score"] == 0


def test_recaps_count_less_than_real_news():
    recap = [item(s, "Solana surges 15% to $250", 1) for s in "ABC"]
    real = [item(s, "Coinbase lists Solana staking", 1) for s in "ABC"]
    assert forecast.coin_forecast(recap, ["SOL"], NOW)["SOL"]["score"] < forecast.coin_forecast(real, ["SOL"], NOW)["SOL"]["score"]


def test_signal_carries_the_forecast():
    cache = {"updated": NOW.isoformat(), "items": [item(s, "SEC approves spot Solana ETF", 1) for s in "ABC"]}
    sig = news.coin_signal(cache, ["SOL"], now=NOW)
    assert sig["coins"]["SOL"]["forecast"]["direction"] == "steigt" and "forecast" in sig["market"]


def test_tilt_keeps_exposure_and_bounds():
    target = {"A": 0.4, "B": 0.4, "C": 0.0, "D": 0.0}
    new, changes = forecast.tilt_weights(target, {"A": 1.0, "B": -1.0, "C": 1.0}, 0.5)
    assert sum(new.values()) == pytest.approx(0.8)          # same amount invested
    assert new["C"] == 0 and new["D"] == 0                  # nothing the strategy did not pick
    assert new["A"] == pytest.approx(0.6) and new["B"] == pytest.approx(0.2)  # 1.5x vs 0.5x, renormalised
    assert set(changes) == {"A", "B"}
    same, none = forecast.tilt_weights(target, {"A": 1.0}, 0.0)
    assert same == target and none == {}


def test_record_and_evaluate(tmp_path):
    path = tmp_path / "f.jsonl"
    t0 = NOW - timedelta(hours=30)
    # forecast says SOL up, BTC down; afterwards SOL rose 5 %, BTC fell 2 %
    assert forecast.record(path, {"SOL": {"score": 0.6}, "BTC": {"score": -0.4}}, {"SOL": 100.0, "BTC": 50.0}, t0)
    assert not forecast.record(path, {"SOL": {"score": 0.6}}, {"SOL": 100.0}, t0 + timedelta(minutes=10))  # hourly
    forecast.record(path, {"SOL": {"score": 0.0}, "BTC": {"score": 0.0}}, {"SOL": 105.0, "BTC": 49.0},
                    t0 + timedelta(hours=24, minutes=20))
    ev = forecast.evaluate(path)
    assert ev["pairs"] == 2 and ev["calls"] == 2 and ev["hit_rate"] == 1.0
    assert ev["avg_after_up"] == pytest.approx(5.0) and ev["avg_after_down"] == pytest.approx(-2.0)


class FakeNews:
    def __init__(self, coins):
        self.coins = coins

    def signal(self, bases):
        return {"coins": {b: self.coins.get(b, {"blocked": False, "sell": False, "reason": "",
                                                "forecast": {"score": 0.0}}) for b in bases},
                "alerts": [], "market": {}}


def test_runner_tilts_rebalance_by_forecast(tmp_path, monkeypatch):
    import pandas as pd
    from trading_bot.portfolio_strategies import EqualWeightHold
    monkeypatch.setattr(live, "STATE_DIR", tmp_path)
    start = (pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=899)).strftime("%Y-%m-%d")
    data = {"AAAUSDT": synthetic_ohlcv(n=900, interval="1d", seed=11, start=start),
            "BBBUSDT": synthetic_ohlcv(n=900, interval="1d", seed=12, start=start)}
    monkeypatch.setattr(live, "fetch_klines", lambda s, *a, **k: data[s])
    monkeypatch.setattr(live, "latest_price", lambda s: float(data[s]["close"].iloc[-1]))
    good = {"blocked": False, "sell": False, "reason": "", "forecast": {"score": 1.0}}
    broker = live.PaperBroker(name="t", starting_cash=1000.0, costs=Costs(fee=0.0, slippage=0.0))
    runner = live.PortfolioBotRunner(EqualWeightHold(), list(data), "1d", broker, news=FakeNews({"AAA": good}),
                                     news_tilt=0.5)
    report = runner.step()
    bal = broker.balances()
    a = bal["AAA"] * float(data["AAAUSDT"]["close"].iloc[-1])
    b = bal["BBB"] * float(data["BBBUSDT"]["close"].iloc[-1])
    assert a == pytest.approx(600, rel=1e-3) and b == pytest.approx(400, rel=1e-3)  # 1.5:1 instead of 1:1
    assert "AAAUSDT" in report["_news_tilt"]
    assert "News-Prognose: AAAUSDT 50→60 %" in notify.format_report("P", report, "USDT")
