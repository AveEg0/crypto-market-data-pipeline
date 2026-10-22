import os
from datetime import timedelta

import pandas as pd

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
REQUEST_TIMEOUT_S = 10.0
CACHE_TTL_S = 60

DEFAULT_LOOKBACK = timedelta(hours=24)
DEFAULT_INTERVAL = "1m"
MAX_CANDLES = 10_000
INTERVALS = {
    "1m": pd.Timedelta(minutes=1),
    "1h": pd.Timedelta(hours=1),
}
INTERVAL_PRESETS: dict[str, dict[str, timedelta]] = {
    "1m": {
        "30m": timedelta(minutes=30),
        "2h": timedelta(hours=2),
        "6h": timedelta(hours=6),
        "12h": timedelta(hours=12),
        "24h": timedelta(hours=24),
    },
    "1h": {
        "12h": timedelta(hours=12),
        "1d": timedelta(days=1),
        "1w": timedelta(weeks=1),
        "1mo": timedelta(days=30),
        "3mo": timedelta(days=90),
    },
}
DEFAULT_PRESET = {"1m": "6h", "1h": "1w"}
