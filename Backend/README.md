# Backend — Inventory Service (FastAPI)

Source of truth for inventory, items, customers, vendors, purchase orders,
sales orders, and the stock-movement audit ledger. Talks to Zoho only via
the Integration Layer; never directly.

> The engineering contract for this service is in [`CLAUDE.md`](./CLAUDE.md).
> Read it before changing code.

---

## Status

| Phase | Theme | Status |
|---|---|---|
| 1 | Bootstrap (app factory, config, logging, exceptions, middleware) | ✅ |
| 2 | Authentication — pwdlib (Argon2id) + JWT | ✅ |
| 3 | Users (self/admin separation, soft-delete, audit) | ✅ |
| 4 | Items (CRUD without DELETE; computed stock status) | ✅ |
| 5 | Customers, Vendors, Vendor-Item-Terms | ✅ |
| 6 | Stock Movements (append-only ledger, the keystone for stock changes) | ✅ |
| 7 | Purchase Orders (DRAFT → RECEIVED, stock IN) | ✅ |
| 8 | Sales Orders (DRAFT → SHIPPED, stock OUT, atomic with `INSUFFICIENT_STOCK` guard) | ✅ |

**Gate** *(at the time of writing)*: 206 tests passing · ruff clean · format clean · mypy clean across 61 source files.

---

## Architecture at a glance

```
React Frontend
     ↓ HTTPS, JWT
Backend (this service) ──► inventory_db (Postgres)
     ↓ internal HTTP  (Phase 9)
Integration Layer ──► integration_db (Postgres) ──► Zoho CRM
```

Single dependency direction inside the service:

```
api  →  services  →  repositories  →  models
```

Routes are thin (≈ ≤ 10 lines): **parse → call service → return**. Business
rules live in services. All SQL lives in repositories. No exceptions.

See [`CLAUDE.md`](./CLAUDE.md) for the canonical folder layout and the rules
applied to each layer.

---

## Domain model

Ten application tables:

| Table | Phase | What it owns |
|---|---|---|
| `users` | 2 | Identity, password hash, `is_admin`, audit attribution |
| `items` | 4 | Inventory master (raw + finished), `stock_quantity` |
| `customers` | 5 | Customer master |
| `vendors` | 5 | Vendor master |
| `vendor_item_terms` | 5 | Per-vendor pricing terms with date windows |
| `stock_movements` | 6 | **Append-only ledger** — every stock change writes here |
| `purchase_orders` | 7 | PO headers (DRAFT, RECEIVED) |
| `purchase_order_items` | 7 | PO lines (immutable once written) |
| `sales_orders` | 8 | SO headers (DRAFT, SHIPPED) |
| `sales_order_items` | 8 | SO lines (immutable once written) |

Plus Postgres ENUMs (`item_type`, `movement_direction`, `movement_reason`,
`purchase_order_status`, `sales_order_status`) and SEQUENCES
(`purchase_order_number_seq`, `sales_order_number_seq`).

The **keystone rule** is that `items.stock_quantity` is mutated by exactly one
function in the codebase — `StockMovementService.record_movement` — which:

1. `SELECT ... FOR UPDATE`s the item row.
2. Updates `items.stock_quantity` and inserts a `stock_movements` row in the
   *same* SQLAlchemy session.
3. Does **not** commit — the caller owns the transaction.

PO `receive` and SO `ship` each call `record_movement` per line inside one
outer transaction, so a stock change and its audit row are atomic together,
and a failure mid-loop (typically `INSUFFICIENT_STOCK` on an OUT line) rolls
the entire transaction back.

---

## API surface — 37 endpoints

| Group | # | Path prefix |
|---|---|---|
| auth | 2 | `/api/v1/auth` |
| users | 4 | `/api/v1/users` |
| items | 4 | `/api/v1/items` |
| customers | 5 | `/api/v1/customers` |
| vendors | 5 | `/api/v1/vendors` |
| vendor-terms | 5 | `/api/v1/vendors/{vendor_id}/terms` |
| stock-movements | 2 | `/api/v1/stock-movements` |
| purchase-orders | 4 | `/api/v1/purchase-orders` |
| sales-orders | 4 | `/api/v1/sales-orders` |
| probes | 2 | `/health` (liveness), `/ready` (readiness) — unversioned |

Live OpenAPI: <http://localhost:8000/docs>.

A full reference (request/response shapes, error codes, examples) lives in
[`docs/Backend_Reference.md`](./docs/Backend_Reference.md) and the rendered
PDF [`docs/Backend_Reference.pdf`](./docs/Backend_Reference.pdf).

A ready-to-import Postman collection lives at
[`docs/InventoryBackend.postman_collection.json`](./docs/InventoryBackend.postman_collection.json).

---

## Error envelope

Every non-2xx response uses the same shape:

```json
{
  "error": {
    "code": "INSUFFICIENT_STOCK",
    "message": "Insufficient stock: 5 available, 50 requested",
    "request_id": "f04ca71a-602e-4f78-8fcf-c2f2dc315170"
  }
}
```

`code` is the stable machine identifier — branch on it, not on `message`.
`request_id` matches the `X-Request-ID` response header for correlation.

---

## Prerequisites

- **Python 3.14** (`.python-version` pins it)
- **uv** — package manager. Install: <https://docs.astral.sh/uv/>
- **Docker Desktop** — runs local Postgres
- **pgAdmin** *(optional)* — GUI for browsing the database

---

## Quick start

Run these once, in order, from PowerShell.

### 1. Start the database (shared with Integration Layer)

From the **project root** (`Code/`), not from `Backend/`:

```powershell
cd "..\"                  # go up to Code/
docker compose up -d
docker compose ps         # wait until STATUS shows (healthy)
```

One Postgres server (`inventory_crm_server`) hosts two databases:
`inventory_db` and `integration_db`. Data persists in the
`inventory_crm_data` named volume.

### 2. Configure the Backend

From the `Backend/` folder:

```powershell
cd Backend
copy .env.example .env
```

Edit `.env`:
- `JWT_SECRET_KEY` — generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`
- `INTEGRATION_LAYER_API_KEY` — generate the same way; must match the
  Integration Layer's `INTERNAL_API_KEY`
- Leave other values at their defaults for local dev.

### 3. Install dependencies

```powershell
uv sync
```

### 4. Apply database migrations

```powershell
uv run alembic upgrade head
```

### 5. Promote your admin (once, in SQL)

After registering your operator account via `POST /api/v1/auth/register`:

```powershell
docker compose exec db psql -U postgres -d inventory_db -c ^
  "UPDATE users SET is_admin = true WHERE email = 'you@example.com';"
```

Phase 1 has no admin-promotion endpoint by design — see the *Administration*
section below.

### 6. Run the dev server

```powershell
uv run uvicorn app.main:app --reload --app-dir src --port 8000
```

Open <http://localhost:8000/docs> for the OpenAPI explorer.

---

## Common commands

```powershell
# tests
uv run pytest -q
uv run pytest -q tests/test_purchase_orders.py
uv run pytest -q tests/test_sales_orders.py::test_ship_so_insufficient_stock_returns_409_and_rolls_back_all_lines

# lint + format
uv run ruff check
uv run ruff format
uv run ruff format --check          # CI-style, fails if unformatted

# types
uv run mypy src

# alembic
uv run alembic revision --autogenerate -m "add foo table"
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic current

# dependency management
uv add <package>                    # runtime dep
uv add --dev <package>              # dev dep
uv sync                             # install/update everything from uv.lock
```

---

## Folder layout

See [`CLAUDE.md §3`](./CLAUDE.md) for the canonical structure. Concretely:

```
Backend/
├── src/app/
│   ├── api/v1/               # routers, one file per resource
│   ├── core/                 # config, security, db, logging, exceptions
│   ├── dependencies/         # FastAPI Depends() providers (auth, db)
│   ├── middleware/           # request-id, access log
│   ├── models/               # SQLAlchemy ORM
│   ├── repositories/         # all SQL lives here
│   ├── schemas/              # Pydantic I/O models
│   ├── services/             # business logic
│   └── main.py               # app factory
├── migrations/               # Alembic
├── tests/                    # 199 tests across 11 files
└── docs/                     # README, Backend_Reference.md, Postman collection
```

---

## Environment

All configuration is read by `app/core/config.py` from `.env`. The full
list of variables is documented in [`.env.example`](./.env.example). When
you add a new setting:

1. Add the field to `Settings` in `app/core/config.py`.
2. Add the variable to `.env.example` with a placeholder + one-line comment.
3. Add it to your local `.env`.

Do not read environment variables anywhere else in the code.

---

## Administration

### Admin user

The Phase 1 backend has **no admin-promotion endpoint** — `is_admin`
defaults to `False` on every registration, and there is deliberately
no API that flips it. This avoids the "first user to register becomes
god" race condition.

To grant the admin bit, run one SQL statement against `inventory_db`
after the operator has registered their account via `/api/v1/auth/register`:

```sql
UPDATE users SET is_admin = true WHERE email = 'you@example.com';
```

From the project root, via Docker:

```powershell
docker compose exec db psql -U postgres -d inventory_db -c ^
  "UPDATE users SET is_admin = true WHERE email = 'you@example.com';"
```

After the next login the new admin can call `GET /api/v1/users` and any
other admin-gated endpoint.

---

## Testing

The test suite runs against a real Postgres database (`inventory_db_test` by
default), with the schema rebuilt **via Alembic** at session start. This
gives us end-to-end confidence that the migrations themselves are correct;
a missing or wrong migration fails the gate immediately.

Per-test isolation uses a SAVEPOINT pattern: each test wraps its work in an
outer transaction that is rolled back at teardown, so tests cannot leak data
into each other even though the schema is shared.

```powershell
uv run pytest -q                                    # whole suite
uv run pytest -q tests/test_purchase_orders.py      # one file
uv run pytest -q -k "ship_so and insufficient"      # by keyword
uv run pytest -q --tb=short -x                      # stop on first fail
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `connection refused` on `localhost:5432` | Postgres container not running | `docker compose ps` from `Code/`; if not healthy, `docker compose up -d` |
| `database "inventory_db" does not exist` | Volume created before the init script existed | From `Code/`: `docker compose down -v` then `docker compose up -d` (wipes data) |
| `password authentication failed` | `DATABASE_URL` password doesn't match the container | Use `postgres` for both user and password in dev defaults |
| `uvicorn` import errors | Deps not installed | `uv sync` |
| `alembic: command not found` | Running it outside `uv run` | Prefix with `uv run alembic ...` |
| Test gate hangs in `alembic upgrade head` | Test DB unreachable | Confirm `TEST_DATABASE_URL` and that the test DB exists |

---

## Where this fits

```
React Frontend
     ↓
Backend (this service) ──► inventory_db (Postgres)
     ↓ internal HTTP   (Phase 9, deferred)
Integration Layer ──► integration_db (Postgres)
     ↓
Zoho Core APIs ──► Zoho CRM
```

The project-level README is at [`../README.md`](../README.md).
