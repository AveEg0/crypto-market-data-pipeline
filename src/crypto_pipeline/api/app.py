from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from psycopg import OperationalError
from psycopg_pool import AsyncConnectionPool, PoolTimeout
from starlette.responses import JSONResponse

from crypto_pipeline.api.config import (
    MAX_POOL_SIZE,
    MIN_POOL_SIZE,
    POOL_OPEN_TIMEOUT,
    READY_TIMEOUT,
    STATEMENT_TIMEOUT_MS,
)
from crypto_pipeline.api.deps import PoolDep
from crypto_pipeline.api.routes import router
from crypto_pipeline.common.config import get_database_url
from crypto_pipeline.common.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(json_logs=False)
    log = structlog.get_logger()

    if app.debug:
        raise RuntimeError("debug mode must not be enabled")

    pool = AsyncConnectionPool(
        conninfo=get_database_url(),
        min_size=MIN_POOL_SIZE,
        max_size=MAX_POOL_SIZE,
        open=False,
        kwargs={"autocommit": True, "options": f"-c statement_timeout={STATEMENT_TIMEOUT_MS}"},
    )
    await pool.open(wait=True, timeout=POOL_OPEN_TIMEOUT)
    app.state.pool = pool
    log.info("api_started", max_size=MAX_POOL_SIZE)

    try:
        yield
    finally:
        await pool.close()
        log.info("api_stopped")


app = FastAPI(title="Crypto Market Data Pipeline API", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(pool: PoolDep) -> dict[str, str]:
    try:
        async with pool.connection(timeout=READY_TIMEOUT) as conn:
            await conn.execute("SELECT 1")
    except (PoolTimeout, OperationalError) as exc:
        structlog.get_logger().warning("readiness_failed", error=str(exc))
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    structlog.get_logger().exception(
        "unhandled_exception", path=request.url.path, method=request.method
    )
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


@app.exception_handler(OperationalError)
async def database_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
    structlog.get_logger().warning("database_error", path=request.url.path)
    return JSONResponse(status_code=503, content={"detail": "database unavailable"})
