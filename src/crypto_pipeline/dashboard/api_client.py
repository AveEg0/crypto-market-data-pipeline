from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from crypto_pipeline.dashboard.config import API_BASE_URL, REQUEST_TIMEOUT_S


class ApiError(Exception):
    """Raised when the API cannot be reached or returns an error status."""


@contextmanager
def _api_errors() -> Iterator[None]:
    try:
        yield
    except httpx.HTTPStatusError as exc:
        raise ApiError(f"{exc.response.status_code}: {_detail(exc.response)}") from exc
    except httpx.HTTPError as exc:
        raise ApiError(f"could not reach the API at {API_BASE_URL}") from exc


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    with _api_errors(), httpx.Client(base_url=API_BASE_URL, timeout=REQUEST_TIMEOUT_S) as client:
        response = client.get(path, params=params)
        response.raise_for_status()
        return response.json()


def _post(path: str, body: dict[str, Any]) -> Any:
    with _api_errors(), httpx.Client(base_url=API_BASE_URL, timeout=REQUEST_TIMEOUT_S) as client:
        response = client.post(path, json=body)
        response.raise_for_status()
        return response.json()


def _detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("detail", response.text))
    except ValueError:
        return response.text


def get_symbols() -> list[str]:
    return _get("/symbols")["symbols"]


def get_candles(
    symbol: str,
    start: datetime,
    end: datetime,
    interval: str,
    limit: int,
) -> dict[str, Any]:
    return _get(
        f"/candles/{symbol}",
        params={
            "start": start.isoformat(),
            "end": end.isoformat(),
            "interval": interval,
            "limit": limit,
        },
    )


def get_coverage(symbol: str, start: datetime, end: datetime) -> dict[str, Any]:
    return _get(
        f"/coverage/{symbol}",
        params={"start": start.isoformat(), "end": end.isoformat()},
    )


def post_backtest(
    symbol: str,
    start: datetime,
    end: datetime,
    initial_capital: Decimal,
    fast_window: int,
    slow_window: int,
    fee_rate: Decimal,
    slippage: Decimal,
    allow_gaps: bool = False,
    include_equity_curve: bool = False,
) -> dict[str, Any]:
    body = {
        "symbol": symbol,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "initial_capital": str(initial_capital),
        "fast_window": fast_window,
        "slow_window": slow_window,
        "fee_rate": str(fee_rate),
        "slippage": str(slippage),
        "allow_gaps": allow_gaps,
        "include_equity_curve": include_equity_curve,
    }
    return _post("/backtest", body)
