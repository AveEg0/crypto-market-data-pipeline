from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from crypto_pipeline.ingester.parse import parse_ws_kline


@pytest.fixture
def sample_raw_kline():
    return {
        "e": "kline",
        "E": 1783742220000,
        "s": "BTCUSDT",
        "k": {
            "t": 1783742160000,
            "T": 1783742219999,
            "s": "BTCUSDT",
            "i": "1m",
            "o": "64183.90000000",
            "c": "64173.78000000",
            "h": "64190.00000000",
            "l": "64173.77000000",
            "v": "6.59157000",
            "n": 1365,
            "x": True,
            "q": "423091.18770620",
            "V": "2.40228000",
            "Q": "154190.62922500",
        },
    }


def test_parse_ws_kline(sample_raw_kline):
    candle = parse_ws_kline(sample_raw_kline)
    assert candle.symbol == "BTCUSDT"
    assert candle.ts == datetime(2026, 7, 11, 3, 56, tzinfo=UTC)
    assert candle.open == Decimal("64183.90000000")
    assert candle.high == Decimal("64190.00000000")
    assert candle.low == Decimal("64173.77000000")
    assert candle.close == Decimal("64173.78000000")
    assert candle.volume == Decimal("6.59157000")


def test_parse_ws_unfinished_kline(sample_raw_kline):
    msg = deepcopy(sample_raw_kline)
    msg["k"]["x"] = False
    with pytest.raises(ValueError, match="unfinished kline"):
        parse_ws_kline(msg)
