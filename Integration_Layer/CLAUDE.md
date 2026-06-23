# CLAUDE.md — Integration Layer (FastAPI)

This file is the working contract for Claude (and any contributor) when
writing code inside `Integration Layer/`. Read it before making changes. If a
rule here conflicts with a user instruction in chat, the user wins — but flag
the conflict.

---

> **Scope note (current engagement) — read with `../ZOHO_INTEGRATION_EXECUTION_PLAN.md`.**
> The integration is split into two tracks. **Track A (build first) — ingest:**
> pull Zoho Leads/Activities/Deals into the Backend so the AI effort/efficiency
> engine can score rep productivity (Zoho **Free**, 3 users). **Track B (deferred,
> needs a paid Zoho edition) — push:** mirror Customers/Vendors/Items/SO/PO into
> Zoho. Every rule below (layering, idempotency, Zoho client, errors, tests)
> applies to **both** tracks; ingest specifics are in **§19**.

## 1. What this service is

The Integration Layer sits between the **Inventory Backend** and **Zoho CRM**.
It is the only service in the system that talks to Zoho.

It owns:

- **OAuth lifecycle** for Zoho (`zoho_tokens` table) — refreshing access
  tokens, persisting refresh tokens, handling expiry.
- **CRM mappings** (`crm_mappings`) — the bridge between local entity IDs
  (customers, vendors, sales orders, purchase orders) and their Zoho record IDs;
  for ingest, also between Zoho Leads/Activities/Deals/Users and their local
  counterparts (used for dedupe + rep attribution).
- **Sync logs** (`sync_logs`) — every outbound sync **and** inbound ingest
  attempt, success or failure, with payload + response + retry count.
- **Idempotency** (`idempotency_keys`) — incoming Backend requests carry an
  `Idempotency-Key`; we dedupe so a retried sync never creates a duplicate
  Zoho record. (Ingest dedupes on the Zoho record id instead — see §19.)
- **Webhook intake** (`webhook_events`) — Zoho → us events, signature-verified,
  stored, then processed.
- **Ingest (Track A)** — pulling Zoho Leads, Activities, and won Deals and
  writing them into the Backend (via its API, never cross-DB) so the AI layer
  can score rep productivity. One-way (Zoho → app), idempotent, app-canonical.
  See **§19**.
- **Retries / backoff** for transient Zoho failures, and a dead-letter
  state for permanently failing syncs.

It does **not**:

- Hold inventory business state (stock, line items, etc.) — that's the Backend.
- Have user-facing endpoints. Its callers are the Backend, a scheduled ingest
  trigger, and Zoho's webhook delivery system — **not** the React frontend.

Parent context: see `../README.md` for the full project overview.

```
Track B (push):    Backend ──internal API──► Integration Layer ──Zoho APIs──► Zoho CRM
Track A (ingest):  Backend ◄──internal API── Integration Layer ◄──Zoho APIs── Zoho CRM
                                                    │
                                                    └── integration_db
                                                         (zoho_tokens, crm_mappings,
                                                          sync_logs, idempotency_keys,
                                                          webhook_events)
```

---

## 2. Tech stack (fixed for Phase 1)

```
Python        3.14
Package mgr   uv (uv init + uv venv already done)
Framework     FastAPI
Server        uvicorn
HTTP client   httpx (AsyncClient) — for Zoho + for being called by Backend
ORM           SQLAlchemy 2.x (async)
Migrations    Alembic
Validation    Pydantic v2 / pydantic-settings
DB            PostgreSQL (integration_db)
Auth (in)     Shared internal API key (header) — service-to-service only
Auth (out)    Zoho OAuth 2.0 (refresh-token flow)
Tests         pytest + pytest-asyncio + httpx.AsyncClient + respx (HTTP mock)
Lint/Format   ruff
Type check    mypy (strict on src/app)
Logging       stdlib logging + structlog (JSON in prod, console in dev)
```

Do **not** introduce Celery, Redis, Kafka, or any background worker
infrastructure without explicit approval. Phase 1 stays lightweight — retries
are handled inline with bounded attempts; anything that can't reconcile
in-process is parked in `sync_logs` with `status = FAILED_PERMANENT` and
re-driven by an admin endpoint.

---

## 3. Folder structure (canonical — do not deviate)

Same skeleton as the Backend, but the contents of each layer reflect this
service's job (Zoho client, token manager, sync, webhooks).

```
Integration Layer/
├── .venv/
├── src/
│   └── app/
│       ├── __init__.py
│       ├── main.py                    # FastAPI app factory only
│       │
│       ├── api/                       # HTTP layer. Thin. No business logic.
│       │   ├── __init__.py
│       │   └── v1/
│       │       ├── __init__.py
│       │       ├── sync.py            # Track B push: POST /sync/customers, /vendors,
│       │       │                      #     /items, /sales-orders, /purchase-orders
│       │       ├── ingest.py          # Track A: POST /ingest/run (Zoho → app) + status — see §19
│       │       ├── webhooks.py        # POST /webhooks/zoho
│       │       ├── admin.py           # GET /sync-logs, POST /sync-logs/{id}/retry
│       │       └── health.py          # /health, /health/zoho
│       │
│       ├── core/                      # Cross-cutting: config, db, logging, errors, security
│       │   ├── __init__.py
│       │   ├── config.py              # Pydantic Settings (Zoho creds, DB, internal key)
│       │   ├── database.py            # async engine, session factory, get_db
│       │   ├── logging.py             # structlog/logging configuration
│       │   ├── exceptions.py          # AppError hierarchy + Zoho-specific errors
│       │   └── security.py            # internal API key check, webhook signature verify
│       │
│       ├── models/                    # SQLAlchemy ORM models
│       │   ├── __init__.py
│       │   ├── zoho_token.py
│       │   ├── crm_mapping.py
│       │   ├── sync_log.py
│       │   ├── idempotency_key.py
│       │   └── webhook_event.py
│       │
│       ├── schemas/                   # Pydantic request/response schemas
│       │   ├── __init__.py
│       │   ├── health.py              # health probe responses (A0, built)
│       │   ├── ingest.py              # ingest run summary + status (A1, built)
│       │   ├── sync.py                # incoming sync payloads from Backend (Track B)
│       │   ├── webhook.py             # Zoho webhook payload shapes (Track B)
│       │   └── admin.py               # (Track B)
│       │
│       ├── services/                  # Business logic. Orchestrates repos + Zoho client.
│       │   ├── __init__.py
│       │   ├── token_service.py       # get-or-refresh access token, persistence
│       │   ├── sync_service.py        # Track B: push state machine (idempotency → mapping → call → log)
│       │   ├── ingest_service.py      # Track A: pull Zoho → map + attribute → write to Backend (idempotent) — §19
│       │   ├── webhook_service.py     # verify + persist + dispatch
│       │   └── mapping_service.py     # local_id ↔ zoho_id resolution (push + ingest)
│       │
│       ├── repositories/              # All DB queries
│       │   ├── __init__.py
│       │   ├── zoho_token_repo.py
│       │   ├── crm_mapping_repo.py
│       │   ├── sync_log_repo.py
│       │   ├── idempotency_repo.py
│       │   └── webhook_event_repo.py
│       │
│       ├── clients/                   # Outbound HTTP clients (this service is special — it has them)
│       │   ├── __init__.py
│       │   ├── zoho/
│       │   │   ├── __init__.py
│       │   │   ├── client.py          # ZohoClient: thin httpx wrapper, auth header, retries
│       │   │   ├── oauth.py           # ZohoOAuthClient: refresh-token grant (A0)
│       │   │   ├── endpoints.py       # URL builders / endpoint constants
│       │   │   └── errors.py          # ZohoAPIError, ZohoRateLimitError, ZohoAuthError
│       │   └── backend/               # 2nd outbound integration: IL → Backend ingest (A1)
│       │       ├── __init__.py
│       │       ├── client.py          # BackendClient: POSTs ingested records to the Backend
│       │       └── errors.py          # BackendError hierarchy
│       │
│       ├── middleware/
│       │   ├── __init__.py
│       │   ├── auth_middleware.py     # internal API key check on /sync, /admin
│       │   └── request_id.py          # generate/propagate X-Request-ID
│       │
│       ├── utils/                     # Pure helpers. No I/O, no framework deps.
│       │   ├── __init__.py
│       │   ├── backoff.py             # exponential backoff with jitter (pure function)
│       │   └── signatures.py          # HMAC verification helpers (pure)
│       │
│       └── dependencies/              # FastAPI Depends() callables
│           ├── __init__.py
│           ├── auth.py                # require_internal_api_key (verify_zoho_signature → Track B)
│           ├── db.py                  # get_db
│           ├── zoho.py                # http client, oauth client, token service, ZohoClient (A0)
│           └── ingest.py              # BackendClient + ingest service providers (A1)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_sync.py
│   ├── test_webhooks.py
│   ├── test_token_service.py
│   ├── test_zoho_client.py            # uses respx to mock Zoho HTTP
│   └── test_admin.py
│
├── .env
├── .env.example
├── .gitignore
├── .python-version
├── pyproject.toml
├── uv.lock
├── README.md
└── CLAUDE.md                          # this file
```

> **Note on infrastructure:** `docker-compose.yml` lives at the project root
> (`Code/docker-compose.yml`), not inside `Integration Layer/`. The Postgres
> server is shared with the Backend (one server, two databases:
> `inventory_db` and `integration_db`). Start it with
> `docker compose up -d` from the `Code/` directory.

Notes on the deltas from the Backend layout:

- A `clients/zoho/` package exists here. The Backend has no such package
  because the Backend never calls third-party APIs.
- `api/v1/users.py` and `api/v1/auth.py` are **gone**. There are no user
  accounts in this service. Auth is a single shared internal API key for the
  Backend, plus webhook signature verification for Zoho.
- `models/user.py` is gone. The integration DB has no users.
- `services/` is bigger because this service has more orchestration: tokens,
  sync, webhooks, mappings.

If you need a new concept (e.g. a second outbound integration), **ask first**.
Don't quietly invent new top-level packages.

---

## 4. Layer responsibilities (separation of concerns)

```
api  →  services  →  repositories  →  models
                  ↘
                   clients/zoho  (outbound HTTP)
```

| Layer            | Owns                                                          | Forbidden                                  |
|------------------|---------------------------------------------------------------|--------------------------------------------|
| `api/`           | Routing, request/response shape, status codes                 | SQL, Zoho calls, business rules            |
| `schemas/`       | Pydantic models for I/O validation                            | DB models, business logic                  |
| `services/`      | Orchestration (idempotency → mapping → Zoho call → log)       | Raw SQL, FastAPI imports, raw httpx        |
| `repositories/`  | All DB queries (SQLAlchemy)                                   | HTTP concerns, business logic              |
| `clients/zoho/`  | All Zoho HTTP traffic, auth header injection, error mapping   | DB access, persistence                     |
| `models/`        | ORM table definitions                                         | Logic beyond hybrid_property/computed      |
| `core/`          | App-wide config, db, logging, exceptions, security primitives | Domain logic                               |
| `dependencies/`  | `Depends()` providers (auth, db)                              | Business logic                             |
| `utils/`         | Pure functions (backoff math, signature HMAC)                 | I/O, DB, network                           |

A route handler should be ≤ 10 lines: parse → call service → return.
Services never `import httpx` directly — they call `ZohoClient`.

---

## 5. How we work — spec-driven + test-driven

Same loop as the Backend. Don't skip steps.

1. **Spec first.** Before code, write down (in chat or in the PR/commit):
   - The endpoint(s) — method, path, request schema, response schema, error
     cases.
   - The Zoho API(s) it talks to (URL, method, expected response shape).
   - Which tables it reads/writes.
   - The idempotency contract (what key, what TTL).
   If the spec is unclear, ask — don't guess.

2. **Tests first.** Failing tests in `tests/`:
   - Happy path (Backend → us → Zoho mocked → 2xx).
   - Validation errors from Backend payload.
   - Idempotent replay (same key returns the same result, no duplicate Zoho
     call).
   - Zoho 4xx (mapped to our error envelope).
   - Zoho 5xx / network failure (retry then `sync_logs.status = FAILED`).
   - Zoho rate-limit (429) (backoff path).
   - Token expiry (refresh triggered, original call retried once).

3. **Implement minimally.** Just enough to pass.

4. **Refactor under green.**

5. **Verify.** `uv run pytest`, `uv run ruff check`, `uv run mypy src`.

---

## 6. API design rules

- All endpoints under `/api/v1/...`. New breaking shapes go to `/api/v2/...`,
  never mutate v1.
- Internal sync (push) endpoints live under `/api/v1/sync/...`. Ingest (pull)
  under `/api/v1/ingest/...`. Webhooks under `/api/v1/webhooks/...`. Admin/ops
  under `/api/v1/admin/...`.
- Every endpoint declares `response_model=` and `tags=[...]` for OpenAPI.
- Every endpoint has a one-line docstring — it shows up in `/docs`.
- Status codes: `202 Accepted` for sync requests that we accept and queue/log
  but whose Zoho outcome is recorded asynchronously; `200` for sync requests
  we complete synchronously; `409` for idempotency conflict (same key, different
  payload); `404` for missing mapping; `422` for Pydantic validation; `502` for
  upstream Zoho failure surfaced to the caller; `503` if our Zoho client is
  in a circuit-broken state.
- Sync endpoints **must** accept `Idempotency-Key` header. Missing key → 400.
- Webhook endpoints **must** verify Zoho's signature before any work — fail
  closed (401) if it doesn't match. Read body raw before parsing.
- All sync + admin endpoints require the internal API key header. Webhook
  endpoints do not (they're authenticated by signature instead).

---

## 7. Exception handling

- Hierarchy in `core/exceptions.py`:
  ```
  AppError                       # base: status_code, code, message
   ├── NotFoundError                 # 404 — missing mapping, missing sync log
   ├── ConflictError                 # 409 — idempotency conflict
   ├── ValidationError               # 422 — business-rule, not Pydantic
   ├── AuthenticationError           # 401 — bad internal key, bad webhook sig
   ├── UpstreamError                 # 502 — Zoho returned a non-retryable error
   └── UpstreamUnavailableError      # 503 — Zoho unreachable / circuit open
  ```
- A separate, narrower hierarchy in `clients/zoho/errors.py` for Zoho-specific
  failures (`ZohoAuthError`, `ZohoRateLimitError`, `ZohoNotFoundError`,
  `ZohoServerError`). Services translate these into the `AppError`
  hierarchy. Routes never see Zoho-specific exceptions.
- One global handler in `main.py` returns:
  ```json
  {"error": {"code": "UPSTREAM_ERROR", "message": "...", "request_id": "..."}}
  ```
- Services raise; routes never `try/except HTTPException`.
- `assert` is for tests only.
- A failure that we've already logged to `sync_logs` is still re-raised so
  the caller (Backend) sees a non-2xx response if the sync failed synchronously.

---

## 8. Logging

Same rules as the Backend, with these additions specific to this service:

- Every sync attempt produces both a `sync_logs` row **and** a structured log
  line. The log line includes: `entity_type`, `local_id`, `zoho_id` (if
  resolved), `idempotency_key`, `attempt`, `outcome`, `latency_ms`,
  `zoho_status_code`, `request_id`.
- Token refresh events log at `INFO`: `event=zoho_token_refreshed`,
  `expires_in`. Never log the access token, refresh token, client secret, or
  webhook signing secret. Redact in a processor.
- Webhook receipt logs at `INFO` once per event id: `event=zoho_webhook_received`,
  `event_id`, `module`, `operation`.
- A retry log line at `WARNING` per failed attempt; a single `ERROR` line when
  retries are exhausted.
- `DEBUG` may include the outbound URL and request id, but **never** the body.

---

## 9. Configuration & secrets

All config goes through `core/config.py` (`pydantic_settings.BaseSettings`).
Required settings for this service:

```
APP_ENV                  # dev | staging | prod
LOG_LEVEL                # INFO by default

DATABASE_URL             # postgres async URL for integration_db

INTERNAL_API_KEY         # shared secret the Backend sends as a header

ZOHO_ACCOUNTS_URL        # e.g. https://accounts.zoho.in
ZOHO_API_BASE_URL        # e.g. https://www.zohoapis.in/crm/v8
ZOHO_CLIENT_ID
ZOHO_CLIENT_SECRET
ZOHO_REFRESH_TOKEN       # bootstrap refresh token (stored encrypted in DB after first use)
ZOHO_WEBHOOK_SECRET      # for HMAC verification of inbound webhooks

BACKEND_BASE_URL         # Backend base URL for ingest write-back (Track A; default http://localhost:8000)
ZOHO_INGEST_ENABLED      # gate the Zoho→app ingest run (Track A; default false)

HTTP_TIMEOUT_SECONDS     # default 10
HTTP_MAX_RETRIES         # default 3
HTTP_BACKOFF_BASE_MS     # default 200
```

- `.env.example` is the source of truth for which variables exist.
- Secrets are never logged, printed, or hardcoded.
- The refresh token, once persisted to `zoho_tokens`, should be considered the
  live value; the env var is bootstrap-only.

---

## 10. Database

- Async SQLAlchemy. One engine, one `async_sessionmaker`, exposed via
  `get_db` in `core/database.py`.
- Migrations are mandatory. Every schema change → an Alembic revision in the
  same commit. Never edit the DB out of band.
- Repositories own SQL. Services compose repositories.
- Use explicit transactions when a service touches more than one repo. For
  sync writes, the pattern is:
  1. Open transaction.
  2. Check idempotency key (return cached result if found).
  3. Resolve / create CRM mapping.
  4. Insert `sync_logs` row with `status = PENDING`.
  5. Commit transaction.
  6. Call Zoho (outside the transaction — never hold a DB transaction across
     a network call).
  7. Open second transaction, update `sync_logs` row with outcome + Zoho id,
     upsert mapping if new, commit.
- Indexes worth declaring up front:
  - `idempotency_keys (key)` unique.
  - `crm_mappings (entity_type, local_id)` unique.
  - `crm_mappings (entity_type, zoho_id)`.
  - `sync_logs (entity_type, local_id, created_at desc)`.
  - `webhook_events (event_id)` unique.

---

## 11. Zoho client rules (`clients/zoho/`)

The Zoho client is the only place in the codebase that does outbound HTTP.

- A single `ZohoClient` class wraps `httpx.AsyncClient`. It's a dependency
  (injected via `Depends`) so tests can override with `respx`.
- It owns: base URL, default timeout, default headers, retry loop, error
  translation, **and** transparent token refresh on `401` (refresh once,
  retry once — never loop).
- Retry policy: exponential backoff with jitter, up to `HTTP_MAX_RETRIES`,
  only on `5xx` and connection errors. **Never retry `4xx` (except 401 once
  after refresh, and 429 with respect for `Retry-After`).**
- Rate-limit handling: on `429`, honour `Retry-After` once; otherwise raise
  `ZohoRateLimitError` and let the caller decide (the sync service marks the
  sync_log `RATE_LIMITED` and surfaces 503 to the Backend).
- The client returns parsed dicts to services, never raw `httpx.Response`
  objects. Services don't deal with HTTP transport details.
- Endpoint URLs live in `clients/zoho/endpoints.py` as named constants /
  builder functions — no f-strings scattered across services.

---

## 12. Idempotency contract

Every sync endpoint accepts an `Idempotency-Key` header (UUID v4 from the
Backend).

- **Same key + same payload** within TTL → return the cached prior response,
  do **not** call Zoho again.
- **Same key + different payload** → `409 ConflictError("IDEMPOTENCY_CONFLICT")`.
- **No key** → `400`.
- Default TTL: 24 hours (revisit if traffic patterns require longer).
- Storage: `idempotency_keys (key, request_hash, response_body, status_code,
  created_at)`. Hash the canonicalized request body.

---

## 13. Webhook handling

- `POST /api/v1/webhooks/zoho` is **public** but only authenticated by
  signature.
- Read the raw body **before** Pydantic parses it (signature is over raw bytes).
- Verify HMAC; mismatch → `401`, log at `WARNING`, do nothing else.
- Persist the event in `webhook_events` immediately. Use Zoho's event id as
  the natural dedupe key (unique index). Duplicate delivery → `200 OK` no-op.
- Acknowledge to Zoho fast (200) once persisted. Processing happens in the
  same request **only if** it's cheap and idempotent; otherwise mark the
  event `PENDING` and let an admin/processor endpoint drive it (Phase 1: keep
  it synchronous unless a real reason emerges).

---

## 14. Testing

- Tests live in `tests/`, mirror `src/app/` where useful.
- `pytest` + `pytest-asyncio` + `httpx.AsyncClient` against the app.
- `respx` to mock outbound Zoho HTTP. **Never** hit real Zoho from tests.
- Fixtures in `conftest.py`:
  - `db_session` — transactional, rolled back per test.
  - `client` — `AsyncClient` bound to the app with the internal API key header
    pre-set.
  - `zoho_mock` — `respx` router configured with a sane default Zoho response.
  - `webhook_signer` — helper to compute a valid signature for test payloads.
- Test naming: `test_<unit>_<scenario>_<expected>`, e.g.
  `test_sync_customer_replays_idempotent_request_without_calling_zoho`.
- Mandatory coverage per sync endpoint:
  - Happy path.
  - Idempotent replay (no Zoho call on second hit).
  - Idempotency conflict (same key, different body → 409).
  - Zoho 4xx → mapped to `UpstreamError`.
  - Zoho 5xx exhausted → `sync_logs.status = FAILED`, 502 to caller.
  - Zoho 401 → token refresh, retry once, success.
  - Zoho 429 → respects `Retry-After` once, then `RATE_LIMITED`.
- Mandatory coverage per webhook endpoint:
  - Valid signature, new event → 200, row persisted.
  - Valid signature, duplicate event id → 200, no duplicate row.
  - Invalid signature → 401, no row persisted.

---

## 15. Code quality bar

Identical to the Backend:

- **Write only what's needed.** No speculative abstractions, no helpers with
  one caller, no "future-proof" config knobs.
- **DRY without being premature.** Three similar lines is fine; three similar
  *functions* is a smell.
- **Readable over clever.** Multi-line over dense one-liners. Self-explanatory
  names over comments.
- **Comments:** only when *why* is non-obvious. No banners, no decorative
  separators.
- **Types everywhere.** Public functions, service methods, repository
  methods, route handlers — fully annotated. `mypy` is strict.
- **Imports:** absolute (`from app.services.sync_service import ...`), grouped
  stdlib / third-party / first-party, sorted by ruff/isort.
- **No dead code.** Delete unused imports, unused params, unused branches.

---

## 16. Definition of Done (per change)

- [ ] Spec captured (chat/PR description), including the Zoho endpoint(s)
      involved.
- [ ] Tests added/updated, all green: `uv run pytest`.
- [ ] `uv run ruff check` clean.
- [ ] `uv run mypy src` clean.
- [ ] Idempotency behaviour tested where applicable.
- [ ] No new `WARNING`+ logs on a normal request path.
- [ ] `.env.example` updated if config changed.
- [ ] Alembic migration committed if schema changed.
- [ ] `/docs` (OpenAPI) renders the new endpoint with correct schemas.
- [ ] No real Zoho calls in tests (verify `respx` was used).
- [ ] No unrelated changes mixed in.

---

## 17. Commands cheat-sheet

```powershell
# install / sync deps
uv sync

# add a runtime dep
uv add fastapi httpx

# add a dev dep
uv add --dev pytest pytest-asyncio httpx respx ruff mypy

# run the app (dev)
uv run uvicorn app.main:app --reload --app-dir src --port 8001

# tests
uv run pytest -q
uv run pytest -q tests/test_sync.py::test_sync_customer_happy_path

# lint + types
uv run ruff check
uv run ruff format
uv run mypy src

# alembic
uv run alembic revision --autogenerate -m "add zoho_tokens table"
uv run alembic upgrade head
```

---

## 18. Working agreement for Claude

When asked to add or change something in `Integration Layer/`:

1. Re-read this file if it's been a while.
2. State the spec back in one short paragraph before coding — include the
   Zoho endpoints touched and the idempotency contract.
3. Show the test plan, write tests first (with `respx` for Zoho).
4. Implement the minimum. No bonus features.
5. Run pytest + ruff + mypy. Report the results honestly.
6. Never hit real Zoho from tests or from local dev unless the user explicitly
   asks for a live integration check.
7. If a rule here is getting in the way, say so — don't quietly bend it.

Anything outside `Integration Layer/` is off-limits unless the user explicitly
opens that scope.

---

## 19. Ingest (Track A — Zoho → app)

The current engagement builds **ingest before push** (see the scope note at the
top). Ingest pulls Zoho **Leads, Activities (Calls/Meetings/Tasks), Users, and
won Deals** and lands them in the Backend so the Intelligence effort/efficiency
engine can score rep productivity. It reuses the same machinery as the push —
this section only states what differs.

- **Direction & ownership.** One-way Zoho → app. The IL **never writes
  `inventory_db` directly** — it calls the Backend's internal ingest endpoints
  (internal API key). The Backend stays the only writer of its own tables.
- **Endpoints.** `api/v1/ingest.py` exposes the pull trigger(s)
  (`POST /ingest/run`, or per-entity) and a status read; orchestration lives in
  `services/ingest_service.py`. A scheduled trigger or an internal call drives
  it — never the frontend.
- **Mapping & dedupe.** Each ingested record gets a `crm_mappings` row keyed on
  its Zoho id (`entity_type ∈ {lead, activity, deal, user}`). Re-pull is
  idempotent: an existing mapping → update, not insert. Pull deltas via a
  per-entity **watermark** (last-modified cursor). Note: ingest dedupes on the
  Zoho record id, **not** the `Idempotency-Key` header (§12 is for inbound push).
- **Rep attribution.** Resolve the Zoho record's **owner email → app
  `users.email`** and store the mapping (`entity_type='user'`). Apply it to
  `created_by_user_id` (activities) / `assigned_to_user_id` (leads). An
  unmatched owner → **park** the record (log to `sync_logs`, status `PARKED`),
  never guess, never hard-fail.
- **Field mapping.** Zoho Call→`CALL`, Task→`FOLLOW_UP`, Meeting/Event→`MEETING`
  (+ duration → time spent); Zoho Lead Status→app lead stage, owner→assignee;
  Closed-Won Deal Amount/date → the lead's `won_value`/`won_at`. ("Visit" has no
  native Zoho type — see the master plan §9 for the agreed convention.)
- **Determinism.** Ingest is additive and flag-gated (`ZOHO_INGEST_ENABLED`).
  The AI engines must produce identical output with ingest off; an ingest
  failure must never corrupt app data. Scores are **never** pushed back to Zoho.
- **Tests.** `respx`-mocked Zoho, never real. Cover: mapped record → one app
  row; re-pull → no duplicate; unmatched owner → parked; flag off → no-op.
- Full phasing + the AI-feed parameter mapping:
  `../ZOHO_INTEGRATION_EXECUTION_PLAN.md` §4 and §7 (Track A).
