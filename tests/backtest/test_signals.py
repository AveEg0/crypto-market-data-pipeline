import pandas as pd
import pytest
from pandas._testing import assert_series_equal

from crypto_pipeline.backtest.indicators import sma
from crypto_pipeline.backtest.signals import sma_crossover


@pytest.fixture
def sma_crossover_sample():
    return (
        pd.Series([10, 9, 8, 7, 6, 12, 14, 16], dtype="int64"),
        pd.Series([10, 12, 14, 16, 18, 11, 9, 7], dtype="int64"),
    )


def test_sma_crossover(sma_crossover_sample):
    first_set, second_set = sma_crossover_sample
    first_expected = pd.Series([0, 0, 0, 0, 0, 0, 0, 1])
    second_expected = pd.Series([0, 0, 0, 0, 0, 1, 1, 0])
    first_fast_sma = sma(first_set, window=3)
    first_slow_sma = sma(first_set, window=5)
    second_fast_sma = sma(second_set, window=3)
    second_slow_sma = sma(second_set, window=5)
    first_result = sma_crossover(first_fast_sma, first_slow_sma)
    second_result = sma_crossover(second_fast_sma, second_slow_sma)

    assert_series_equal(first_result, first_expected)
    assert_series_equal(second_result, second_expected)
