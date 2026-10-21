import os

import httpx
import pytest
from psycopg_pool import AsyncConnectionPool

from crypto_pipeline.api.app import app
from crypto_pipeline.common.config import get_database_url

pytestmark = pytest.mark.integration


@pytest.fixture
async def live_client() -> httpx.AsyncClient:
    if not os.getenv("DATABASE_URL"):
        pytest.skip("Skipping because DATABASE_URL is not set")
    pool = AsyncConnectionPool(
        conninfo=get_database_url(),
        min_size=1,
        max_size=2,
        open=False,
        kwargs={"autocommit": True},
    )
    await pool.open(wait=True, timeout=5)
    app.state.pool = pool
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        await pool.close()


async def test_symbols_against_real_db(live_client):
    response = await live_client.get("/symbols")

    assert response.status_code == 200
    assert "BTCUSDT" in response.json()["symbols"]


async def test_candles_against_real_db(live_client):
    response = await live_client.get(
        "/candles/BTCUSDT",
        params={"start": "2026-10-01T00:00:00Z", "end": "2026-10-02T00:00:00Z", "limit": 10},
    )
    body = response.json()
    assert len(body["candles"]) == 10
    assert body["coverage"]["truncated"] is True
    assert body["coverage"]["expected"] == 1441


async def test_candles_hourly_against_real_db(live_client):
    response = await live_client.get(
        "/candles/BTCUSDT",
        params={
            "start": "2026-10-01T00:00:00Z",
            "end": "2026-10-02T00:00:00Z",
            "interval": "1h",
            "limit": 100,
        },
    )
    body = response.json()
    assert body["coverage"]["expected"] == 25
    assert body["candles"][0]["ts"] == "2026-10-01T00:00:00Z"


async def test_backtest_against_real_db(live_client):
    # candles in range should be filled
    response = await live_client.post(
        "/backtest",
        json={
            "symbol": "BTCUSDT",
            "start": "2026-09-01T00:00:00Z",
            "end": "2026-09-02T00:00:00Z",
            "initial_capital": "10000",
            "fast_window": 10,
            "slow_window": 30,
            "allow_gaps": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["frame_info"]["interval"] == "1m"
    assert body["equity_curve"] is None
    assert isinstance(body["metrics"]["final_equity"], str)
