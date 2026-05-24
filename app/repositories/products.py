"""Read products and their price time-series from PostgreSQL.

The schema is owned and created by the transform pipeline
(``transform/foodie_transform/persistence/postgres_repository.py``):

* ``products`` — one row per product (slowly-changing descriptive fields).
* ``price_observations`` — append-only time-series, one row per observation.

This repository only *reads*. A product's ``price.current`` / ``price.historical``
are derived from the observation series — current is the latest observation,
historical is everything before it — exactly as the writer's ``_row_to_product``
does, so the JSON served here matches the pipeline's own output object-for-object.

All reads go through a borrowed pooled connection; the repository is cheap to
construct per request and holds no connection state of its own.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from psycopg_pool import AsyncConnectionPool

from app.models import Item, Nutrition, Price, PricePoint, StoreRef

# Columns selected from the time-series table, in a stable order.
_OBS_COLUMNS = "product_id, observed_at, price, discounted, non_discounted_price"


def _format_amount(value: Decimal | float | None) -> str:
    """Format a numeric DB amount as ``"D.DD"`` (``""`` for NULL).

    Mirrors the transform pipeline's ``prices.format_amount`` so prices render
    identically on the read side.
    """
    if value is None:
        return ""
    try:
        return f"{Decimal(str(value)):.2f}"
    except (InvalidOperation, ValueError):
        return ""


def _observation_to_point(obs: dict[str, Any]) -> PricePoint:
    """Map one ``price_observations`` row to a :class:`PricePoint`."""
    observed_at = obs["observed_at"]
    return PricePoint(
        timestamp=observed_at.isoformat() if observed_at else "",
        price=_format_amount(obs["price"]),
        discounted=bool(obs["discounted"]),
        non_discounted_price=_format_amount(obs["non_discounted_price"]),
    )


def _row_to_item(row: dict[str, Any], observations: list[dict[str, Any]]) -> Item:
    """Combine a ``products`` row with its (time-ascending) observations."""
    points = [_observation_to_point(obs) for obs in observations]
    price = Price()
    if points:
        price = Price(current=points[-1], historical=points[:-1])
    return Item(
        id=row["id"],
        name=row["name"],
        brand=row["brand"],
        category=row["category"],
        description=row["description"],
        unit=row["unit"],
        country=row["country"],
        store=StoreRef(name=row["store_name"], coordinates=row["store_coords"]),
        price=price,
        tags=list(row["tags"] or []),
        nutrition=Nutrition.model_validate(row["nutrition"] or {}),
    )


class ProductRepository:
    """Reads the product catalog from PostgreSQL into :class:`Item` models."""

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def list_items(self) -> list[Item]:
        """Return every product with its full price history, ordered by id.

        Two queries (products, then all observations) are grouped in memory —
        the same approach as the writer's ``all()`` — to avoid an N+1 fan-out.
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM products ORDER BY id")
                product_rows = await cur.fetchall()
                await cur.execute(
                    f"SELECT {_OBS_COLUMNS} FROM price_observations"
                    " ORDER BY product_id, observed_at"
                )
                obs_rows = await cur.fetchall()

        by_product: dict[str, list[dict[str, Any]]] = {}
        for obs in obs_rows:
            by_product.setdefault(obs["product_id"], []).append(obs)

        return [_row_to_item(row, by_product.get(row["id"], [])) for row in product_rows]

    async def get_item(self, item_id: str) -> Item | None:
        """Return a single product by id, or ``None`` if it does not exist."""
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM products WHERE id = %s", (item_id,))
                row = await cur.fetchone()
                if row is None:
                    return None
                await cur.execute(
                    f"SELECT {_OBS_COLUMNS} FROM price_observations"
                    " WHERE product_id = %s ORDER BY observed_at",
                    (item_id,),
                )
                obs_rows = await cur.fetchall()
        return _row_to_item(row, obs_rows)

    async def ping(self) -> None:
        """Run a trivial query to confirm the database is reachable."""
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                await cur.fetchone()
