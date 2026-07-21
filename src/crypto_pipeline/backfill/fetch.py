import time
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from crypto_pipeline.backfill.models import Candle

BASE_URL = "https://data-api.binance.vision/api/v3/klines"
QUERY_LIMIT = 1000
IP_USED_WEIGHT_HEADER = "X-MBX-USED-WEIGHT-1M"
BINANCE_IP_WEIGHT_LIMIT = 6000
TIMEOUT = 10
SLEEP_TIME = 62
MIN_IN_EPOCH = 60_000


def fetch_range(symbol: str, start: datetime, end: datetime) -> list[Candle]:
    start_ms = int(start.timestamp() * 1000)
    last_complete_ms = (int(end.timestamp() * 1000) // MIN_IN_EPOCH) * MIN_IN_EPOCH - MIN_IN_EPOCH
    candles = []
    while True:
        page = fetch_klines(symbol, start_ms, last_complete_ms)
        if not page:
            break
        candles.extend(page)
        start_ms = int(page[-1][0] + MIN_IN_EPOCH)
        if len(page) < QUERY_LIMIT or start_ms > last_complete_ms:
            break
    if candles and candles[-1][0] > last_complete_ms:
        raise RuntimeError(f"fetched an in-progress candle for {symbol}: {candles[-1][0]}")
    return [parse_kline(symbol, row) for row in candles]


def fetch_klines(
    symbol: str, start_ms: int, end_ms: int | None, limit: int = QUERY_LIMIT
) -> list[list]:
    params = {
        "symbol": symbol,
        "interval": "1m",
        "limit": limit,
        "startTime": start_ms,
    }
    if end_ms is not None:
        params["endTime"] = end_ms
    response = httpx.get(BASE_URL, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    weight = response.headers[IP_USED_WEIGHT_HEADER]
    print(f"LOG INFO: current weight = {weight}")
    if int(weight) / BINANCE_IP_WEIGHT_LIMIT >= 0.9:
        time.sleep(SLEEP_TIME)
    data = response.json()
    return data


def parse_kline(symbol: str, raw: list) -> Candle:
    ts = datetime.fromtimestamp((raw[0] / 1000), tz=UTC)
    candle = Candle(
        symbol=symbol,
        ts=ts,
        open=Decimal(raw[1]),
        high=Decimal(raw[2]),
        low=Decimal(raw[3]),
        close=Decimal(raw[4]),
        volume=Decimal(raw[5]),
    )
    return candle
