# Integration Layer — Zoho CRM Bridge (FastAPI)

Sits between the Inventory **Backend** and **Zoho CRM**. The only service in
the system that talks to Zoho. Owns OAuth tokens, CRM record mappings, sync
logs, idempotency keys, and webhook intake.

> The engineering contract for this service is in [`CLAUDE.md`](./CLAUDE.md).
> Read it before changing code.

---

## Build status

Built and tested today (Track A — ingest-led, see
`../ZOHO_INTEGRATION_EXECUTION_PLAN.md`):

- **A0** — app factory, config, Alembic + the 5-table migration, OAuth
  `token_service`, `ZohoClient` read path. Endpoints: `GET /health`,
  `GET /health/zoho`.
- **A1** — Zoho → app ingest (`BackendClient` + `ingest_service`). Endpoints:
  `POST /api/v1/ingest/run`, `GET /api/v1/ingest/status` (internal-key auth).

Planned / not yet built (Track B — push, deferred, needs a paid Zoho edition):
`/api/v1/sync/...`, `/api/v1/webhooks/zoho`, `/api/v1/admin/...`. Sections below
describing those endpoints document the **target** contract, not current state.

---

## Prerequisites

- **Python 3.14** (`.python-version` pins it)
- **uv** — package manager. Install: <https://docs.astral.sh/uv/>
- **Docker Desktop** — runs local Postgres
- **pgAdmin** *(optional)* — GUI for browsing the database

---

## Quick start

Run these once, in order, from PowerShell.

### 1. Start the database (shared with Backend)

From the **project root** (`Code/`), not from `Integration Layer/`:

```powershell
cd "..\"                  # go up to Code/
docker compose up -d
docker compose ps         # wait until STATUS shows (healthy)
```

This boots one Postgres server (`inventory_crm_server`) hosting two
databases: `inventory_db` and `integration_db`. This service uses
`integration_db`.

### 2. Configure the Integration Layer

From the `Integration Layer/` folder:

```powershell
cd "Integration Layer"
copy .env.example .env
```

Edit `.env`:
- `INTERNAL_API_KEY` — generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
  **Must match** the Backend's `INTEGRATION_LAYER_API_KEY` value.
- `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN` — from your
  Zoho API Console.
- `ZOHO_WEBHOOK_SECRET` — generate with the same `secrets.token_urlsafe(48)`.
- `ZOHO_ACCOUNTS_URL` / `ZOHO_API_BASE_URL` — make sure the data-centre
  suffix (`.in`, `.com`, `.eu`, …) matches your Zoho account.
- Leave other values at their defaults for local dev.

### 3. Install dependencies

```powershell
uv sync
```

### 4. Apply database migrations

```powershell
uv run alembic upgrade head
```

### 5. Run the dev server

```powershell
uv run uvicorn app.main:app --reload --app-dir src --port 8001
```

Then open <http://localhost:8001/docs> for the OpenAPI explorer.

Note the port is **8001** (Backend runs on 8000), so both services can run
side by side locally.

---

## Common commands

```powershell
# tests
uv run pytest -q
uv run pytest -q tests/test_ingest_service.py::test_run_creates_lead_activity_and_applies_won_deal

# lint + format
uv run ruff check
uv run ruff format
uv run ruff format --check          # CI-style, fails if unformatted

# types
uv run mypy src

# alembic
uv run alembic revision --autogenerate -m "add zoho_tokens table"
uv run alembic upgrade head
uv run alembic downgrade -1

# dependency management
uv add <package>                    # runtime dep
uv add --dev <package>              # dev dep
uv sync                             # install/update everything from uv.lock
```

---

## Folder layout

See [`CLAUDE.md §3`](./CLAUDE.md) for the canonical structure and the rules
for each layer. The dependency direction is:

```
api  →  services  →  repositories  →  models
                  ↘
                   clients/zoho  (outbound HTTP — only place that imports httpx)
```

Routes are thin (≈ ≤ 10 lines). Services orchestrate idempotency, mappings,
and Zoho calls. All SQL lives in repositories. All Zoho HTTP lives in
`clients/zoho/`.

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

## Inbound auth (from Backend / ingest trigger)

Every request to `/api/v1/ingest/...` (live today) and, when built,
`/api/v1/sync/...` and `/api/v1/admin/...` must include:

```
X-Internal-API-Key: <INTERNAL_API_KEY value>
```

Sync requests must also include an `Idempotency-Key` header (UUID v4). Same
key + same payload returns the cached response; same key + different payload
returns 409.

---

## Inbound webhooks (from Zoho)

`POST /api/v1/webhooks/zoho` is publicly reachable but authenticated by
HMAC signature over the raw request body, computed with
`ZOHO_WEBHOOK_SECRET`. Missing or invalid signature → 401.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `connection refused` on `localhost:5432` | Postgres container not running | `docker compose ps` from `Code/`; if not healthy, `docker compose up -d` |
| `database "integration_db" does not exist` | Volume created before init scripts existed | From `Code/`: `docker compose down -v` then `docker compose up -d --build` (wipes data) |
| `401 Unauthorized` calling `/sync/...` | `X-Internal-API-Key` missing or wrong | Confirm both services' `.env` files have the **same** value (Backend's `INTEGRATION_LAYER_API_KEY` == this service's `INTERNAL_API_KEY`) |
| `401 Unauthorized` calling `/webhooks/zoho` | HMAC mismatch | Confirm `ZOHO_WEBHOOK_SECRET` matches what's configured in the Zoho webhook settings |
| Zoho calls all return `INVALID_TOKEN` | Wrong data centre | `ZOHO_ACCOUNTS_URL` and `ZOHO_API_BASE_URL` must both use the same suffix (`.in` / `.com` / `.eu`) and that suffix must match your Zoho account |

---

## Where this fits

```
React Frontend
     ↓
Backend ──► inventory_db (Postgres)
     ↓ internal HTTP (X-Internal-API-Key + Idempotency-Key)
Integration Layer (this service) ──► integration_db (Postgres)
     ↓ OAuth 2.0
Zoho Core APIs ──► Zoho CRM
```

The project-level README is at [`../README.md`](../README.md).
