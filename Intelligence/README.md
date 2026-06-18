# Intelligence Service

The deterministic **AI scoring** service for the JSPL CRM POC — a standalone
FastAPI app that runs the four scoring engines (lead scoring, customer health,
effort & efficiency, beat planning) over the CRM data the Backend owns.

It is a **separate service** from the Backend (its own process, port, build,
tests, and migration chain) that **shares the same PostgreSQL database**
(`inventory_db`): it *reads* the CRM tables (customers, leads, activities,
invoices, sales orders, items, users) and *owns* the scoring tables
(`scoring_configs` + four snapshot tables). It validates the **same JWTs** the
Backend issues (shared `JWT_SECRET_KEY`) — it never issues tokens itself.

> Spec: `../INTELLIGENCE_SPECIFICATION.md`. Engineering contract:
> `CLAUDE.md`. Ports: 8000 Backend · 8001 Integration Layer · **8002 Intelligence**.

---

## Architecture

```
api/v1/intelligence.py     thin routes  → services
services/scoring/          the engines (pure functions + orchestrators)
repositories/              read-only CRM access + owned-table access
models/                    CRM read-models (consumed) + scoring models (owned)
core/                      config, db, logging, security (JWT verify), exceptions
```

* **Live-on-read** for all four engines: scores are computed on each GET (the
  cohort math depends on the whole active set). Lead scores are **not**
  persisted on write — the Backend has no knowledge of scoring.
* **Snapshots** (trend history) are produced by the admin `POST
  /intelligence/recompute` endpoint, intended to run nightly.
* Every score carries the `config_id` it used; weights live in
  `scoring_configs`, never in code (changing a weight is a new version row).

## Endpoints (all under `/api/v1/intelligence`, JWT-protected)

| Method & path | Purpose |
|---|---|
| `GET /lead-scores[/{lead_id}]` | Live lead scores (filter classification / rep); detail + snapshot history |
| `GET /customer-health[/{customer_id}]` | Live customer health; detail + CPS/CRS breakdown + trend |
| `GET /effort-efficiency[/{user_id}]` | Live per-rep effort & efficiency cohort (period override); detail + trend |
| `GET /beat-plan?rep_user_id=&max_visits=` | Visit-priority ranking + district clusters + suggested beat |
| `GET/POST /configs` *(admin)* | List / create+activate scoring-config versions |
| `POST /recompute` *(admin)* | Recompute + snapshot one engine or all four |

---

## Quick start

```powershell
# 1. Configure (DATABASE_URL + JWT_SECRET_KEY MUST match the Backend)
copy .env.example .env   # then edit

# 2. Install deps (its own venv)
uv sync

# 3. Apply this service's migrations (creates the scoring tables in the shared DB)
#    PREREQUISITE: the Backend must be migrated first — the scoring tables FK to
#    its CRM tables (users, customers, leads, ...). On a fresh DB run, in order:
#        cd ..\Backend ; uv run alembic upgrade head     # creates CRM tables
#        cd ..\Intelligence
uv run alembic upgrade head     # or: .\.venv\Scripts\python.exe -m alembic upgrade head

# 4. Run (port 8002)
uv run uvicorn app.main:app --reload --app-dir src --port 8002
#    → http://localhost:8002/docs
```

> If `uv run` is blocked by local Application Control, invoke tools as modules
> on the venv: `.\.venv\Scripts\python.exe -m alembic upgrade head`, etc.

### Migrating an existing dev DB (one-time reconciliation)

If the scoring tables were previously created by the **Backend** (before this
service existed), reconcile the two migration pointers once — the tables stay,
only the bookkeeping moves:

```powershell
# Backend: forget the scoring revisions (they are no longer the Backend's)
cd ..\Backend ;  .\.venv\Scripts\python.exe -m alembic stamp f4b6c8e0a3d5
# Intelligence: adopt the existing scoring tables without recreating them
cd ..\Intelligence ;  .\.venv\Scripts\python.exe -m alembic stamp head
```

On a fresh DB, none of this is needed — `alembic upgrade head` creates them.

---

## Common commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q        # tests
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m ruff format src tests
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### Nightly recompute

`POST /api/v1/intelligence/recompute {"engine": null}` (admin token) refreshes
snapshots for all engines. Schedule it with Windows Task Scheduler / cron — no
new infrastructure:

```powershell
curl -X POST http://localhost:8002/api/v1/intelligence/recompute ^
  -H "Authorization: Bearer <admin-token>" -H "Content-Type: application/json" ^
  -d "{\"engine\": null}"
```

---

## Testing

The test schema is built from `Base.metadata` via `create_all` (the CRM
read-models **and** the scoring tables) and the v1 configs are seeded — the
same active configs the production migration seeds. Each test runs in a
transaction rolled back at the end. Because this service has no auth endpoints,
authenticated test clients mint a JWT directly with the shared secret. The
canonical vectors (LS-1, EE-1, CH-1, BP-1) are asserted to two decimals against
the pure engine functions; integration tests insert CRM rows via the factories
and exercise the live endpoints.
