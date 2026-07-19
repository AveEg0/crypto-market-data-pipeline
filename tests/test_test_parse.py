from datetime import UTC, datetime
from decimal import Decimal

import pytest

from crypto_pipeline.backfill.fetch import parse_kline

SYMBOL = "BTCUSDT"

@pytest.fixture
def sample_raw_candle():
    return [1783742160000, '64183.90000000', '64190.00000000', '64173.77000000', '64173.78000000',
            '6.59157000', 1783742219999, '423091.18770620', 1365, '2.40228000', '154190.62922500',
            '0']

def test_parse_candle(sample_raw_candle):
    candle = parse_kline(SYMBOL, sample_raw_candle)
    assert candle.symbol == SYMBOL
    assert candle.ts == datetime(2026, 7, 11, 3, 56, tzinfo=UTC)
    assert candle.open == Decimal('64183.90000000')
    assert candle.high == Decimal('64190.00000000')
    assert candle.low == Decimal('64173.77000000')
    assert candle.close == Decimal('64173.78000000')
    assert candle.volume == Decimal('6.59157000')
