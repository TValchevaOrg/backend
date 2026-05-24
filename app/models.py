"""Response schema — the canonical product shape the frontend consumes.

These models reproduce, field for field, the JSON the transform pipeline emits
(``transform .../models.py::Product.to_dict``) and that the React app types as
``Item`` (``frontend/src/models/item.ts``). Numeric values are intentionally
strings (matching the source feed); the frontend's catalog service parses them.

Keeping the shape here as Pydantic models means it is validated on the way out
and published in the OpenAPI docs, so any drift between the DB read path and the
contract the UI expects surfaces immediately.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Nutrition(BaseModel):
    """Per-pack nutrition facts; all fields raw strings, ``""`` when unknown."""

    model_config = ConfigDict(extra="ignore")

    grams: str = ""
    protein: str = ""
    carbs: str = ""
    fats: str = ""
    description: str = ""


class StoreRef(BaseModel):
    """The store a product was observed at."""

    name: str = ""
    coordinates: str = ""


class PricePoint(BaseModel):
    """A single price observation at a point in time. Prices are raw strings."""

    timestamp: str = ""
    price: str = ""
    discounted: bool = False
    non_discounted_price: str = ""


class Price(BaseModel):
    """Latest price observation plus the trailing history (oldest → newest)."""

    current: PricePoint = Field(default_factory=PricePoint)
    historical: list[PricePoint] = Field(default_factory=list)


class Item(BaseModel):
    """One product observed at one store — the unit of the ``/items`` feed."""

    id: str = ""
    name: str = ""
    brand: str = ""
    category: str = ""
    description: str = ""
    unit: str = ""
    country: str = ""
    store: StoreRef = Field(default_factory=StoreRef)
    price: Price = Field(default_factory=Price)
    tags: list[str] = Field(default_factory=list)
    nutrition: Nutrition = Field(default_factory=Nutrition)
