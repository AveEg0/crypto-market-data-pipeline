from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

from crypto_pipeline.api import routes
from crypto_pipeline.api.models import CandleOut

BASE = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
RANGE = {"start": "2026-09-01T10:00:00Z", "end": "2026-09-01T11:00:00Z"}


def candle(minute: int) -> CandleOut:
    return CandleOut(
        symbol="BTCUSDT",
        ts=BASE + timedelta(minutes=minute),
        open=Decimal("64183.90000000"),
        high=Decimal("64200.00000000"),
        low=Decimal("64100.00000000"),
        close=Decimal("64150.00000000"),
        volume=Decimal("1.5"),
    )


async def test_symbols_returns_envelope(client, monkeypatch):
    monkeypatch.setattr(routes, "list_symbols", AsyncMock(return_value=["BTCUSDT", "ETHUSDT"]))

    response = await client.get("/symbols")

    assert response.status_code == 200
    assert response.json() == {"symbols": ["BTCUSDT", "ETHUSDT"]}


async def test_candles_serializes_decimals_as_strings(client, monkeypatch):
    monkeypatch.setattr(
        routes, "list_candles", AsyncMock(return_value=([candle(0), candle(1)], False))
    )

    response = await client.get("/candles/BTCUSDT", params=RANGE)
    first = response.json()["candles"][0]

    assert isinstance(first["open"], str)
    assert first["open"] == "64183.90000000"
    assert first["ts"].endswith("Z") or first["ts"].endswith("+00:00")


async def test_candles_coverage_uses_requested_range(client, monkeypatch):
    """expected counts the requested window, not the candles that came back."""
    monkeypatch.setattr(
        routes,
        "list_candles",
        AsyncMock(return_value=([candle(0), candle(1), candle(3)], False)),
    )

    coverage = (await client.get("/candles/BTCUSDT", params=RANGE)).json()["coverage"]

    assert coverage["expected"] == 61  # 10:00-11:00 inclusive at 1m
    assert coverage["returned"] == 3
    assert coverage["truncated"] is False


async def test_candles_unknown_symbol_is_404(client, monkeypatch):
    monkeypatch.setattr(routes, "list_candles", AsyncMock(return_value=([], False)))
    monkeypatch.setattr(routes, "list_symbols", AsyncMock(return_value=["BTCUSDT"]))

    response = await client.get("/candles/FAKEUSDT", params=RANGE)

    assert response.status_code == 404


async def test_candles_known_symbol_empty_range_is_200(client, monkeypatch):
    monkeypatch.setattr(routes, "list_candles", AsyncMock(return_value=([], False)))
    monkeypatch.setattr(routes, "list_symbols", AsyncMock(return_value=["BTCUSDT"]))

    response = await client.get("/candles/BTCUSDT", params=RANGE)

    assert response.status_code == 200
    assert response.json()["candles"] == []
    assert response.json()["coverage"]["expected"] == 61
    assert response.json()["coverage"]["returned"] == 0


async def test_candles_malformed_symbol_is_422(client):
    response = await client.get("/candles/bad!", params=RANGE)

    assert response.status_code == 422


async def test_coverage_rejects_reversed_range(client):
    response = await client.get(
        "/coverage/BTCUSDT",
        params={"start": "2026-09-02T00:00:00Z", "end": "2026-09-01T00:00:00Z"},
    )

    assert response.status_code == 422


async def test_candles_requires_range(client):
    """start and end are mandatory since coverage measures the requested window."""
    response = await client.get("/candles/BTCUSDT")
    assert response.status_code == 422


async def test_candles_truncated_when_limit_reached(client, monkeypatch):
    """A capped result reports truncated so the client doesn't read it as a gap."""
    monkeypatch.setattr(
        routes,
        "list_candles",
        AsyncMock(return_value=([candle(i) for i in range(5)], True)),
    )
    body = (await client.get("/candles/BTCUSDT", params={**RANGE, "limit": 5})).json()
    assert body["coverage"]["truncated"] is True
