import pandas as pd


def sma_crossover(fast: pd.Series, slow: pd.Series) -> pd.Series:
    if not fast.index.equals(slow.index):
        raise ValueError("Index does not match")
    if fast.empty or slow.empty:
        raise ValueError("Empty series")
    if not pd.api.types.is_numeric_dtype(fast) or not pd.api.types.is_numeric_dtype(slow):
        raise ValueError("Series must have numeric dtype")
    if fast.isna().all() or slow.isna().all():
        raise ValueError(
            "All NaN values in series, probable cause = window is longer than data length"
        )
    if fast.isna().sum() > slow.isna().sum():
        raise ValueError("Args appear swapped: fast must have the shorter window")

    crossover = (fast > slow).astype(int)
    return crossover.shift(1).fillna(0).astype("int64")
