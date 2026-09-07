from decimal import Decimal

import pandas as pd

from crypto_pipeline.backtest.contracts import (
    FEE_DEFAULT,
    SLIPPAGE_DEFAULT,
    BacktestMetrics,
    Column,
)
from crypto_pipeline.backtest.frame import prepare_candles
from crypto_pipeline.backtest.indicators import sma
from crypto_pipeline.backtest.metrics import (
    buy_and_hold,
    max_drawdown,
    sharpe,
    total_return,
    win_rate,
)
from crypto_pipeline.backtest.signals import sma_crossover
from crypto_pipeline.backtest.simulation import simulate
from crypto_pipeline.common.models import Candle


def run_backtest(
    candles: list[Candle],
    interval: pd.Timedelta,
    initial_capital: Decimal,
    fast_window: int,
    slow_window: int,
    *,
    fee_rate: Decimal = FEE_DEFAULT,
    slippage: Decimal = SLIPPAGE_DEFAULT,
    allow_gaps: bool = False,
) -> BacktestMetrics:
    prepared = prepare_candles(candles, interval, allow_gaps=allow_gaps)

    close = prepared.df[Column.CLOSE]
    fast = sma(close, fast_window)
    slow = sma(close, slow_window)
    position = sma_crossover(fast, slow)

    result = simulate(position, prepared, initial_capital, fee_rate, slippage)
    bh_trade = buy_and_hold(prepared, initial_capital, fee_rate, slippage)
    bh_final_equity = initial_capital + bh_trade.pnl

    periods_per_year = int(pd.Timedelta(days=365) / prepared.info.interval)

    return BacktestMetrics(
        initial_capital=initial_capital,
        final_equity=result.final_cash,
        total_return=total_return(float(initial_capital), float(result.final_cash)),
        max_drawdown=max_drawdown(result.equity_curve),
        sharpe=sharpe(result.equity_curve, periods_per_year),
        win_rate=win_rate(result.trades),
        trade_count=len(result.trades),
        fees_paid=result.total_fees,
        buy_and_hold_final_equity=bh_final_equity,
        buy_and_hold_total_return=total_return(float(initial_capital), float(bh_final_equity)),
        frame_info=prepared.info,
    )
