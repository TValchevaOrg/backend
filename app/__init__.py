"""FreshList backend — a FastAPI read service over the normalized product catalog.

The transform pipeline writes products and their price time-series into
PostgreSQL; this service reads them back and serves them in the exact JSON shape
the React frontend already consumes (``GET /items``), so the UI can swap its
bundled mock data for live data without any component changes.
"""

__version__ = "0.1.0"
