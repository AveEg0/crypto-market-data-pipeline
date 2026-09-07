from datetime import datetime

import psycopg

from crypto_pipeline.common.config import get_database_url
from crypto_pipeline.common.models import Candle


def read_candles(symbol: str, start: datetime, end: datetime) -> list[Candle]:
    with psycopg.connect(get_database_url(), connect_timeout=5) as conn:
        with conn.cursor() as cur:
            rows = cur.execute(
                """
                SELECT symbol, ts, open, high, low, close, volume
                FROM candles_1m
                WHERE symbol = %s AND ts >= %s AND ts < %s
                ORDER BY ts
                """,
                (symbol, start, end),
            ).fetchall()
    return [Candle(*row) for row in rows]
