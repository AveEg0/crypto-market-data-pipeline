import pandas as pd

from crypto_pipeline.backtest.contracts import INDEX, Column, FrameInfo, PreparedData
from crypto_pipeline.common.models import Candle


def prepare_candles(
    candles: list[Candle], interval: pd.Timedelta, *, allow_gaps: bool = False
) -> PreparedData:

    if not candles:
        raise ValueError("candles must not be empty")
    if interval is None or interval < pd.Timedelta(0):
        raise ValueError("interval must be positive")
    symbol = candles[0].symbol
    for c in candles:
        if c.symbol != symbol:
            raise ValueError(f"mixed symbols: expected {symbol}, got {c.symbol} at {c.ts}")
        if c.high < max(c.open, c.close, c.low) or c.low > min(c.open, c.close, c.high):
            raise ValueError(f"OHLC incoherent at {c.ts}: {c.open=} {c.high=} {c.low=} {c.close=}")
        if c.volume < 0:
            raise ValueError(f"negative volume at {c.ts}: {c.volume}")
        if min(c.open, c.high, c.low, c.close) <= 0:
            raise ValueError(f"non-positive price at {c.ts}")
    rows = [
        {
            INDEX: c.ts,
            Column.OPEN: c.open,
            Column.HIGH: c.high,
            Column.LOW: c.low,
            Column.CLOSE: c.close,
            Column.VOLUME: c.volume,
        }
        for c in candles
    ]
    df = pd.DataFrame(rows)
    df[INDEX] = pd.to_datetime(df[INDEX], utc=True)
    df = df.set_index(INDEX)

    if df.index.has_duplicates:
        raise ValueError("duplicate candles")
    if not df.index.is_monotonic_increasing:
        raise ValueError("index must be monotonic increasing")
    if df.isna().any().any():
        raise ValueError("NaN values in candles")
    deltas = df.index.to_series().diff().dropna()
    gap_count = int((deltas != interval).sum())
    if gap_count and not allow_gaps:
        raise ValueError(f"{gap_count} gap(s) detected; pass allow_gaps=True to proceed")
    df = df.astype("float64")
    prices = dict(zip(df.index, (c.open for c in candles), strict=True))
    final_close = candles[-1].close
    info = FrameInfo(
        symbol=symbol,
        interval=interval,
        start_ts=df.index[0],
        end_ts=df.index[-1],
        candle_count=len(candles),
        gap_count=gap_count,
    )

    return PreparedData(df=df, info=info, prices=prices, final_close=final_close)
