import pandas as pd


def sma(values: pd.Series, window: int) -> pd.Series:
    if window < 1:
        raise ValueError("window must >= 1")
    return values.rolling(window=window, min_periods=window).mean()


def rsi(values: pd.Series, window: int = 14) -> pd.Series:
    if window < 1:
        raise ValueError("window must be >= 1")
    delta = values.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = _wilder(gain, window)
    avg_loss = _wilder(loss, window)
    rs = avg_gain / avg_loss
    rsi = 100 - 100 / (1 + rs)
    flat = (avg_gain == 0) & (avg_loss == 0)
    rsi[(avg_loss == 0) & ~flat] = 100.0
    rsi[flat] = 50.0
    return rsi


def _wilder(series: pd.Series, window: int) -> pd.Series:
    seed = series.iloc[1 : window + 1].mean()
    tail = series.iloc[window:].copy()
    tail.iloc[0] = seed
    smoothed = tail.ewm(alpha=1 / window, adjust=False).mean()
    return smoothed.reindex(series.index)
