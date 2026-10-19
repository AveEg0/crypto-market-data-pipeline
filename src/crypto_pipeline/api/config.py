import os
from datetime import timedelta
from decimal import Decimal

import pandas as pd

HOST = os.getenv("API_HOST", "127.0.0.1")
PORT = int(os.getenv("API_PORT", "8000"))
MIN_POOL_SIZE = 1
MAX_POOL_SIZE = 10
POOL_OPEN_TIMEOUT = 10
READY_TIMEOUT = 3
CANDLE_INTERVAL = timedelta(minutes=1)
SYMBOL_PATTERN = r"^[A-Z0-9]{3,20}$"
MAX_BACKTEST_CANDLES = 200_000
INTERVALS: dict[str, pd.Timedelta] = {"1m": pd.Timedelta(minutes=1)}
MONEY_PLACES = Decimal("0.01")
STATEMENT_TIMEOUT_MS = 5000
MAX_CONCURRENT_BACKTESTS = 4
BACKTEST_TIMEOUT_S = 30
