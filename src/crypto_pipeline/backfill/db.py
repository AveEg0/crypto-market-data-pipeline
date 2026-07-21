from dataclasses import astuple

import psycopg

from crypto_pipeline.backfill.models import Candle
from crypto_pipeline.common.config import get_database_url


def insert_candles(candles: list[Candle]) -> int:
    with psycopg.connect(get_database_url()) as conn:
        with conn.cursor() as cur:
            start_count = cur.execute("SELECT COUNT(*) FROM candles_1m;").fetchone()[0]
            cur.execute("""
            CREATE TEMP TABLE candles_stage (LIKE candles_1m INCLUDING DEFAULTS) ON COMMIT DROP;
            """)
            with cur.copy(
                "COPY candles_stage (symbol, ts, open, high, low, close, volume) FROM STDIN"
            ) as copy:
                for candle in candles:
                    copy.write_row(astuple(candle))
            cur.execute("""
            INSERT INTO candles_1m (symbol, ts, open, high, low, close, volume)
            SELECT symbol, ts, open, high, low, close, volume FROM candles_stage
            ON CONFLICT (symbol, ts) DO NOTHING""")
            end_count = cur.execute("SELECT COUNT(*) FROM candles_1m;").fetchone()[0]
    return end_count - start_count
