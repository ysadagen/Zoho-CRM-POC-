# CLAUDE.md — Intelligence Service (FastAPI)

Working contract for anyone (human or AI) changing code in `Intelligence/`.
Read it before making changes. If a rule here conflicts with a user
instruction in chat, the user wins — but flag the conflict.

---

## 1. What this service is

The Intelligence service runs the four deterministic scoring engines (lead
scoring, customer health, effort & efficiency, beat planning) defined in
`../INTELLIGENCE_SPECIFICATION.md`. It is a **separate service** from the
Backend that **shares the same PostgreSQL database** (`inventory_db`):

- It **reads** the Backend-owned CRM tables (customers, leads, activities,
  invoices, sales orders, items, users) — never writes them.
- It **owns** the scoring tables (`scoring_configs` + the four snapshot
  tables) and migrates them via its own Alembic chain.
- It **validates** the Backend's JWTs (shared `JWT_SECRET_KEY`); it issues no
  tokens and has no auth/CRUD endpoints for CRM data.

This separation reverses spec Decision **D-1** at the project owner's
direction (see the spec's decisions log).

## 2. Tech stack (fixed)

Python 3.14 · FastAPI · SQLAlchemy 2.x async · Alembic · Pydantic v2 ·
PostgreSQL (shared `inventory_db`) · JWT verify (python-jose) · pytest ·
ruff · mypy (strict) · structlog. No Redis/Celery/queues.

## 3. Layout (canonical)

```
src/app/
  main.py                  app factory only
  api/v1/intelligence.py   thin routes → services
  core/                    config, database, logging, security (JWT verify), exceptions
  dependencies/auth.py     get_current_user / require_admin (verify-only)
  middleware/              request_id, access_log
  models/                  CRM read-models (consumed) + scoring models (owned)
  schemas/intelligence.py  request/response shapes
  services/scoring/        engines (pure functions + orchestrators) + config/recompute
  repositories/            read-only CRM access + owned-table access
migrations/                own Alembic chain (version_table=alembic_version_intelligence)
tests/                     pure-vector + integration tests; factories for CRM rows
```

Dependency direction is one-way: `api → services → repositories → models`.
Routes are thin (parse → call service → return). Services hold business rules;
repositories own all SQL.

## 4. Hard rules

- **Read-only on CRM tables.** Repositories for customers/leads/activities/
  invoices/sales-orders/items/users expose only reads. Never INSERT/UPDATE a
  CRM table — that is the Backend's job.
- **Own only the scoring tables.** Schema changes to scoring tables get an
  Alembic revision in the same commit. The CRM read-models mirror just the
  columns the engines need; they are materialised in the test schema via
  `create_all` but never migrated here.
- **Weights live in `scoring_configs`, not code.** Every engine reads its
  active config; every snapshot records the `config_id`. A weight change is a
  new config version (a new row), never an edit.
- **Engines are pure functions** over plain dataclasses (no session, no I/O),
  so the canonical vectors (LS-1/EE-1/CH-1/BP-1) are unit-testable to the
  decimal. A thin orchestrator gathers inputs via repositories and computes
  live (or snapshots on recompute).
- **Missing data never blocks scoring** — every parameter has a documented
  default, recorded in `defaults_applied`.
- **Errors** raise the `AppError` hierarchy in `core/exceptions.py`; the global
  handler in `main.py` maps them to `{"error": {code, message, request_id}}`.
  Services raise; routes never catch.
- **Logging** is structured (structlog), one event per scoring/recompute run;
  never log tokens or secrets.

## 5. How we work — spec + test driven

Spec first → tests → minimal implementation → green → `ruff` + `mypy --strict`.
Mandatory coverage: canonical vectors to two decimals, every band edge, every
default, cohort edges, config versioning, admin-gating, 404s. `pytest`,
`ruff check`, `mypy src` must pass before any commit.

## 6. Definition of Done

- [ ] Spec captured · tests green (`pytest`) · `ruff check` clean · `mypy src` clean
- [ ] Alembic revision committed if a scoring table changed
- [ ] No CRM-table writes introduced · no weights hardcoded
- [ ] `/docs` renders new endpoints · no unrelated changes mixed in

## 7. Commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir src --port 8002
```

(If `uv run` is blocked by local Application Control, use `python -m <tool>` on
the venv as above.)
