from datetime import UTC, datetime
from decimal import Decimal

from crypto_pipeline.common.models import Candle


def parse_ws_kline(msg: dict) -> Candle:
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
