from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

import pandas as pd


class Column(StrEnum):
    OPEN = "open"
    CLOSE = "close"
    HIGH = "high"
    LOW = "low"
    VOLUME = "volume"


INDEX = "ts"
PRICE_COLUMNS = [Column.OPEN, Column.HIGH, Column.LOW, Column.CLOSE]


@dataclass(frozen=True, slots=True)
class FrameInfo:
    symbol: str
    interval: pd.Timedelta
    start_ts: datetime
    end_ts: datetime
    candle_count: int
    gap_count: int


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    initial_capital: Decimal
    final_equity: Decimal
    total_return: float
    max_drawdown: float  # negative value : -0.20 === max_drawdown=20%
    sharpe: float | None
    win_rate: float | None
    trade_count: int
    fees_paid: Decimal
    buy_and_hold_final_equity: Decimal
    buy_and_hold_total_return: float  # 1 round trip, fees included
    frame_info: FrameInfo


@dataclass(frozen=True, slots=True)
class PreparedData:
    df: pd.DataFrame
    prices: dict[datetime, Decimal]
    final_close: Decimal
    info: FrameInfo
