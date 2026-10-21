from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd

from crypto_pipeline.api.models import CandleOut
from crypto_pipeline.api.routes import _expected_for_range
from crypto_pipeline.common.time import to_utc

BASE = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
MINUTE = pd.Timedelta(minutes=1)
HOUR = pd.Timedelta(hours=1)


def candle(minute: int) -> CandleOut:
    return CandleOut(
        symbol="BTCUSDT",
        ts=BASE + timedelta(minutes=minute),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=Decimal("1"),
    )


#   _expected_for_range (inclusive on both ends)


def test_expected_single_minute():
    # 10:00 -> 10:00 : one candle occupies the range
    assert _expected_for_range(BASE, BASE, MINUTE) == 1


def test_expected_four_minutes():
    # 10:00, 10:01, 10:02, 10:03 -> 4 slots
    assert _expected_for_range(BASE, BASE + timedelta(minutes=3), MINUTE) == 4


def test_expected_full_hour():
    # 10:00 through 11:00 inclusive -> 60 gaps + 1 = 61 slots
    assert _expected_for_range(BASE, BASE + timedelta(hours=1), MINUTE) == 61


def test_expected_hourly_buckets():
    # 10:00 -> 13:00 inclusive at 1h = 4 buckets
    assert _expected_for_range(BASE, BASE + timedelta(hours=3), HOUR) == 4


#   to_utc


def test_to_utc_attaches_utc_to_naive():
    naive = datetime(2026, 9, 1, 12, 0)
    result = to_utc(naive)
    assert result.tzinfo == UTC
    assert result.hour == 12  # naive is assumed to already be UTC


def test_to_utc_converts_offset_aware():
    # 12:00+02:00 is 10:00 UTC
    aware = datetime(2026, 9, 1, 12, 0, tzinfo=timezone(timedelta(hours=2)))
    result = to_utc(aware)
    assert result.tzinfo == UTC
    assert result.hour == 10


def test_to_utc_leaves_utc_unchanged():
    assert to_utc(BASE) == BASE
