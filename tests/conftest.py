import asyncio
import sys
from collections.abc import Callable, Mapping

import httpx
import pytest

from crypto_pipeline.api.app import app
from crypto_pipeline.api.deps import get_conn


@pytest.fixture
def fake_conn() -> object:
    return object()


@pytest.fixture
async def client(fake_conn) -> httpx.AsyncClient:
    app.dependency_overrides[get_conn] = lambda: fake_conn
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def pytest_asyncio_loop_factories(
    config: object, item: object
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]]:
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return {"default": asyncio.new_event_loop}
