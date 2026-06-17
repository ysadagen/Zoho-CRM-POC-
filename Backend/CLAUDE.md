# CLAUDE.md — Inventory Backend (FastAPI)

This file is the working contract for Claude (and any contributor) when writing
code inside `Backend/`. Read it before making changes. If a rule here conflicts
with a user instruction in chat, the user wins — but flag the conflict.

---

## 1. What this service is

The Inventory Backend is the source of truth for stock, items, customers,
vendors, purchase orders, and sales orders. It does **not** call Zoho directly.
All CRM traffic goes through the Integration Layer over an internal API.

Parent context: see `../README.md` for the full project overview.

**Working docs (read these for current state + roadmap):**
- `docs/Backend_Reference.md` — the current schema & API (source of truth).
- `proposal.md` — the pharmaceutical-inventory upgrade design + decisions.
- `execution.md` — the phase-by-phase build log; the pharma upgrade ships as
  ordered, non-breaking phases tracked there.

---

## 2. Tech stack (fixed for Phase 1)

```
Python        3.14
Package mgr   uv (uv init + uv venv already done)
Framework     FastAPI
Server        uvicorn
ORM           SQLAlchemy 2.x (async)
Migrations    Alembic
Validation    Pydantic v2
DB            PostgreSQL (inventory_db)
Auth          JWT
Tests         pytest + pytest-asyncio + httpx.AsyncClient
Lint/Format   ruff
Type check    mypy (strict on src/app)
Logging       stdlib logging + structlog (JSON in prod, console in dev)
```

Do not introduce Redis, Celery, Kafka, or any other infra without an explicit
go-ahead. Phase 1 stays lightweight.

---

## 3. Folder structure (canonical — do not deviate)

```
Backend/
├── .venv/
├── src/
│   └── app/
│       ├── __init__.py
│       ├── main.py                # FastAPI entry point — app factory only
│       │
│       ├── api/                   # HTTP layer. Thin. No business logic.
│       │   ├── __init__.py
│       │   └── v1/
│       │       ├── __init__.py
│       │       ├── users.py
│       │       └── auth.py
│       │
│       ├── core/                  # Cross-cutting: config, security, db, logging
│       │   ├── __init__.py
│       │   ├── config.py          # Pydantic Settings, reads .env
│       │   ├── security.py        # JWT, password hashing
│       │   ├── database.py        # engine, session factory, get_db dep
│       │   ├── logging.py         # structlog/logging configuration
│       │   └── exceptions.py      # AppError hierarchy + handlers
│       │
│       ├── models/                # SQLAlchemy ORM models only
│       │   ├── __init__.py
│       │   └── user.py
│       │
│       ├── schemas/               # Pydantic request/response schemas
│       │   ├── __init__.py
│       │   └── user.py
│       │
│       ├── services/              # Business logic. Orchestrates repos.
│       │   ├── __init__.py
│       │   └── user_service.py
│       │
│       ├── repositories/          # All DB access. Returns models, not rows.
│       │   ├── __init__.py
│       │   └── user_repo.py
│       │
│       ├── middleware/
│       │   ├── __init__.py
│       │   └── auth_middleware.py
│       │
│       ├── utils/                 # Pure helpers. No I/O, no framework deps.
│       │   ├── __init__.py
│       │   └── helpers.py
│       │
│       └── dependencies/          # FastAPI Depends() callables
│           ├── __init__.py
│           └── auth.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # shared fixtures (db, client, auth)
│   ├── test_users.py
│   └── test_auth.py
│
├── .env                           # gitignored, real secrets
├── .env.example                   # committed, placeholder values
├── .gitignore
├── .python-version
├── pyproject.toml
├── uv.lock
├── README.md
└── CLAUDE.md                      # this file
```

> **Note on infrastructure:** `docker-compose.yml` lives at the project root
> (`Code/docker-compose.yml`), not inside `Backend/`. The Postgres server is
> shared with the Integration Layer (one server, two databases:
> `inventory_db` and `integration_db`). Start it with
> `docker compose up -d` from the `Code/` directory.

> **Note on `scripts/`:** a `Backend/scripts/` folder holds standalone
> operational scripts (currently `seed_demo.py`, the deterministic
> intelligence-layer demo seeder). It is **not** imported by the app; scripts
> add `src` to `sys.path` themselves. Sanctioned by
> `INTELLIGENCE_SPECIFICATION.md` §16. `services/scoring/` (the Phase-2B engine
> subpackage) is likewise sanctioned there.

If you need a new concept (e.g. `events/`, `tasks/`), **ask first**. Don't
quietly invent new top-level packages.

---

## 4. Layer responsibilities (separation of concerns)

The dependency direction is one-way:

```
api  →  services  →  repositories  →  models
        ↑                ↑
        schemas          database session (via dependencies/)
```

| Layer            | Owns                                          | Forbidden                            |
|------------------|-----------------------------------------------|--------------------------------------|
| `api/`           | Routing, request/response shape, status codes | SQL, business rules                  |
| `schemas/`       | Pydantic models for I/O validation            | DB models, business logic            |
| `services/`      | Business rules, multi-step orchestration      | Raw SQL, FastAPI imports             |
| `repositories/`  | All DB queries (SQLAlchemy)                   | HTTP concerns, business rules        |
| `models/`        | ORM table definitions                         | Logic beyond hybrid_property/computed|
| `core/`          | App-wide config, security primitives          | Domain logic                         |
| `dependencies/`  | `Depends()` providers (auth, db, pagination)  | Business logic                       |
| `utils/`         | Pure functions                                | I/O, DB, network                     |

A route handler should usually be ≤ 10 lines: parse → call service → return.

---

## 5. How we work — spec-driven + test-driven

Every new feature follows this loop. Don't skip steps.

1. **Spec first.** Before code, write down (in chat or in a short markdown
   block inside the PR/commit message):
   - The endpoint(s) being added — method, path, request schema, response
     schema, error cases.
   - The business rule in one paragraph.
   - The DB tables/columns touched.
   If the spec is unclear, ask — don't guess.

2. **Tests first.** Write failing tests in `tests/` that encode the spec:
   - Happy path
   - Validation errors (Pydantic)
   - Business-rule violations (e.g. insufficient stock)
   - Auth/permission failures
   Run them, see them fail for the right reason.

3. **Implement minimally.** Write only enough code to make the tests pass.
   No speculative fields, no "while I'm here" refactors.

4. **Refactor under green.** Once tests pass, tidy. Tests stay green.

5. **Verify.** `uv run pytest`, `uv run ruff check`, `uv run mypy src`.

---

## 6. API design rules

- Versioned under `/api/v1/...`. New breaking shapes go to `/api/v2/...`,
  never mutate v1.
- Resource naming is plural and kebab-or-snake-consistent — pick one and stick
  to it. Default: lowercase plural nouns (`/api/v1/sales-orders`).
- One router per resource file in `api/v1/`. Mount in `main.py` via
  `app.include_router(...)`.
- Use proper status codes: `201` on create, `204` on delete, `404` for missing,
  `409` for conflict (e.g. duplicate), `422` only for Pydantic validation.
- Every endpoint declares `response_model=` and a `tags=[...]` for OpenAPI.
- Every endpoint has a short docstring — it shows up in `/docs`.
- Pagination: `?limit=&offset=` with sensible defaults. Return
  `{"items": [...], "total": N, "limit": L, "offset": O}`.
- No business data in URL query strings if it could be in the body for
  POST/PUT/PATCH.

---

## 7. Exception handling

- Define a small hierarchy in `core/exceptions.py`:
  ```
  AppError                     # base, has .status_code, .code, .message
   ├── NotFoundError               # 404
   ├── ConflictError               # 409
   ├── ValidationError             # 422 (business-rule, not Pydantic)
   ├── AuthenticationError         # 401
   └── AuthorizationError          # 403
  ```
- Register one exception handler in `main.py` that turns `AppError` into a
  consistent JSON response:
  ```json
  {"error": {"code": "INSUFFICIENT_STOCK", "message": "..."}}
  ```
- **Services raise domain exceptions. The API layer never catches them** —
  the global handler does. Don't sprinkle `try/except HTTPException` in routes.
- Never swallow exceptions silently. If you catch, you either re-raise, convert
  to a domain exception, or log at `ERROR` with context — pick one.
- `assert` is for tests only. Do not use it for runtime checks.

---

## 8. Logging

- Configure once in `core/logging.py`, called from `main.py` startup.
- JSON output in non-dev environments. Console (human-readable) in dev.
- Every log line carries: `timestamp`, `level`, `logger`, `message`,
  `request_id` (when in request context), plus structured fields for the event.
- Use module-level loggers: `logger = logging.getLogger(__name__)`.
  Don't use the root logger.
- Log levels — be disciplined:
  - `DEBUG`  — verbose, dev-only. Variable dumps, SQL.
  - `INFO`   — lifecycle events worth keeping (request start/end, sync
    triggered, order created). One line per business event.
  - `WARNING`— recoverable oddity (retryable failure, deprecated path hit).
  - `ERROR`  — request failed, sync failed permanently, unexpected exception.
  - `CRITICAL` — app can't continue.
- **Never log secrets, tokens, full Authorization headers, full request bodies
  with PII, or raw passwords.** Redact in a middleware/processor.
- Request-id middleware: generate/propagate `X-Request-ID` and bind it to
  every log line in that request.

---

## 9. Configuration & secrets

- All config goes through `core/config.py` as a `pydantic_settings.BaseSettings`
  subclass. Read from `.env`. Never `os.getenv` directly in business code.
- `.env.example` is the source of truth for which variables exist. Keep it in
  sync — when you add a setting, add it to `.env.example` in the same commit.
- Secrets never get logged, printed, or hardcoded. They're not committed.
  `.env` is already in `.gitignore`.

---

## 10. Database

- Async SQLAlchemy. One engine, one `async_sessionmaker`, exposed via a
  `get_db` dependency in `core/database.py`.
- Migrations are mandatory. Every schema change → an Alembic revision in the
  same commit. Never edit the DB out of band.
- Repositories own SQL. Services compose repositories. Don't query from a
  route or a service body directly.
- Use transactions explicitly when a service touches more than one repo. A
  failed Zoho sync must not roll back the local stock movement — local commit
  first, sync request after (see `README.md` core workflow).

### 10.1 Refresh after commit when columns are server-managed on update

If a column has a server-side `onupdate=` (e.g. `updated_at` set by
`func.now()`), SQLAlchemy marks that column **stale on the in-memory
instance** after a `commit()` so the new server value can be fetched back.
The next attribute access tries to fetch sync — outside async context this
explodes with `MissingGreenlet: greenlet_spawn has not been called`.

**Rule:** in every service method that mutates and commits a row whose
return value is then handed to Pydantic (i.e. every PATCH-style path),
end with:

```python
await self._session.commit()
await self._session.refresh(item)   # capture server-side updated_at
return item
```

`expire_on_commit=False` on the session does **not** override this — it
exempts ordinary columns from expiry but server-onupdate columns get a
separate "needs refresh" flag. INSERT paths are unaffected; the trap is
update-only.

### 10.2 Row-level audit fields

Every business table that records user-driven changes carries:

```python
created_by_user_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("users.id", ondelete="RESTRICT"),
    nullable=False,
    index=True,
)
updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("users.id", ondelete="RESTRICT"),
    nullable=False,
)
```

`ON DELETE RESTRICT` — losing audit on user delete would defeat the
purpose; we use soft-delete via `is_active=false` on the user instead. The
service signatures take `*, actor_id: uuid.UUID` (or `*, actor: User`) and
populate both fields on create, only `updated_by_user_id` on update.

The `users` table itself does **not** carry these fields (chicken/egg
with the first user). If you ever add `created_by_user_id` to `users`, it
must be nullable and the bootstrap admin must be handled explicitly.

### 10.3 CHECK constraints for invariants

When an invariant must hold no matter which code path writes the row,
enforce it at the DB with a `CheckConstraint`, not just at the Pydantic
schema. The schema is *defence in depth*; the DB is the *contract*.

```python
class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="ck_items_stock_quantity_non_negative"),
        ...
    )
```

The constraint protects against three classes of bug we cannot lint away:
(1) buggy internal services that bypass the schema layer; (2) raw SQL
written by an operator; (3) a future code path that legitimately writes
that column but forgets the check. Pair every invariant assertion with a
test that bypasses the API (`db_session.add(...)` directly) and asserts
`IntegrityError` — that test is what proves the DB-level safety net is
actually wired.

### 10.4 String normalisation on input schemas

Set `str_strip_whitespace=True` in `model_config` on every `*Create` and
`*Update` schema. Trailing whitespace in identifiers like SKU or email is
the canonical source of "why are there two of these in the UI that look
identical" bugs. One line per schema, no downside.

---

## 11. Testing

- All tests live in `tests/`, mirror the `src/app/` structure where useful.
- Use `pytest` + `pytest-asyncio` + `httpx.AsyncClient` against the app.
- Fixtures in `conftest.py`:
  - `db_session` — transactional, rolled back per test
  - `client` — `AsyncClient` bound to the app
  - `auth_headers` — pre-baked JWT for an authenticated user
- Test naming: `test_<unit>_<scenario>_<expected>`, e.g.
  `test_create_sales_order_with_insufficient_stock_returns_409`.
- Aim for: every endpoint has at least one happy-path test and one failure
  test. Every service method with branching has a test per branch.
- Don't mock what you can use for real (use a real test Postgres via Docker
  for integration tests). Mock only at true boundaries (Integration Layer HTTP
  client, time, randomness).
- `uv run pytest -q` must pass before any commit.

---

## 12. Code quality bar (DRY, minimal, readable)

- **Write only what's needed.** No speculative abstractions, no "future-proof"
  config knobs, no helpers used in exactly one place.
- **DRY, but not prematurely.** Three similar lines is fine. Three similar
  *functions* is a smell. Extract on the third occurrence, not the second.
- **Readable over clever.** Multi-line expressions beat dense one-liners.
  Self-explanatory names beat comments.
- **Comments:** only when *why* is non-obvious. Don't restate *what*. No
  block-comment banners, no decorative `# === foo ===` lines.
- **Types everywhere.** Public functions, service methods, repository methods,
  and route handlers must be fully type-annotated. `mypy` is strict.
- **Imports:** absolute (`from app.services.user_service import ...`), grouped
  stdlib / third-party / first-party, sorted by ruff/isort.
- **No dead code.** Delete unused imports, unused params, unused branches.
  Don't leave `# TODO` without an owner and a reason.

---

## 13. Definition of Done (per change)

A change is done when **all** of these are true:

- [ ] Spec captured (chat/PR description).
- [ ] Tests added/updated, all green: `uv run pytest`.
- [ ] `uv run ruff check` clean.
- [ ] `uv run mypy src` clean.
- [ ] No new `WARNING`+ logs on a normal request path.
- [ ] `.env.example` updated if config changed.
- [ ] Alembic migration committed if schema changed.
- [ ] `/docs` (OpenAPI) renders the new endpoint with correct schemas.
- [ ] No unrelated changes mixed in.

---

## 14. Commands cheat-sheet

```powershell
# install / sync deps
uv sync

# add a runtime dep
uv add fastapi

# add a dev dep
uv add --dev pytest pytest-asyncio httpx ruff mypy

# run the app (dev)
uv run uvicorn app.main:app --reload --app-dir src

# tests
uv run pytest -q
uv run pytest -q tests/test_users.py::test_create_user_returns_201

# lint + types
uv run ruff check
uv run ruff format
uv run mypy src

# alembic
uv run alembic revision --autogenerate -m "add users table"
uv run alembic upgrade head
```

> **If `uv run` is blocked** (some dev machines run Application Control, which
> rejects `uv` spawning a child exe with `os error 4551`), invoke the tool as a
> module on the active venv instead: `python -m alembic upgrade head`,
> `python -m pytest -q`, `python -m ruff check`, `python -m mypy src`. The test
> bootstrap (`tests/conftest.py`) already uses `sys.executable -m alembic` for
> this reason.

---

## 15. Working agreement for Claude

When asked to add or change something in `Backend/`:

1. Re-read this file if it's been a while.
2. State the spec back in one short paragraph before coding.
3. Show the test plan, write tests first.
4. Implement the minimum. No bonus features.
5. Run pytest + ruff + mypy. Report the results honestly.
6. If a rule here is getting in the way, say so — don't quietly bend it.

Anything outside `Backend/` is off-limits unless the user explicitly opens
that scope.
