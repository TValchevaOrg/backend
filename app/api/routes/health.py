"""Liveness and readiness endpoints for orchestrators and uptime checks."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import ProductRepositoryDep

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str
    database: str


@router.get("/health", summary="Liveness check")
async def health() -> dict[str, str]:
    """Return ok if the process is up (does not touch the database)."""
    return {"status": "ok"}


@router.get("/health/ready", response_model=Health, summary="Readiness check")
async def readiness(repo: ProductRepositoryDep) -> Health:
    """Report whether the database backing the catalog is reachable."""
    try:
        await repo.ping()
    except psycopg.Error:
        return Health(status="degraded", database="unreachable")
    return Health(status="ok", database="reachable")
