# Backend — Inventory Service (FastAPI)

Source of truth for inventory, items, customers, vendors, purchase orders,
sales orders, and stock movements. Talks to Zoho only via the Integration
Layer; never directly.

> The engineering contract for this service is in [`CLAUDE.md`](./CLAUDE.md).
> Read it before changing code.

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

This boots one Postgres server (`inventory_crm_server`) hosting two
databases: `inventory_db` and `integration_db`. Data persists in the
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

*(Skip this step until Phase 2 of the build plan — Alembic isn't wired yet.)*

```powershell
uv run alembic upgrade head
```

### 5. Run the dev server

*(Skip this step until Phase 1 of the build plan — the app factory isn't
written yet.)*

```powershell
uv run uvicorn app.main:app --reload --app-dir src --port 8000
```

Then open <http://localhost:8000/docs> for the OpenAPI explorer.

---

## Common commands

```powershell
# tests
uv run pytest -q
uv run pytest -q tests/test_users.py::test_create_user_returns_201

# lint + format
uv run ruff check
uv run ruff format
uv run ruff format --check          # CI-style, fails if unformatted

# types
uv run mypy src

# alembic
uv run alembic revision --autogenerate -m "add users table"
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
for each layer (`api/`, `services/`, `repositories/`, `models/`, …).

Short version of the dependency direction:

```
api  →  services  →  repositories  →  models
```

Routes are thin (≈ ≤ 10 lines). Business rules live in services. All SQL
lives in repositories. No exceptions.

---

## Environment

All configuration is read by `app/core/config.py` from `.env`. The full
list of variables and what they do is documented in
[`.env.example`](./.env.example). When you add a new setting:

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

After the next login the new admin can call `GET /api/v1/users` and
any other admin-gated endpoint. Phase 2 (RBAC) will replace this with
a proper role model.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `connection refused` on `localhost:5432` | Postgres container not running | `docker compose ps` from `Code/`; if not healthy, `docker compose up -d` |
| `database "inventory_db" does not exist` | Volume created before the init script existed | From `Code/`: `docker compose down -v` then `docker compose up -d` (wipes data) |
| `password authentication failed` | `DATABASE_URL` password doesn't match the container | Use `postgres` for both user and password in dev defaults |
| `uvicorn` import errors | Deps not installed | `uv sync` |
| `alembic: command not found` | Running it outside `uv run` | Prefix with `uv run alembic ...` |

---

## Where this fits

```
React Frontend
     ↓
Backend (this service) ──► inventory_db (Postgres)
     ↓ internal HTTP
Integration Layer ──► integration_db (Postgres)
     ↓
Zoho Core APIs ──► Zoho CRM
```

The project-level README is at [`../README.md`](../README.md).
