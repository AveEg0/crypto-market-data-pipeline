from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, model_validator

from crypto_pipeline.api.config import (
    MAX_BACKTEST_CANDLES,
    MONEY_PLACES,
    SYMBOL_PATTERN,
)
from crypto_pipeline.backtest.contracts import FEE_DEFAULT, SLIPPAGE_DEFAULT


def _quantize_money(value: Decimal) -> str:
    return str(value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP))


MoneyOut = Annotated[Decimal, PlainSerializer(_quantize_money, return_type=str)]


class SymbolsResponse(BaseModel):
    symbols: list[str]


class CandleOut(BaseModel):
    symbol: str
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class Coverage(BaseModel):
    start: datetime
    end: datetime
    expected: int
    returned: int
    truncated: bool = False


class CandlesResponse(BaseModel):
    symbol: str
    candles: list[CandleOut]
    coverage: Coverage | None = None


class FrameInfoOut(BaseModel):
    symbol: str
    interval: str
    start_ts: datetime
    end_ts: datetime
    candle_count: int
    gap_count: int


class MetricsOut(BaseModel):
    initial_capital: MoneyOut
    final_equity: MoneyOut
    total_return: float
    max_drawdown: float
    sharpe: float | None
    win_rate: float | None
    trade_count: int
    fast_window: int
    slow_window: int
    fees_paid: MoneyOut
    buy_and_hold_final_equity: MoneyOut
    buy_and_hold_total_return: float
    frame_info: FrameInfoOut


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entry_ts: datetime
    exit_ts: datetime | None
    entry_price: Decimal
    exit_price: Decimal | None
    fees: MoneyOut
    pnl: MoneyOut | None


class EquityPoint(BaseModel):
    ts: datetime
    equity: float


class BacktestRequest(BaseModel):
    symbol: Annotated[str, Field(pattern=SYMBOL_PATTERN)]
    start: datetime
    end: datetime
    interval: Literal["1m"] = "1m"
    initial_capital: Annotated[Decimal, Field(gt=0)]
    fast_window: Annotated[int, Field(ge=1)]
    slow_window: Annotated[int, Field(ge=2)]
    fee_rate: Annotated[Decimal, Field(ge=0, lt=1)] = FEE_DEFAULT
    slippage: Annotated[Decimal, Field(ge=0, lt=1)] = SLIPPAGE_DEFAULT
    allow_gaps: bool = False
    include_equity_curve: bool = False

    @model_validator(mode="after")
    def check_consistency(self) -> "BacktestRequest":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if self.fast_window >= self.slow_window:
            raise ValueError("fast_window must be less than slow_window")
        span = int((self.end - self.start) / INTERVALS[self.interval].delta)
        if span > MAX_BACKTEST_CANDLES:
            raise ValueError(f"range too large: {span} candles, max = {MAX_BACKTEST_CANDLES}")
        return self


class BacktestResponse(BaseModel):
    metrics: MetricsOut
    trades: list[TradeOut]
    equity_curve: list[EquityPoint] | None = None


@dataclass(frozen=True, slots=True)
class IntervalSpec:
    delta: pd.Timedelta
    sql: str


RAW_INTERVAL = "1m"
INTERVALS: dict[str, IntervalSpec] = {
    "1m": IntervalSpec(pd.Timedelta(minutes=1), "1 minute"),
    "1h": IntervalSpec(pd.Timedelta(hours=1), "1 hour"),
}
CandleInterval = Literal["1m", "1h"]
