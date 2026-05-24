"""Shared FastAPI dependencies.

The connection pool lives on ``app.state`` (set in the lifespan handler). These
helpers expose it and the repository to handlers so routes never reach into
application state directly — which keeps them trivial to override in tests.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from psycopg_pool import AsyncConnectionPool

from app.repositories.products import ProductRepository


def get_pool(request: Request) -> AsyncConnectionPool:
    """Return the application-wide connection pool."""
    return request.app.state.pool


def get_product_repository(
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
) -> ProductRepository:
    """Construct a per-request repository bound to the shared pool."""
    return ProductRepository(pool)


ProductRepositoryDep = Annotated[ProductRepository, Depends(get_product_repository)]
