"""PostgreSQL connection-pool lifecycle.

A single :class:`AsyncConnectionPool` is created at application startup and
closed at shutdown (wired in :mod:`app.main` via the lifespan handler). Request
handlers borrow a connection through the :func:`get_pool` dependency.

The pool is opened with ``wait=False`` so the API still boots when the database
is temporarily unreachable (e.g. starting the stack before Postgres is ready);
individual requests then fail fast with a clear 503 rather than the process
crashing on startup.
"""

from __future__ import annotations

import logging

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)


def create_pool(conninfo: str, *, min_size: int, max_size: int) -> AsyncConnectionPool:
    """Build a (not-yet-opened) async pool whose connections return dict rows."""
    return AsyncConnectionPool(
        conninfo,
        min_size=min_size,
        max_size=max_size,
        open=False,
        kwargs={"row_factory": dict_row},
        name="foodie-backend",
    )


async def open_pool(pool: AsyncConnectionPool) -> None:
    """Open the pool without blocking startup on database availability."""
    await pool.open(wait=False)
    logger.info("Database connection pool opened (lazy connect).")


async def close_pool(pool: AsyncConnectionPool) -> None:
    """Close the pool and release all connections."""
    await pool.close()
    logger.info("Database connection pool closed.")
