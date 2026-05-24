"""Product catalog endpoints.

``GET /items`` is the contract the frontend already calls (see
``frontend/src/api/catalog.api.ts``): a flat array of products in the
pipeline's canonical shape, from which the UI derives stores, categories and
offerings client-side. Everything else here is additive and optional.
"""

from __future__ import annotations

import logging

import psycopg
from fastapi import APIRouter, HTTPException, status

from app.api.deps import ProductRepositoryDep
from app.models import Item

logger = logging.getLogger(__name__)

router = APIRouter(tags=["catalog"])

_DB_UNAVAILABLE = "The product catalog is temporarily unavailable."


@router.get("/items", response_model=list[Item], summary="List all products")
async def list_items(repo: ProductRepositoryDep) -> list[Item]:
    """Return every product with its derived current price and price history."""
    try:
        return await repo.list_items()
    except psycopg.Error:
        logger.exception("Failed to read products from the database")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_DB_UNAVAILABLE
        ) from None


@router.get(
    "/items/{item_id}",
    response_model=Item,
    summary="Get one product by id",
    responses={404: {"description": "No product with that id"}},
)
async def get_item(item_id: str, repo: ProductRepositoryDep) -> Item:
    """Return a single product, or 404 if the id is unknown."""
    try:
        item = await repo.get_item(item_id)
    except psycopg.Error:
        logger.exception("Failed to read product %s from the database", item_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_DB_UNAVAILABLE
        ) from None
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"No product with id {item_id!r}"
        )
    return item
