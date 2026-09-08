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
    CASH = "cash"
    QUANTITY = "quantity"


INDEX = "ts"
PRICE_COLUMNS = [Column.OPEN, Column.HIGH, Column.LOW, Column.CLOSE]
FEE_DEFAULT = Decimal("0.001")
SLIPPAGE_DEFAULT = Decimal("0.001")
DEFAULT_GRID = [
    (60, 480),
    (60, 1440),
    (240, 1440),
    (240, 2880),
    (500, 2000),
    (500, 7200),
    (1440, 7200),
    (1440, 20160),
]
MIN_TRADES_FOR_ELIGIBILITY = 5


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


@dataclass(frozen=True, slots=True)
class TradeRecord:
    entry_ts: datetime
    exit_ts: datetime | None
    entry_price: Decimal
    exit_price: Decimal | None
    fees: Decimal
    pnl: Decimal | None


@dataclass(frozen=True, slots=True)
class SimulationResult:
    trades: list[TradeRecord]
    equity_curve: pd.Series
    final_cash: Decimal
    total_fees: Decimal


@dataclass(frozen=True, slots=True)
class SweepResult:
    fast_window: int
    slow_window: int
    in_sample: BacktestMetrics
    out_of_sample: BacktestMetrics
    ranked_in_sample: list[tuple[int, int, BacktestMetrics]]
