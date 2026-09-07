from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
import pytest

from crypto_pipeline.backtest.runner import run_backtest
from crypto_pipeline.common.models import Candle
from tests.conf_test import SYMBOL


def _flat_candle(minute: int, price: str) -> Candle:
    p = Decimal(price)
    return Candle(SYMBOL, datetime(2026, 1, 1, 0, minute, tzinfo=UTC), p, p, p, p, Decimal("1"))


def _candles(closes: list[str]) -> list[Candle]:
    return [_flat_candle(i, c) for i, c in enumerate(closes)]


def test_run_backtest_round_trip():
    # buy at minute 4 (open=200) and sell at minute 6 (open=100)
    # a losing round trip.
    candles = _candles(["100", "100", "100", "200", "200", "100", "100"])

    metrics = run_backtest(
        candles,
        pd.Timedelta(minutes=1),
        Decimal("1000"),
        fast_window=2,
        slow_window=3,
    )

    assert isinstance(metrics.initial_capital, Decimal)
    assert isinstance(metrics.final_equity, Decimal)
    assert isinstance(metrics.fees_paid, Decimal)
    assert isinstance(metrics.buy_and_hold_final_equity, Decimal)
    assert isinstance(metrics.total_return, float)
    assert isinstance(metrics.max_drawdown, float)

    assert metrics.initial_capital == Decimal("1000")
    assert metrics.final_equity == Decimal("498.00349600299900")
    assert metrics.fees_paid == Decimal("1.49850199800100")
    assert metrics.trade_count == 1
    assert metrics.win_rate == pytest.approx(0.0)
    assert metrics.total_return == pytest.approx(-0.501996503997001)
    assert metrics.max_drawdown == pytest.approx(-0.501996503997001)
    assert metrics.sharpe == pytest.approx(-298.8132811163204)

    assert metrics.buy_and_hold_final_equity == Decimal("996.00699200599800")
    assert metrics.buy_and_hold_total_return == pytest.approx(-0.00399300799400204)

    assert metrics.frame_info.symbol == SYMBOL
    assert metrics.frame_info.interval == pd.Timedelta(minutes=1)
    assert metrics.frame_info.candle_count == len(candles)
    assert metrics.frame_info.start_ts == candles[0].ts
    assert metrics.frame_info.end_ts == candles[-1].ts
    assert metrics.frame_info.gap_count == 0


def test_run_backtest_no_crossover_takes_no_trades():
    candles = _candles(["100"] * 6)

    metrics = run_backtest(
        candles,
        pd.Timedelta(minutes=1),
        Decimal("1000"),
        fast_window=2,
        slow_window=3,
    )

    assert metrics.trade_count == 0
    assert metrics.win_rate is None
    assert metrics.sharpe is None
    assert metrics.final_equity == Decimal("1000")
    assert metrics.fees_paid == Decimal("0")
    assert metrics.total_return == pytest.approx(0.0)
    assert metrics.max_drawdown == pytest.approx(0.0)

    assert metrics.buy_and_hold_final_equity == Decimal("996.00699200599800")
    assert metrics.buy_and_hold_total_return == pytest.approx(-0.00399300799400204)
