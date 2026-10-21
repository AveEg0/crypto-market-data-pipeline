import asyncio
from dataclasses import asdict
from datetime import datetime
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, HTTPException, Path, Query

from crypto_pipeline.api.config import (
    BACKTEST_TIMEOUT_S,
    MAX_CONCURRENT_BACKTESTS,
    SYMBOL_PATTERN,
)
from crypto_pipeline.api.deps import ConnDep
from crypto_pipeline.api.models import (
    INTERVALS,
    RAW_INTERVAL,
    BacktestRequest,
    BacktestResponse,
    CandleInterval,
    CandlesResponse,
    Coverage,
    EquityPoint,
    FrameInfoOut,
    MetricsOut,
    SymbolsResponse,
    TradeOut,
)
from crypto_pipeline.api.queries import (
    count_candles,
    fetch_backtest_candles,
    list_candles,
    list_symbols,
)
from crypto_pipeline.backtest.frame import GapError
from crypto_pipeline.backtest.runner import run_backtest
from crypto_pipeline.common.time import to_utc

router = APIRouter(tags=["market data"])
_backtest_semaphore = asyncio.Semaphore(MAX_CONCURRENT_BACKTESTS)


@router.get("/symbols")
async def get_symbols(conn: ConnDep) -> SymbolsResponse:
    return SymbolsResponse(symbols=await list_symbols(conn))


@router.get("/candles/{symbol}")
async def get_candles(
    conn: ConnDep,
    symbol: Annotated[str, Path(pattern=SYMBOL_PATTERN)],
    start: Annotated[datetime, Query()],
    end: Annotated[datetime, Query()],
    limit: Annotated[int, Query(ge=1, le=10_000)] = 1_000,
    interval: Annotated[CandleInterval, Query()] = "1m",
) -> CandlesResponse:
    start = to_utc(start)
    end = to_utc(end)
    if start > end:
        raise HTTPException(status_code=422, detail=f"start {start} > end {end}")

    candles, truncated = await list_candles(conn, symbol, start, end, limit, interval)
    if not candles and symbol not in await list_symbols(conn):
        raise HTTPException(status_code=404, detail=f"unknown symbol {symbol}")

    return CandlesResponse(
        symbol=symbol,
        candles=candles,
        coverage=Coverage(
            start=start,
            end=end,
            expected=_expected_for_range(start, end, INTERVALS[interval].delta),
            returned=len(candles),
            truncated=truncated,
        ),
    )


@router.get("/coverage/{symbol}")
async def get_coverage(
    conn: ConnDep,
    symbol: Annotated[str, Path(pattern=SYMBOL_PATTERN)],
    start: Annotated[datetime, Query()],
    end: Annotated[datetime, Query()],
) -> Coverage:
    start = to_utc(start)
    end = to_utc(end)
    if start > end:
        raise HTTPException(status_code=422, detail=f"start {start} > end {end}")
    returned = await count_candles(conn, symbol, start, end)
    expected = _expected_for_range(start, end, INTERVALS[RAW_INTERVAL].delta)
    return Coverage(
        start=start,
        end=end,
        expected=expected,
        returned=returned,
    )


@router.post("/backtest")
async def post_backtest(
    conn: ConnDep,
    request: BacktestRequest,
) -> BacktestResponse:
    start = to_utc(request.start)
    end = to_utc(request.end)
    interval = INTERVALS[request.interval].delta
    candles = await fetch_backtest_candles(conn, request.symbol, start, end)
    if not candles:
        if request.symbol not in await list_symbols(conn):
            raise HTTPException(status_code=404, detail=f"unknown symbol {request.symbol}")
        raise HTTPException(status_code=422, detail="no candles in requested range")
    try:
        async with asyncio.timeout(BACKTEST_TIMEOUT_S):
            async with _backtest_semaphore:
                result = await asyncio.to_thread(
                    run_backtest,
                    candles=candles,
                    interval=interval,
                    initial_capital=request.initial_capital,
                    fast_window=request.fast_window,
                    slow_window=request.slow_window,
                    fee_rate=request.fee_rate,
                    slippage=request.slippage,
                    allow_gaps=request.allow_gaps,
                )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=503, detail="backtest capacity exceeded, retry shortly"
        ) from exc
    except GapError as exc:
        raise HTTPException(
            status_code=422, detail=f"gap(s) detected: count={exc.gap_count}"
        ) from exc
    frame_info = result.metrics.frame_info
    metrics = result.metrics
    simulation = result.simulation
    frame_info_out = FrameInfoOut.model_validate(
        {**asdict(frame_info), "interval": request.interval}
    )
    metrics_out = MetricsOut.model_validate({**asdict(metrics), "frame_info": frame_info_out})
    trades = [TradeOut.model_validate(t) for t in simulation.trades]
    curve = None
    if request.include_equity_curve:
        curve = [
            EquityPoint(ts=ts, equity=equity) for ts, equity in simulation.equity_curve.items()
        ]
    return BacktestResponse(metrics=metrics_out, trades=trades, equity_curve=curve)


def _expected_for_range(start: datetime, end: datetime, interval: pd.Timedelta) -> int:
    return int((end - start + interval) / interval)
