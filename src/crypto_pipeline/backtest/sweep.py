from decimal import Decimal

import pandas as pd

from crypto_pipeline.backtest.contracts import (
    DEFAULT_GRID,
    FEE_DEFAULT,
    MIN_TRADES_FOR_ELIGIBILITY,
    SLIPPAGE_DEFAULT,
    BacktestMetrics,
    SweepResult,
)
from crypto_pipeline.backtest.runner import run_backtest
from crypto_pipeline.common.models import Candle


def split_chronological(
    candles: list[Candle], ratio: float = 0.7
) -> tuple[list[Candle], list[Candle]]:
    split_index = int(len(candles) * ratio)
    return candles[:split_index], candles[split_index:]


def run_sweep(
    candles: list[Candle],
    interval: pd.Timedelta,
    initial_capital: Decimal,
    *,
    grid: list[tuple[int, int]] = DEFAULT_GRID,
    ratio: float = 0.7,
    fee_rate: Decimal = FEE_DEFAULT,
    slippage: Decimal = SLIPPAGE_DEFAULT,
    allow_gaps: bool = False,
) -> SweepResult:
    is_candles, oos_candles = split_chronological(candles, ratio)

    def _run(segment: list[Candle], fast: int, slow: int) -> BacktestMetrics:
        return run_backtest(
            candles=segment,
            interval=interval,
            initial_capital=initial_capital,
            fast_window=fast,
            slow_window=slow,
            fee_rate=fee_rate,
            slippage=slippage,
            allow_gaps=allow_gaps,
        )

    ranked = []
    for fast, slow in grid:
        if fast >= slow or slow > len(is_candles):
            continue
        ranked.append((fast, slow, _run(is_candles, fast, slow)))

    if not ranked:
        raise ValueError("no parameter combination fits the in-sample segment")

    eligible = [
        r
        for r in ranked
        if r[2].sharpe is not None and r[2].trade_count >= MIN_TRADES_FOR_ELIGIBILITY
    ]
    if not eligible:
        raise ValueError(
            f"no combination produced a Sharpe with >= {MIN_TRADES_FOR_ELIGIBILITY} trades"
        )

    ranked.sort(key=lambda r: (r[2].sharpe is not None, r[2].sharpe or 0.0), reverse=True)
    best_fast, best_slow, best_is = max(eligible, key=lambda r: r[2].sharpe)

    oos = _run(oos_candles, best_fast, best_slow)

    return SweepResult(
        fast_window=best_fast,
        slow_window=best_slow,
        in_sample=best_is,
        out_of_sample=oos,
        ranked_in_sample=ranked,
    )
