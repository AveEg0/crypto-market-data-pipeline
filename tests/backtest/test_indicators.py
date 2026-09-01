import pandas as pd
import pytest
from pandas._testing import assert_series_equal

from crypto_pipeline.backtest.indicators import rsi, sma


@pytest.fixture
def sma_sample_values():
    return pd.Series([10, 20, 30, 40, 50])


@pytest.fixture
def rsi_sample_values():
    return pd.Series([10, 12, 11, 14])


def test_sma(sma_sample_values):
    smas = sma(sma_sample_values, window=3)
    expected = pd.Series([float("nan"), float("nan"), 20.0, 30.0, 40.0])
    assert smas.equals(expected)


def test_rsi(rsi_sample_values):
    rsis = rsi(rsi_sample_values, window=2)
    expected = pd.Series([float("nan"), float("nan"), 200 / 3, 800 / 9])
    assert_series_equal(rsis, expected)
