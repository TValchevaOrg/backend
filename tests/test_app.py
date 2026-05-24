"""App-level smoke tests that need no database.

The pool opens lazily (``wait=False``), so the app boots and serves routes that
don't touch the database even when Postgres is absent.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_app_boots_and_health_ok():
    app = create_app()
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}


def test_items_route_is_published_in_openapi():
    app = create_app()
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    assert "/items" in schema["paths"]
    assert "get" in schema["paths"]["/items"]
