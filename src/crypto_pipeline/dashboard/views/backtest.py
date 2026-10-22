from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import streamlit as st

from crypto_pipeline.backtest.contracts import FEE_DEFAULT, SLIPPAGE_DEFAULT
from crypto_pipeline.dashboard.api_client import ApiError, get_symbols, post_backtest
from crypto_pipeline.dashboard.charts import equity_curve
from crypto_pipeline.dashboard.config import CACHE_TTL_S

RESULT_KEY = "backtest_result"
DEFAULT_LOOKBACK = timedelta(days=7)


@st.cache_data(ttl=CACHE_TTL_S)
def load_symbols() -> list[str]:
    return get_symbols()


def _as_utc(day: date, moment: time) -> datetime:
    return datetime.combine(day, moment, tzinfo=UTC)


st.title("Backtest")

try:
    symbols = load_symbols()
except ApiError as exc:
    st.error(str(exc))
    st.stop()

if not symbols:
    st.warning("No symbols available.")
    st.stop()

prefill = st.session_state.get("last_selection", {})
default_symbol = prefill.get("symbol", symbols[0])
default_end = prefill.get("end", datetime.now(UTC))
default_start = prefill.get("start", default_end - DEFAULT_LOOKBACK)

with st.form("backtest_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        symbol = st.selectbox("Symbol", symbols, index=symbols.index(default_symbol))
        initial_capital = st.number_input(
            "Initial capital", min_value=100, max_value=10_000_000, value=10_000, step=1_000
        )
    with col2:
        start_day = st.date_input("Start", value=default_start.date())
        end_day = st.date_input("End", value=default_end.date())
    with col3:
        fast_window = st.number_input("Fast window (minutes)", min_value=1, value=60)
        slow_window = st.number_input("Slow window (minutes)", min_value=2, value=240)

    with st.expander("Advanced"):
        fee_rate = st.number_input(
            "Fee rate", min_value=0.0, max_value=0.1, value=float(FEE_DEFAULT), format="%.5f"
        )
        slippage = st.number_input(
            "Slippage", min_value=0.0, max_value=0.1, value=float(SLIPPAGE_DEFAULT), format="%.5f"
        )
        allow_gaps = st.checkbox("Allow gaps", value=False)
        show_curve = st.checkbox("Show equity curve", value=True)

    submitted = st.form_submit_button("Run backtest")

if submitted:
    start = _as_utc(start_day, time.min)
    end = _as_utc(end_day, time.min)

    if end <= start:
        st.error("End must be after start.")
        st.stop()
    if fast_window >= slow_window:
        st.error("Fast window must be shorter than the slow window.")
        st.stop()

    with st.spinner("Running backtest..."):
        try:
            st.session_state[RESULT_KEY] = post_backtest(
                symbol=symbol,
                start=start,
                end=end,
                initial_capital=Decimal(str(initial_capital)),
                fast_window=int(fast_window),
                slow_window=int(slow_window),
                fee_rate=Decimal(str(fee_rate)),
                slippage=Decimal(str(slippage)),
                allow_gaps=allow_gaps,
                include_equity_curve=show_curve,
            )
        except ApiError as exc:
            st.session_state.pop(RESULT_KEY, None)
            st.error(str(exc))

result = st.session_state.get(RESULT_KEY)

if result:
    metrics = result["metrics"]
    info = metrics["frame_info"]

    st.subheader(f"{info['symbol']} · SMA {metrics['fast_window']}/{metrics['slow_window']}")

    row1 = st.columns(4)
    row1[0].metric("Final equity", metrics["final_equity"])
    row1[1].metric("Total return", f"{metrics['total_return']:+.2%}")
    row1[2].metric("Buy & hold", f"{metrics['buy_and_hold_total_return']:+.2%}")
    row1[3].metric("Max drawdown", f"{metrics['max_drawdown']:.2%}")

    row2 = st.columns(4)
    sharpe = metrics["sharpe"]
    win_rate = metrics["win_rate"]
    row2[0].metric("Sharpe", f"{sharpe:.2f}" if sharpe is not None else "n/a")
    row2[1].metric("Win rate", f"{win_rate:.1%}" if win_rate is not None else "n/a")
    row2[2].metric("Trades", metrics["trade_count"])
    row2[3].metric("Fees paid", metrics["fees_paid"])

    st.caption(
        f"{info['candle_count']:,} candles · {info['gap_count']} gaps · "
        f"{info['start_ts'][:16]} to {info['end_ts'][:16]} UTC"
    )

    if metrics["total_return"] < metrics["buy_and_hold_total_return"]:
        st.info("The strategy underperformed buy-and-hold over this range.")

    curve = result.get("equity_curve")
    if curve:
        st.plotly_chart(equity_curve(curve, symbol), use_container_width=True)

    trades = result["trades"]
    with st.expander(f"Trades ({len(trades)})"):
        if trades:
            st.dataframe(trades, use_container_width=True, hide_index=True)
        else:
            st.write("No trades were taken.")
