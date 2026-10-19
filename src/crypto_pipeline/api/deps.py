from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Request
from fastapi.params import Depends
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool


def get_pool(request: Request) -> AsyncConnectionPool:
    return request.app.state.pool


PoolDep = Annotated[AsyncConnectionPool, Depends(get_pool)]


async def get_conn(pool: PoolDep) -> AsyncIterator[AsyncConnection]:
    async with pool.connection() as conn:
        yield conn


ConnDep = Annotated[AsyncConnection, Depends(get_conn)]
