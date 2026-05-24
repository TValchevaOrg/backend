# foodie-backend

A FastAPI read service that serves the normalized grocery product catalog from
PostgreSQL to the **FreshList** React frontend.

The [transform](../transform) pipeline scrapes and normalizes grocery data and
writes it to PostgreSQL (tables `products` + `price_observations`). This service
reads that data back and serves it in **the exact JSON shape the frontend
already consumes** — so the UI swaps its bundled mock data for live data by
setting a single environment variable, with no component changes.

```
 transform/  ──writes──▶  PostgreSQL  ──reads──▶  backend/ (this)  ──HTTP──▶  frontend/
  (scrapers)              products,                 GET /items                React UI
                          price_observations
```

## The contract

The frontend's data layer issues exactly one request — `GET /items` — and
derives stores, categories and offerings from the result client-side
(`frontend/src/services/catalog.service.ts`). So this service's job is to
return a flat JSON array of products in the pipeline's canonical shape:

```jsonc
{
  "id": "2bc14159a6889dc2",
  "name": "...", "brand": "", "category": "", "description": "",
  "unit": "кг", "country": "BG",
  "store": { "name": "Kaufland", "coordinates": "" },
  "price": {
    "current":    { "timestamp": "...", "price": "0.37", "discounted": true, "non_discounted_price": "0.99" },
    "historical": [ /* prior observations, oldest → newest */ ]
  },
  "tags": [],
  "nutrition": { "grams": "", "protein": "", "carbs": "", "fats": "", "description": "" }
}
```

`price.current` is the latest price observation and `price.historical` is every
earlier one — both *derived* from the `price_observations` time-series, mirroring
the transform pipeline's own object construction so the shapes never drift.

| Method & path        | Purpose                                              |
|----------------------|------------------------------------------------------|
| `GET /items`         | All products (the feed the frontend consumes).       |
| `GET /items/{id}`    | A single product by id.                              |
| `GET /health`        | Liveness (does not touch the database).              |
| `GET /health/ready`  | Readiness (reports database reachability).           |
| `GET /docs`          | Interactive OpenAPI docs.                            |

## Quick start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'          # or: pip install -r requirements.txt

cp .env.example .env             # then edit DB credentials
uvicorn app.main:app --reload    # http://127.0.0.1:8000  (docs at /docs)
```

You need a populated database. The transform pipeline creates the schema and
fills it; a throwaway local Postgres/TimescaleDB works for both sides:

```bash
docker run -d --name foodie-pg -p 5432:5432 \
    -e POSTGRES_USER=foodie -e POSTGRES_PASSWORD=foodie -e POSTGRES_DB=foodie \
    timescale/timescaledb:latest-pg16

# populate it (from ../transform, with its postgres extra installed):
FOODIE_BACKEND=postgres FOODIE_DB_PASSWORD=foodie \
    python -m foodie_transform raw_data
```

The API boots even if the database is unreachable (the pool connects lazily);
catalog requests then return `503` until the database is available.

## Configuration

Settings come from the environment, with a `.env` / `.env.local` fallback. The
database variables **reuse the transform pipeline's `FOODIE_DB_*` names**, so one
set of credentials drives both sides. See [`.env.example`](.env.example).

| Variable | Meaning | Default |
|----------|---------|---------|
| `FOODIE_DB_DSN` | full connection string (wins over the parts) | — |
| `FOODIE_DB_HOST` / `_PORT` / `_NAME` / `_USER` / `_PASSWORD` / `_SSLMODE` | connection parts | `localhost` / `5432` / `foodie` / `foodie` / — / `prefer` |
| `FOODIE_API_CORS_ORIGINS` | comma-separated allowed browser origins | `http://localhost:5173,http://127.0.0.1:5173` |
| `FOODIE_API_LOG_LEVEL` | `DEBUG`/`INFO`/`WARNING`/`ERROR` | `INFO` |
| `FOODIE_API_POOL_MIN_SIZE` / `_MAX_SIZE` | connection-pool sizing | `1` / `10` |

## Connecting the frontend

Point the React app at this service by setting its base URL, then run it:

```bash
cd ../frontend
echo "VITE_API_BASE_URL=http://127.0.0.1:8000" > .env.local
npm run dev
```

With `VITE_API_BASE_URL` set, the frontend's HTTP client issues real `fetch`
calls against this backend instead of returning bundled mock data — no other
changes required (`frontend/src/api/client.ts`).

## Architecture

```
app/
├── main.py              # app factory + lifespan (opens/closes the pool), CORS
├── config.py            # pydantic-settings; FOODIE_DB_* + FOODIE_API_* contract
├── db.py                # async psycopg connection-pool lifecycle
├── models.py            # Pydantic response models = the canonical Item shape
├── repositories/
│   └── products.py      # SQL reads → Item mapping (mirrors the pipeline's writer)
└── api/
    ├── deps.py          # DI: pool → repository
    └── routes/
        ├── items.py     # GET /items, GET /items/{id}
        └── health.py    # GET /health, GET /health/ready
```

**Layering:** routes depend on repositories (via DI), repositories depend on the
pool and models, models are pure schema. The pool is created once per process and
shared; each request borrows a connection. Adding an endpoint means adding a
repository method and a route — nothing else moves.

## Tests

```bash
pip install -e '.[dev]'
pytest        # no database required
```

`tests/test_mapping.py` pins the DB-row → `Item` JSON shape to the frontend
contract; `tests/test_app.py` boots the app and checks health + OpenAPI.
