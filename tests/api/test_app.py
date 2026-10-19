import httpx

from crypto_pipeline.api.app import app


def test_debug_is_disabled():
    assert app.debug is False


async def test_unhandled_exception_returns_clean_500():
    @app.get("/_test_boom")
    async def boom() -> None:
        raise RuntimeError("deliberate failure with a secret: alien")

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/_test_boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "internal server error"}
    assert "alien" not in response.text
    assert "Traceback" not in response.text


async def test_health_needs_no_database():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
