import math
from decimal import Decimal

import pandas as pd

from crypto_pipeline.backtest.contracts import (
    FEE_DEFAULT,
    SLIPPAGE_DEFAULT,
    PreparedData,
    TradeRecord,
)
from crypto_pipeline.backtest.simulation import execute_buy, execute_sell


def total_return(initial: float, final: float) -> float:
    return float(final / initial) - 1

def max_drawdown(equity: pd.Series) -> float | None:
    if equity.empty:
        return None
    peak = equity.cummax()
    drawdown = (equity - peak) / peak
    return float(drawdown.min())

def sharpe(equity: pd.Series, periods_per_year: int) -> float| None:
    returns = equity.pct_change().dropna()
    sd = returns.std()
    if returns.empty or pd.isna(sd) or sd == 0:
        return None
    return float(returns.mean() / sd * math.sqrt(periods_per_year))


def win_rate(trades: list[TradeRecord]) -> float | None:
    closed = [t for t in trades if t.pnl is not None]
    if not closed:
        return None
    wins = sum(1 for t in closed if t.pnl > 0)
    return wins / len(closed)

def buy_and_hold(prepared_data: PreparedData,
                 initial_capital: Decimal, fee_rate: Decimal = FEE_DEFAULT,
                 slippage: Decimal = SLIPPAGE_DEFAULT) -> TradeRecord:
    df = prepared_data.df
    prices = prepared_data.prices
    final_close = prepared_data.final_close
    quantity, entry_fee = execute_buy(initial_capital, prices[df.index[0]], slippage, fee_rate)
    cash, fee = execute_sell(quantity, final_close, slippage, fee_rate)
    return TradeRecord(
        entry_ts=df.index[0],
        entry_price=prices[df.index[0]],
        exit_ts=df.index[-1],
        exit_price=final_close,
        fees=entry_fee + fee,
        pnl=cash - initial_capital
    )