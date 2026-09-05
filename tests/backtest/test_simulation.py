from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
import pytest

from crypto_pipeline.backtest.frame import prepare_candles
from crypto_pipeline.backtest.simulation import simulate
from crypto_pipeline.common.models import Candle
from tests.conf_test import SYMBOL


def _candle(minute: int, o: str, h: str, low: str, c: str) -> Candle:
    return Candle(
        SYMBOL,
        datetime(2026, 1, 1, 0, minute, tzinfo=UTC),
        Decimal(o),
        Decimal(h),
        Decimal(low),
        Decimal(c),
        Decimal("1"),
    )


@pytest.fixture
def trip_data():
    candles = [
        _candle(0, "100", "110", "90", "100"),
        _candle(1, "100", "200", "95", "200"),
        _candle(2, "200", "210", "190", "200"),
    ]
    return prepare_candles(candles, pd.Timedelta(minutes=1))


@pytest.fixture
def round_trip_position(trip_data):
    return pd.Series([0, 1, 0], index=trip_data.df.index, dtype="int64")


@pytest.fixture
def open_trip_position(trip_data):
    return pd.Series([0, 1, 1], index=trip_data.df.index, dtype="int64")


def test_simulate_round_trip(trip_data, round_trip_position):
    result = simulate(
        round_trip_position,
        trip_data,
        initial_capital=Decimal("1000"),
        fee_rate=Decimal("0.001"),
        slippage=Decimal("0.001"),
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_ts == datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    assert trade.exit_ts == datetime(2026, 1, 1, 0, 2, tzinfo=UTC)
    assert trade.entry_price == Decimal("100")
    assert trade.exit_price == Decimal("200")

    assert trade.fees == Decimal("2.994007992004")
    assert trade.pnl == Decimal("992.013984011996")
    assert result.total_fees == Decimal("2.994007992004")
    assert result.final_cash == Decimal("1992.013984011996")

    assert result.equity_curve.iloc[0] == pytest.approx(1000.0)
    assert result.equity_curve.iloc[1] == pytest.approx(1996.003996)
    assert result.equity_curve.iloc[2] == pytest.approx(1992.013984011996)

    assert float(result.final_cash) == pytest.approx(result.equity_curve.iloc[-1])


def test_simulate_open_trade_trip(trip_data, open_trip_position):
    result = simulate(
        open_trip_position,
        trip_data,
        initial_capital=Decimal("1000"),
        fee_rate=Decimal("0.001"),
        slippage=Decimal("0.001"),
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_ts == datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    assert trade.exit_ts is None
    assert trade.entry_price == Decimal("100")
    assert trade.exit_price is None

    assert trade.fees == Decimal("1.0")
    assert trade.pnl is None
    assert result.total_fees == Decimal("1.0")
    assert result.final_cash == Decimal("1996.003996")

    assert result.equity_curve.iloc[0] == pytest.approx(1000.0)
    assert result.equity_curve.iloc[1] == pytest.approx(1996.003996)
    assert result.equity_curve.iloc[2] == pytest.approx(1996.003996)

    assert float(result.final_cash) == pytest.approx(result.equity_curve.iloc[-1])
