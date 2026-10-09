"""Market data: download, cache and load OHLCV candles.

Primary source is Binance's public market-data API (no API key needed).
``data-api.binance.vision`` is Binance's official public mirror and works in
regions where ``api.binance.com`` is geo-blocked.

Candles are cached as gzipped CSV files under ``data/cache`` and updated
incrementally, so repeated backtests do not hit the network.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BINANCE_ENDPOINTS = (
    "https://data-api.binance.vision/api/v3/klines",
    "https://api.binance.com/api/v3/klines",
)

INTERVAL_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480, "12h": 720,
    "1d": 1440, "3d": 4320, "1w": 10080,
}

# Universe used for the benchmark. It deliberately mixes long-term survivors with
# coins that faded or were delisted (EOS, MATIC, WAVES) to reduce survivorship bias.
DEFAULT_UNIVERSE = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "SOLUSDT", "DOGEUSDT", "LTCUSDT", "LINKUSDT", "TRXUSDT",
    "XLMUSDT", "ETCUSDT", "EOSUSDT", "NEOUSDT", "IOTAUSDT",
    "AVAXUSDT", "BCHUSDT", "DOTUSDT", "MATICUSDT", "WAVESUSDT",
)

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume", "quote_volume", "trades"]


def interval_to_timedelta(interval: str) -> pd.Timedelta:
    return pd.Timedelta(minutes=INTERVAL_MINUTES[interval])


def bars_per_year(interval: str) -> float:
    return 365.0 * 24 * 60 / INTERVAL_MINUTES[interval]


def _to_utc(ts) -> pd.Timestamp:
    ts = pd.Timestamp(ts)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def _to_ms(ts) -> int:
    if isinstance(ts, (int, np.integer)):
        return int(ts)
    return int(_to_utc(ts).timestamp() * 1000)


def fetch_klines(
    symbol: str,
    interval: str,
    start=None,
    end=None,
    session: requests.Session | None = None,
    limit: int = 1000,
    pause: float = 0.05,
    max_retries: int = 5,
) -> pd.DataFrame:
    """Download candles from Binance (paginated). Returns only *closed* candles."""
    if interval not in INTERVAL_MINUTES:
        raise ValueError(f"unknown interval {interval!r}")
    session = session or requests.Session()
    step_ms = INTERVAL_MINUTES[interval] * 60_000
    start_ms = _to_ms(start) if start is not None else 0
    end_ms = _to_ms(end) if end is not None else int(time.time() * 1000)

    rows: list[list] = []
    cursor = start_ms
    while cursor < end_ms:
        params = {"symbol": symbol, "interval": interval, "startTime": cursor,
                  "endTime": end_ms, "limit": limit}
        batch = _get_with_retries(session, params, max_retries)
        if not batch:
            break
        rows.extend(batch)
        last_open = batch[-1][0]
        if len(batch) < limit:
            break
        cursor = last_open + step_ms
        time.sleep(pause)

    if not rows:
        return _empty_frame()

    df = pd.DataFrame(rows, columns=[
        "open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
    ])
    # Drop the still-forming candle: its close_time lies in the future.
    now_ms = int(time.time() * 1000)
    df = df[df["close_time"] < now_ms]
    return _normalize(df)


def _get_with_retries(session: requests.Session, params: dict, max_retries: int) -> list:
    last_error: Exception | None = None
    for endpoint in BINANCE_ENDPOINTS:
        for attempt in range(max_retries):
            try:
                resp = session.get(endpoint, params=params, timeout=30)
                if resp.status_code in (418, 429):  # rate limited -> back off
                    time.sleep(2 ** attempt)
                    continue
                if resp.status_code in (403, 451):  # geo-blocked endpoint -> try next
                    break
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                time.sleep(2 ** attempt)
    raise RuntimeError(f"could not download klines for {params}: {last_error}")


def _empty_frame() -> pd.DataFrame:
    idx = pd.DatetimeIndex([], tz="UTC", name="time")
    return pd.DataFrame(columns=OHLCV_COLUMNS, index=idx, dtype=float)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    ts = df["open_time"].astype("int64")
    # Binance bulk files switched to microsecond timestamps in 2025.
    ts = np.where(ts > 10**14, ts // 1000, ts)
    out = pd.DataFrame({c: pd.to_numeric(df[c], errors="coerce") for c in OHLCV_COLUMNS})
    out.index = pd.to_datetime(ts, unit="ms", utc=True)
    out.index.name = "time"
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out.dropna(subset=["open", "high", "low", "close"])


def cache_path(symbol: str, interval: str, cache_dir: Path | str = DEFAULT_CACHE_DIR) -> Path:
    return Path(cache_dir) / f"{symbol}-{interval}.csv.gz"


def read_cache(symbol: str, interval: str, cache_dir: Path | str = DEFAULT_CACHE_DIR) -> pd.DataFrame:
    path = cache_path(symbol, interval, cache_dir)
    if not path.exists():
        return _empty_frame()
    df = pd.read_csv(path, index_col="time", parse_dates=["time"])
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


def load_ohlcv(
    symbol: str,
    interval: str,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    update: bool = False,
    start=None,
    end=None,
) -> pd.DataFrame:
    """Load candles from the local cache, optionally downloading what is missing."""
    df = read_cache(symbol, interval, cache_dir)
    if update or df.empty:
        fetch_from = df.index[-1] + interval_to_timedelta(interval) if not df.empty else start
        new = fetch_klines(symbol, interval, start=fetch_from)
        if not new.empty:
            df = pd.concat([df, new])
            df = df[~df.index.duplicated(keep="last")].sort_index()
            path = cache_path(symbol, interval, cache_dir)
            path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(path, compression="gzip", float_format="%.10g")
    if start is not None:
        df = df[df.index >= _to_utc(start)]
    if end is not None:
        df = df[df.index < _to_utc(end)]
    return df


def synthetic_ohlcv(
    n: int = 2000,
    interval: str = "1d",
    seed: int = 0,
    start: str = "2018-01-01",
    drift: float = 0.0004,
    vol: float = 0.035,
    regimes: bool = True,
) -> pd.DataFrame:
    """Random-walk OHLCV with optional trending/ranging regimes (for tests & demos)."""
    rng = np.random.default_rng(seed)
    mu = np.full(n, drift)
    if regimes:
        regime_len = max(n // 8, 20)
        for k in range(0, n, regime_len):
            mu[k:k + regime_len] = rng.choice([-1.5, 0.0, 1.5]) * vol / 8
    rets = mu + vol * rng.standard_t(df=4, size=n) / np.sqrt(2)
    close = 100 * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[100.0], close[:-1]]) * np.exp(rng.normal(0, vol / 10, n))
    spread = np.abs(rng.normal(0, vol / 2, n))
    high = np.maximum(open_, close) * np.exp(spread / 2)
    low = np.minimum(open_, close) * np.exp(-spread / 2)
    volume = rng.lognormal(10, 0.5, n) * (1 + 5 * np.abs(rets))
    idx = pd.date_range(start, periods=n, freq=interval_to_timedelta(interval), tz="UTC", name="time")
    return pd.DataFrame({
        "open": open_, "high": high, "low": low, "close": close, "volume": volume,
        "quote_volume": volume * close, "trades": (volume / 10).astype(int),
    }, index=idx)
