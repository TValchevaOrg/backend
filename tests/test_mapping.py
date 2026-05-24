"""Lock the DB-row → Item mapping to the exact frontend/pipeline JSON shape.

These tests need no database: they feed representative ``products`` and
``price_observations`` rows (as psycopg's dict rows would arrive) through the
repository's pure mapping helpers and assert the resulting JSON matches the
canonical ``Item`` contract field-for-field.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.repositories.products import _format_amount, _row_to_item

# The exact top-level keys the frontend's Item interface expects.
ITEM_KEYS = {
    "id", "name", "brand", "category", "description", "unit", "country",
    "store", "price", "tags", "nutrition",
}


def _product_row(**overrides):
    row = {
        "id": "2bc14159a6889dc2",
        "name": "Картофи Клас: I",
        "brand": "",
        "category": "",
        "description": "",
        "unit": "кг",
        "country": "BG",
        "store_name": "Kaufland",
        "store_coords": "",
        "tags": [],
        "nutrition": {"grams": "", "protein": "", "carbs": "", "fats": "", "description": ""},
    }
    row.update(overrides)
    return row


def _obs(ts: str, price: str, *, discounted=False, was: str | None = None):
    return {
        "product_id": "2bc14159a6889dc2",
        "observed_at": datetime.fromisoformat(ts),
        "price": Decimal(price),
        "discounted": discounted,
        "non_discounted_price": Decimal(was) if was is not None else None,
    }


def test_format_amount():
    assert _format_amount(Decimal("0.37")) == "0.37"
    assert _format_amount(Decimal("18.4")) == "18.40"
    assert _format_amount(None) == ""
    assert _format_amount(7.66) == "7.66"


def test_item_has_exactly_the_contract_keys():
    item = _row_to_item(_product_row(), [])
    payload = item.model_dump()
    assert set(payload) == ITEM_KEYS
    assert set(payload["price"]) == {"current", "historical"}
    assert set(payload["price"]["current"]) == {
        "timestamp", "price", "discounted", "non_discounted_price"
    }
    assert set(payload["nutrition"]) == {"grams", "protein", "carbs", "fats", "description"}
    assert set(payload["store"]) == {"name", "coordinates"}


def test_no_observations_yields_empty_price():
    item = _row_to_item(_product_row(), [])
    assert item.price.current.price == ""
    assert item.price.current.timestamp == ""
    assert item.price.historical == []


def test_current_is_latest_history_is_prior():
    # Observations arrive time-ascending (the repository's ORDER BY guarantees it).
    observations = [
        _obs("2026-05-21T10:00:00+00:00", "0.99"),
        _obs("2026-05-22T10:00:00+00:00", "0.50", discounted=True, was="0.99"),
        _obs("2026-05-23T23:44:20.463574+00:00", "0.37", discounted=True, was="0.99"),
    ]
    item = _row_to_item(_product_row(), observations)

    # current == newest observation
    assert item.price.current.price == "0.37"
    assert item.price.current.timestamp == "2026-05-23T23:44:20.463574+00:00"
    assert item.price.current.discounted is True
    assert item.price.current.non_discounted_price == "0.99"

    # historical == everything before current, oldest → newest
    assert [p.price for p in item.price.historical] == ["0.99", "0.50"]


def test_full_payload_round_trips_to_expected_json():
    observations = [_obs("2026-05-23T23:44:20.463574+00:00", "0.37", discounted=True, was="0.99")]
    item = _row_to_item(_product_row(), observations)
    assert item.model_dump() == {
        "id": "2bc14159a6889dc2",
        "name": "Картофи Клас: I",
        "brand": "",
        "category": "",
        "description": "",
        "unit": "кг",
        "country": "BG",
        "store": {"name": "Kaufland", "coordinates": ""},
        "price": {
            "current": {
                "timestamp": "2026-05-23T23:44:20.463574+00:00",
                "price": "0.37",
                "discounted": True,
                "non_discounted_price": "0.99",
            },
            "historical": [],
        },
        "tags": [],
        "nutrition": {"grams": "", "protein": "", "carbs": "", "fats": "", "description": ""},
    }
