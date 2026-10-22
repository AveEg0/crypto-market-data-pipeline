import datetime

import pandas as pd
import plotly.graph_objects as go

from crypto_pipeline.dashboard.config import INTERVALS


def candlestick(
    df: pd.DataFrame, symbol: str, start: datetime, end: datetime, interval: str
) -> go.Figure:
    figure = go.Figure(
        data=[
            go.Candlestick(
                x=df["ts"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name=symbol,
            )
        ]
    )
    figure.update_xaxes(range=[start, end])
    gaps = gap_spans(df, start, end, INTERVALS[interval])
    for gap_start, gap_end in gaps:
        figure.add_vrect(x0=gap_start, x1=gap_end, fillcolor="red", opacity=0.15, line_width=0)
    figure.update_layout(
        title=f"{symbol} · {interval}",
        xaxis_title=None,
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        height=500,
        margin={"l": 40, "r": 20, "t": 40, "b": 20},
    )
    return figure


def gap_spans(
    df: pd.DataFrame, start: datetime, end: datetime, interval: pd.Timedelta
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    spans = []
    first, last = df["ts"].iloc[0], df["ts"].iloc[-1]

    if first - pd.Timestamp(start) > interval:
        spans.append((start, first))

    deltas = df["ts"].diff()
    spans.extend(
        (df["ts"].iloc[i - 1], df["ts"].iloc[i])
        for i in range(1, len(df))
        if deltas.iloc[i] > interval
    )

    if pd.Timestamp(end) - last > interval:
        spans.append((last, end))

    return spans


def equity_curve(points: list[dict], symbol: str) -> go.Figure:
    figure = go.Figure(
        data=[
            go.Scatter(
                x=[p["ts"] for p in points],
                y=[p["equity"] for p in points],
                mode="lines",
                name=f"{symbol} strategy",
            )
        ]
    )
    figure.update_layout(
        title="Equity Curve",
        yaxis_title="Equity",
        height=400,
        margin={"l": 40, "r": 20, "t": 40, "b": 20},
    )
    return figure
