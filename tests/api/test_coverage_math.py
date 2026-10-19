from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

from crypto_pipeline.api.models import CandleOut
from crypto_pipeline.api.routes import _coverage, _expected_for_range
from crypto_pipeline.common.time import to_utc

BASE = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)


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
    assert _expected_for_range(BASE, BASE) == 1


def test_expected_four_minutes():
    # 10:00, 10:01, 10:02, 10:03 -> 4 slots
    assert _expected_for_range(BASE, BASE + timedelta(minutes=3)) == 4


def test_expected_full_hour():
    # 10:00 through 11:00 inclusive -> 60 gaps + 1 = 61 slots
    assert _expected_for_range(BASE, BASE + timedelta(hours=1)) == 61


#   _coverage


def test_coverage_empty_is_none():
    assert _coverage([], truncated=False) is None


def test_coverage_complete_range():
    # 10:00, 10:01, 10:02 : expected 3, returned 3, no gap
    result = _coverage([candle(0), candle(1), candle(2)], truncated=False)
    assert result.start == BASE
    assert result.end == BASE + timedelta(minutes=2)
    assert result.expected == 3
    assert result.returned == 3
    assert result.truncated is False


def test_coverage_detects_single_gap():
    # 10:00, 10:01, 10:03 : 10:02 missing
    # span 10:00 -> 10:03 = 3 min + 1 = 4 expected, 3 returned
    result = _coverage([candle(0), candle(1), candle(3)], truncated=False)
    assert result.expected == 4
    assert result.returned == 3
    assert result.expected - result.returned == 1


def test_coverage_detects_multiple_gaps():
    # 10:00, 10:01, 10:05 : 10:02, 10:03, 10:04 missing
    # span = 5 min + 1 = 6 expected, 3 returned
    result = _coverage([candle(0), candle(1), candle(5)], truncated=False)
    assert result.expected == 6
    assert result.returned == 3
    assert result.expected - result.returned == 3


def test_coverage_truncated_flag_passes_through():
    result = _coverage([candle(0), candle(1)], truncated=True)
    assert result.truncated is True
    assert result.expected == 2


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
