from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

from crypto_pipeline.api import routes
from crypto_pipeline.api.models import CandleOut

BASE = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)


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

    response = await client.get("/candles/BTCUSDT")
    first = response.json()["candles"][0]

    assert isinstance(first["open"], str)
    assert first["open"] == "64183.90000000"
    assert first["ts"].endswith("Z") or first["ts"].endswith("+00:00")


async def test_candles_reports_gap_in_coverage(client, monkeypatch):
    # 10:00, 10:01, 10:03 -> expected 4, returned 3
    monkeypatch.setattr(
        routes,
        "list_candles",
        AsyncMock(return_value=([candle(0), candle(1), candle(3)], False)),
    )

    coverage = (await client.get("/candles/BTCUSDT")).json()["coverage"]

    assert coverage["expected"] == 4
    assert coverage["returned"] == 3
    assert coverage["truncated"] is False


async def test_candles_unknown_symbol_is_404(client, monkeypatch):
    monkeypatch.setattr(routes, "list_candles", AsyncMock(return_value=([], False)))
    monkeypatch.setattr(routes, "list_symbols", AsyncMock(return_value=["BTCUSDT"]))

    response = await client.get("/candles/FAKEUSDT")

    assert response.status_code == 404


async def test_candles_known_symbol_empty_range_is_200(client, monkeypatch):
    monkeypatch.setattr(routes, "list_candles", AsyncMock(return_value=([], False)))
    monkeypatch.setattr(routes, "list_symbols", AsyncMock(return_value=["BTCUSDT"]))

    response = await client.get("/candles/BTCUSDT")

    assert response.status_code == 200
    assert response.json()["candles"] == []
    assert response.json()["coverage"] is None


async def test_candles_malformed_symbol_is_422(client):
    response = await client.get("/candles/bad!")

    assert response.status_code == 422


async def test_coverage_rejects_reversed_range(client):
    response = await client.get(
        "/coverage/BTCUSDT",
        params={"start": "2026-09-02T00:00:00Z", "end": "2026-09-01T00:00:00Z"},
    )

    assert response.status_code == 422
