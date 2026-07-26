import json
from datetime import UTC, datetime
from decimal import Decimal

from crypto_pipeline.common.models import Candle


def parse_ws_candle(msg: dict) -> Candle:
    kline = msg["k"]
    if not kline["x"]:
        raise ValueError(f"unfinished kline for {kline['s']} at {kline['t']}")
    candle = Candle(
        ts=datetime.fromtimestamp(kline["t"] / 1000, tz=UTC),
        symbol=kline["s"],
        open=Decimal(kline["o"]),
        high=Decimal(kline["h"]),
        low=Decimal(kline["l"]),
        close=Decimal(kline["c"]),
        volume=Decimal(kline["v"]),
    )
    return candle


def candle_to_json(c: Candle) -> bytes:
    return json.dumps(
        {
            "symbol": c.symbol,
            "ts": c.ts.isoformat(),
            "open": str(c.open),
            "high": str(c.high),
            "low": str(c.low),
            "close": str(c.close),
            "volume": str(c.volume),
        }
    ).encode()
