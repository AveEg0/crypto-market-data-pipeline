import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx

from crypto_pipeline.backfill.models import Candle

BASE_URL = "https://data-api.binance.vision/api/v3/klines"
QUERY_LIMIT = 1000
IP_USED_WEIGHT_HEADER = "X-MBX-USED-WEIGHT-1M"
BINANCE_IP_WEIGHT_LIMIT = 6000
TIMEOUT = 10
SLEEP_TIME = 62


def fetch_range(symbol: str, start: datetime, end: datetime) -> list[Candle]:
    start_ms = int(start.timestamp() * 1000)
    end_ms = (end.timestamp() * 1000) + 60_000 # adding a minute for including the last candle
    candles = []
    while True:
        page = fetch_klines(symbol, start_ms, int(end_ms))
        if not page:
            break
        candles.extend(page)
        start_ms = int(page[-1][0] + 60_000)
        if len(page) < QUERY_LIMIT or start_ms > end_ms:
            break
    return [parse_kline(symbol, row) for row in candles]


def fetch_klines(symbol: str, start_ms: int, end_ms: int | None,
                 limit: int = QUERY_LIMIT) -> list[list]:
    params = {
        "symbol": symbol, "interval": "1m", "limit": limit, "startTime": start_ms,
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
    candle = Candle(symbol=symbol, ts=ts, open=Decimal(raw[1]), high=Decimal(raw[2]),
                    low=Decimal(raw[3]), close=Decimal(raw[4]), volume=Decimal(raw[5]))
    return candle

def main() -> None:
    time0 = time.perf_counter()
    symbol = "BTCUSDT"
    end = datetime.now(UTC)
    start = end - timedelta(days=7)
    candles = fetch_range(symbol, start, end)
    print(f"{len(candles)} candles")
    print(candles[0])
    print(candles[-1])
    print(len(candles) == len({c.ts for c in candles}))
    print(f"time performance = {time.perf_counter() - time0}")

if __name__ == "__main__":
    main()