import re
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pandas import Timedelta

from crypto_pipeline.backtest.contracts import INDEX, Column, FrameInfo, PreparedData
from crypto_pipeline.backtest.frame import prepare_candles
from crypto_pipeline.common.models import Candle
from tests.conf_test import SYMBOL


def make_sample_candle(ts: datetime, *, open=Decimal("64183.9"), high=Decimal("64190.0"),
                low=Decimal("64173.77"), close=Decimal("64173.78"), volume=Decimal("6")) -> Candle:
    return Candle(SYMBOL, ts, open, high, low, close, volume)

@pytest.fixture
def healthy_sample_candles():
    sample_candles = [
        Candle(
            SYMBOL,
            datetime(2026, 7, 11, 3, 57, tzinfo=UTC),
            Decimal("64183.90000000"),
            Decimal("64190.00000000"),
            Decimal("64173.77000000"),
            Decimal("64173.78000000"),
            Decimal("6.59157000"),
        ),
        Candle(
            SYMBOL,
            datetime(2026, 7, 11, 3, 58, tzinfo=UTC),
            Decimal("64173.78000000"),
            Decimal("66473.78000000"),
            Decimal("64073.77000000"),
            Decimal("66473.78000000"),
            Decimal("4.59157000"),
        ),
        Candle(
            SYMBOL,
            datetime(2026, 7, 11, 3, 59, tzinfo=UTC),
            Decimal("66473.78000000"),
            Decimal("66490.78000000"),
            Decimal("64273.77000000"),
            Decimal("64345.78000000"),
            Decimal("2.59157000"),
        ),
    ]
    return sample_candles


@pytest.fixture
def gap_sample_candles():
    sample_candles = [
        make_sample_candle(datetime(2026, 7, 11, 3, 56, tzinfo=UTC)),
        make_sample_candle(datetime(2026, 7, 11, 3, 58, tzinfo=UTC)),
        make_sample_candle(datetime(2026, 7, 11, 3, 59, tzinfo=UTC)),
    ]
    return sample_candles


def test_prepare_candles_happy_path(healthy_sample_candles):
    prepared_data = prepare_candles(healthy_sample_candles, Timedelta(minutes=1))
    df = prepared_data.df
    assert isinstance(prepared_data, PreparedData)
    assert df.shape == (3, 5)
    assert list(df.columns) == [Column.OPEN, Column.HIGH, Column.LOW, Column.CLOSE, Column.VOLUME]
    assert df.index.name == INDEX
    assert df.index.is_monotonic_increasing
    assert str(df.index.tz) == "UTC"
    assert (df.dtypes == "float64").all()
    assert df[Column.OPEN].to_list() == pytest.approx([64183.9, 64173.78, 66473.78])

    assert len(prepared_data.prices) == 3
    assert list(prepared_data.prices) == list(df.index)
    assert all(isinstance(price, Decimal) for price in prepared_data.prices.values())
    assert prepared_data.prices[df.index[0]] == Decimal("64183.9")

    assert prepared_data.final_close == Decimal("64345.78000000")

    info = prepared_data.info
    assert isinstance(info, FrameInfo)
    assert info.symbol == SYMBOL
    assert info.candle_count == 3
    assert info.gap_count == 0
    assert info.start_ts == datetime(2026, 7, 11, 3, 57, tzinfo=UTC)
    assert info.end_ts == datetime(2026, 7, 11, 3, 59, tzinfo=UTC)


def test_prepare_candles_exception_on_gap(gap_sample_candles):
    with pytest.raises(ValueError, match=re.escape("1 gap(s) detected")):
        prepare_candles(gap_sample_candles, Timedelta(minutes=1), allow_gaps=False)


def test_prepare_candles_count_on_gap(gap_sample_candles):
    prepared_data = prepare_candles(gap_sample_candles, Timedelta(minutes=1), allow_gaps=True)
    assert prepared_data.info.gap_count == 1
    assert prepared_data.info.candle_count == 3
