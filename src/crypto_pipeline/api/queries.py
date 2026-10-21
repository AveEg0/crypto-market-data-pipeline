from datetime import datetime

from psycopg import AsyncConnection
from psycopg.rows import class_row

from crypto_pipeline.api.models import INTERVALS, RAW_INTERVAL, CandleOut
from crypto_pipeline.common.models import Candle


async def list_symbols(conn: AsyncConnection) -> list[str]:
    async with conn.cursor() as cursor:
        await cursor.execute("SELECT DISTINCT symbol FROM candles_1m")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def list_candles(
    conn: AsyncConnection,
    symbol: str,
    start: datetime,
    end: datetime,
    limit: int,
    interval: str,
) -> tuple[list[CandleOut], bool]:
    if interval == RAW_INTERVAL:
        query = """
            SELECT symbol, ts, open, high, low, close, volume
            FROM candles_1m
            WHERE symbol = %s AND ts >= %s AND ts <= %s
            ORDER BY ts
            LIMIT %s
        """
        params = [symbol, start, end, limit + 1]
    else:
        query = """
            SELECT symbol,
                   time_bucket(%s::interval, ts) AS ts,
                   first(open, ts) AS open,
                   max(high) AS high,
                   min(low) AS low,
                   last(close, ts) AS close,
                   sum(volume) AS volume
            FROM candles_1m
            WHERE symbol = %s AND ts >= %s AND ts <= %s
            GROUP BY 1, 2
            ORDER BY 2
            LIMIT %s
        """
        params = [INTERVALS[interval].sql, symbol, start, end, limit + 1]

    async with conn.cursor(row_factory=class_row(CandleOut)) as cursor:
        await cursor.execute(query, params)
        rows = await cursor.fetchall()
        return rows[:limit], len(rows) > limit


async def count_candles(
    conn: AsyncConnection,
    symbol: str,
    start: datetime,
    end: datetime,
) -> int:
    async with conn.cursor() as cursor:
        await cursor.execute(
            "SELECT count(*) FROM candles_1m WHERE symbol = %s AND ts >= %s AND ts <= %s",
            [symbol, start, end],
        )
        row = await cursor.fetchone()
        return row[0]


async def fetch_backtest_candles(
    conn: AsyncConnection,
    symbol: str,
    start: datetime,
    end: datetime,
) -> list[Candle]:
    query = """
        SELECT symbol, ts, open, high, low, close, volume 
        FROM candles_1m 
        WHERE symbol = %s AND ts >= %s AND ts <= %s 
        ORDER BY ts
    """
    async with conn.cursor(row_factory=class_row(Candle)) as cursor:
        await cursor.execute(query, (symbol, start, end))
        return await cursor.fetchall()
