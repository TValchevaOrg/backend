"""Application entry point and factory.

Run in development with::

    uvicorn app.main:app --reload

The factory pattern (:func:`create_app`) keeps construction explicit and testable;
``app`` is the module-level instance uvicorn imports.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import api_router
from app.config import Settings, get_settings
from app.db import close_pool, create_pool, open_pool


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()
    _configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Open the connection pool for the lifetime of the app.
        pool = create_pool(
            settings.conninfo,
            min_size=settings.pool_min_size,
            max_size=settings.pool_max_size,
        )
        await open_pool(pool)
        app.state.pool = pool
        app.state.settings = settings
        logger.info("FreshList backend %s started.", __version__)
        try:
            yield
        finally:
            await close_pool(pool)

    app = FastAPI(
        title="FreshList API",
        version=__version__,
        summary="Serves the normalized grocery product catalog to the FreshList UI.",
        lifespan=lifespan,
    )

    origins = settings.cors_origin_list
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET"],
            allow_headers=["*"],
        )

    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"service": "freshlist-api", "version": __version__, "docs": "/docs"}

    return app


app = create_app()
