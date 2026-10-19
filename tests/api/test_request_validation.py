from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from crypto_pipeline.api.config import MAX_BACKTEST_CANDLES
from crypto_pipeline.api.models import BacktestRequest
from crypto_pipeline.backtest.contracts import FEE_DEFAULT, SLIPPAGE_DEFAULT

START = datetime(2026, 9, 1, tzinfo=UTC)
END = datetime(2026, 9, 2, tzinfo=UTC)


def build(**overrides) -> BacktestRequest:
    defaults = {
        "symbol": "BTCUSDT",
        "start": START,
        "end": END,
        "initial_capital": Decimal("10000"),
        "fast_window": 10,
        "slow_window": 30,
    }
    return BacktestRequest(**{**defaults, **overrides})


def test_valid_request_builds():
    assert build().slow_window == 30


def test_defaults_applied_when_omitted():
    request = build()
    assert request.fee_rate == FEE_DEFAULT
    assert request.slippage == SLIPPAGE_DEFAULT
    assert request.allow_gaps is False
    assert request.include_equity_curve is False
    assert request.interval == "1m"


def test_fast_window_equal_to_slow_is_rejected():
    with pytest.raises(ValidationError, match="fast_window"):
        build(fast_window=30, slow_window=30)


def test_fast_window_greater_than_slow_is_rejected():
    with pytest.raises(ValidationError):
        build(fast_window=50, slow_window=30)


def test_end_before_start_is_rejected():
    with pytest.raises(ValidationError, match="end must be after start"):
        build(start=END, end=START)


def test_end_equal_to_start_is_rejected():
    with pytest.raises(ValidationError):
        build(start=START, end=START)


def test_span_over_limit_is_rejected():
    too_long = START + timedelta(minutes=MAX_BACKTEST_CANDLES + 10)
    with pytest.raises(ValidationError, match="range too large"):
        build(end=too_long)


def test_span_at_limit_is_accepted():
    at_limit = START + timedelta(minutes=MAX_BACKTEST_CANDLES)
    assert build(end=at_limit).end == at_limit


def test_fee_rate_of_one_is_rejected():
    with pytest.raises(ValidationError):
        build(fee_rate=Decimal("1"))


def test_negative_fee_rate_is_rejected():
    with pytest.raises(ValidationError):
        build(fee_rate=Decimal("-0.001"))


def test_zero_capital_is_rejected():
    with pytest.raises(ValidationError):
        build(initial_capital=Decimal("0"))


def test_lowercase_symbol_is_rejected():
    with pytest.raises(ValidationError):
        build(symbol="btcusdt")


def test_unsupported_interval_is_rejected():
    with pytest.raises(ValidationError):
        build(interval="1h")
