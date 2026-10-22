from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from crypto_pipeline.dashboard.api_client import ApiError, get_candles, get_coverage, get_symbols
from crypto_pipeline.dashboard.charts import candlestick
from crypto_pipeline.dashboard.config import (
    CACHE_TTL_S,
    DEFAULT_PRESET,
    INTERVAL_PRESETS,
    MAX_CANDLES,
)


@st.cache_data(ttl=CACHE_TTL_S)
def load_symbols() -> list[str]:
    return get_symbols()


@st.cache_data(ttl=CACHE_TTL_S)
def load_candles(symbol: str, start: datetime, end: datetime, interval: str, limit: int) -> dict:
    return get_candles(symbol, start, end, interval, limit)


@st.cache_data(ttl=CACHE_TTL_S)
def load_coverage(symbol: str, start: datetime, end: datetime) -> dict:
    return get_coverage(symbol, start, end)


try:
    symbols = load_symbols()
except ApiError as exc:
    st.error(str(exc))
    symbols = []

if not symbols:
    st.warning("No symbols available.")
    st.stop()

now = datetime.now(UTC).replace(second=0, microsecond=0)

col1, col2, col3 = st.columns(3)
with col1:
    symbol = st.selectbox("Symbol", symbols)
with col2:
    interval = st.selectbox("Interval", ["1m", "1h"])

presets = INTERVAL_PRESETS[interval]
labels = list(presets)

with col3:
    preset = st.radio(
        "Lookback",
        labels,
        index=labels.index(DEFAULT_PRESET[interval]),
        horizontal=True,
    )

end = now
start = end - presets[preset]

st.caption(f"{symbol} · {interval} · {start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} UTC")


try:
    data = load_candles(symbol, start, end, interval, MAX_CANDLES)
except ApiError as exc:
    st.error(str(exc))
    st.stop()

candles = data["candles"]
coverage = data["coverage"]

if not candles:
    st.warning(f"No candles for {symbol} in this range.")
    st.stop()

df = pd.DataFrame(candles)
df["ts"] = pd.to_datetime(df["ts"])
for column in ("open", "high", "low", "close", "volume"):
    df[column] = df[column].astype(float)

st.plotly_chart(candlestick(df, symbol, start, end, interval), use_container_width=True)

left, right = st.columns([3, 1])
with left:
    st.dataframe(df, width="stretch", hide_index=True)

try:
    data = load_candles(symbol, start, end, interval, MAX_CANDLES)
    raw_coverage = load_coverage(symbol, start, end)
except ApiError as exc:
    st.error(str(exc))
    st.stop()

candles = data["candles"]
truncated = data["coverage"]["truncated"]

with right:
    st.subheader("Data coverage (1m)")
    expected = raw_coverage["expected"]
    returned = raw_coverage["returned"]
    missing = expected - returned
    pct = 100 * returned / expected

    st.metric("Candles shown", len(candles))
    st.metric("Complete", f"{pct:.1f}%")
    st.metric("Missing (1m)", f"{missing:,}")

    if truncated:
        st.warning("Result truncated by limit — narrow the range or use a larger interval.")
    elif missing:
        st.warning(
            f"{missing:,} minutes missing. "
            f"A backtest over this range will be rejected unless gaps are allowed."
        )


st.session_state["last_selection"] = {"symbol": symbol, "start": start, "end": end}
