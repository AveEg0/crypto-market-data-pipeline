from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
import pytest

from crypto_pipeline.backtest.contracts import PERIODS_PER_YEAR_FOR_MINUTE_CANDLE, TradeRecord
from crypto_pipeline.backtest.metrics import (
    max_drawdown,
    sharpe,
    total_return,
    win_rate,
)


def _trade(pnl: Decimal | None) -> TradeRecord:
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    return TradeRecord(
        entry_ts=ts,
        exit_ts=None if pnl is None else ts,
        entry_price=Decimal("100"),
        exit_price=None if pnl is None else Decimal("110"),
        fees=Decimal("1"),
        pnl=pnl,
    )


@pytest.fixture
def drawdown_curve():
    return pd.Series([100.0, 120.0, 90.0, 95.0, 130.0, 110.0])


@pytest.fixture
def sharpe_curve():
    return pd.Series([1000.0, 1100.0, 1045.0, 1150.0, 1127.0])


def test_total_return():
    assert total_return(100.0, 150.0) == pytest.approx(0.5)


def test_max_drawdown(drawdown_curve):
    assert max_drawdown(drawdown_curve) == pytest.approx(-0.25)


def test_max_drawdown_monotonic_rise():
    assert max_drawdown(pd.Series([100.0, 110.0, 120.0])) == pytest.approx(0.0)


def test_sharpe(sharpe_curve):
    assert sharpe(
        sharpe_curve, periods_per_year=PERIODS_PER_YEAR_FOR_MINUTE_CANDLE
    ) == pytest.approx(299.2161116)


def test_sharpe_flat_equity_is_none():
    assert (
        sharpe(
            pd.Series([100.0, 100.0, 100.0]), periods_per_year=PERIODS_PER_YEAR_FOR_MINUTE_CANDLE
        )
        is None
    )


def test_win_rate_excludes_open_trades():
    trades = [
        _trade(Decimal("50")),
        _trade(Decimal("-20")),
        _trade(Decimal("30")),
        _trade(None),
    ]
    assert win_rate(trades) == pytest.approx(0.6666666)


def test_win_rate_all_open_is_none():
    assert win_rate([_trade(None)]) is None


def test_win_rate_empty_is_none():
    assert win_rate([]) is None
