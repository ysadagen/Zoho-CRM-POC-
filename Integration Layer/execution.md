# execution.md — Integration Layer

Living phase log for the Integration Layer. Architecture contract: `CLAUDE.md`.
Cross-service master plan (decisions, AI integration, sequencing):
`../ZOHO_INTEGRATION_EXECUTION_PLAN.md` — **read its §0 (scenario) and §4 (AI
integration) before starting.**

**Service:** FastAPI on **:8001**, owns `integration_db`, the only service that
talks to Zoho. Backend ↔ IL over an internal API key; IL → Zoho over OAuth.

---

## The engagement in one line

**Zoho Free, 3 users (1 admin + 2 sales reps).** The reps work Leads + log
Calls/Meetings/Tasks in Zoho; the IL **ingests** that into the Backend so the
Intelligence **effort & efficiency** engine can compute each rep's productivity.
**Ingest-led (Track A) is the priority;** the order/master **push (Track B)** is
deferred and needs a paid Zoho edition.

## Decisions in force (from the master plan)
- **D-1 mappings-only:** Zoho↔local links live in `crm_mappings`
  `(entity_type, local_id)→zoho_id`. No `zoho_*` columns on Backend tables.
- **D-2 app-canonical:** leads live in the app (the AI scores them); we ingest
  Zoho→app; scores are never pushed to Zoho.
- **D-3 productivity-first:** ingest (Leads + Activities + won Deals) is the
  near-term build; push is parked.
- **Guardrails:** app data never corrupted by Zoho; AI engines run with no Zoho
  (ingest is additive); idempotent ingest; bounded inline retries, no queue.

---

## Phase log

### TRACK A — Productivity from Zoho (priority)

#### Phase A0 — Scaffold + OAuth + Zoho read access — ✅ DONE (code) · ⏳ awaiting manual live smoke
- ✅ `src/app/` skeleton per `CLAUDE.md` §3 (core: config, database, logging
  with secret-redaction processor, exceptions, security; middleware:
  request-id + access-log; one error envelope `{error:{code,message,request_id}}`).
- ✅ First Alembic migration `86e5805cbb3d_initial_integration_schema`:
  `zoho_tokens`, `crm_mappings`, `sync_logs`, `idempotency_keys`,
  `webhook_events` (+ §10 indexes). Applies and round-trips (downgrade→upgrade)
  on `integration_db`; the shared `mapping_entity_type` ENUM is created once
  explicitly (autogenerate would have emitted `CREATE TYPE` twice and failed).
- ✅ `token_service` (OAuth refresh-token flow, get-or-refresh with expiry
  skew, persisted to `zoho_tokens`) + `ZohoOAuthClient` + `ZohoClient` **read**
  path (`get_users`) with retry/backoff, refresh-once-retry-once on 401,
  `Retry-After` on 429, error mapping → `AppError`; `/health` + `/health/zoho`.
- ✅ Tests (**14 passing**, `respx`-mocked, no real Zoho): app boots;
  `/health/zoho` green (fresh token → no call; missing/expired → refresh) and
  503 on bad creds; `GET users` parses; 401→refresh→retry; 404/429/5xx mapping;
  migrations applied (5 tables asserted). `ruff` + `mypy --strict` clean.
- ⏳ **Manual (you):** Zoho self-client + scopes (`ZohoCRM.modules.ALL`,
  `ZohoCRM.users.READ`), generate refresh token into `.env`, invite the **2
  reps + admin** with **emails matching the app `users`**, then one live
  token-refresh smoke (`GET /health/zoho` against real creds). Steps + commands
  are in the A0 handoff (chat).

> **A0 decisions flagged for you:**
> 1. `/health/zoho` proves Zoho auth by acquiring a token (refresh only when
>    missing/near-expiry) — it does **not** make a CRM read, to protect Zoho
>    Free's daily API credits (probes can fire every few seconds).
> 2. Tokens are stored **plaintext** in `zoho_tokens` (columns are `Text`, so
>    field-level encryption is a non-breaking add later). At-rest encryption
>    needs a dedicated key setting that isn't specced yet — flag if you want it.
> 3. `crm_mappings` is unique on **both** `(entity_type, local_id)` and
>    `(entity_type, zoho_id)` — the latter is the ingest dedupe key (§19),
>    strengthening §10's plain zoho index. Both id columns are nullable so a
>    parked ingest / in-flight push never collides.

#### Phase A1 — Ingest Leads + Activities (+ won Deals) → Backend — ✅ DONE (code) · ⏳ awaiting live ingest smoke
> Feeds the AI engine (master plan §4). Built across **IL + Backend** (full scope
> confirmed by the user). **No new migrations** — reuses A0's `crm_mappings`/
> `sync_logs` and the Backend's existing `leads`/`sales_activities` (D-1 intact).

**Backend (receiver) — green: 354 tests, ruff + mypy clean.**
- `require_internal_api_key` (constant-time, header `X-Internal-API-Key` vs
  `INTEGRATION_LAYER_API_KEY`) + `require_ingest_enabled` (503 unless
  `ZOHO_INGEST_ENABLED`) — both as router-level deps on `api/v1/ingest.py`.
- Endpoints: `GET /ingest/users`, `POST /ingest/leads`, `PATCH /ingest/leads/{id}`,
  `POST /ingest/activities`. `services/ingest_service.py` mirrors Zoho:
  stage set directly + history row (Zoho-authoritative; bypasses the interactive
  transition-legality check but honours every DB CHECK), `created_at` ← Zoho
  creation time, won Deal → `stage=WON`+`won_value`+`won_at` together. Audit
  actor = the resolved rep/owner (no human actor in ingest).
- Attribution lands on the columns the engine aggregates: `assigned_to_user_id`
  (leads) and `rep_user_id` (activities) — verified against the Intelligence
  `rep_metrics_repo`.

**IL (puller) — green: 28 tests, ruff + mypy clean.**
- `clients/backend/` (2nd outbound integration), Zoho read methods
  (Leads/Calls/Events/Tasks/Deals, paginated), `crm_mapping_repo` +
  `sync_log_repo`, `mapping_service`, `services/ingest_service.py`,
  `POST /ingest/run` + `GET /ingest/status`. Config: `BACKEND_BASE_URL`,
  `ZOHO_INGEST_ENABLED`.
- Mapping: Call→CALL, Task→FOLLOW_UP, Meeting **with Location**→VISIT else
  MEETING; Lead_Status→stage (in-funnel only); owner email→app user (unmatched
  → **PARK** to `sync_logs`, never guessed); won Deal→lead via Zoho's
  converted-deal reference, parked if unresolved.
- Idempotent on the Zoho id via `crm_mappings`: re-pull updates leads / skips
  append-only activities, never duplicates. Per-record commit so progress
  survives a later failure.
- Tests (respx, never real Zoho/Backend): full run (lead+VISIT+won Deal, owner
  resolved, payloads asserted), re-pull no-dup, unmatched owner parked, disabled
  → no-op + zero upstream calls, Backend-client error mapping, Zoho pagination.

- ⏳ **Manual (you), to close A1:** set `ZOHO_INGEST_ENABLED=true` on **both**
  services + `INTERNAL_API_KEY`==Backend `INTEGRATION_LAYER_API_KEY`; run the
  Backend (:8000) + IL (:8001); `POST :8001/api/v1/ingest/run`; confirm on the
  **Team Performance** page that the 2 reps' effort/efficiency reflects Zoho
  data after `POST /api/v1/intelligence/recompute`. The §4.4 determinism check
  (engines byte-identical with the flag off) holds by construction (ingest is
  additive + flag-gated).

> **A1 decisions flagged for you:**
> 1. **Watermarking deferred** — A1 does a full idempotent re-pull each run
>    (`crm_mappings` guarantees no dupes). A per-entity last-modified cursor is a
>    pure efficiency add for later; not needed for correctness at 3 users.
> 2. **Deal→Lead link** uses Zoho's native converted-lead→deal reference
>    (`Converted_Deal` captured during lead ingest → `crm_mappings(DEAL)`); a
>    Closed-Won Deal with no such link is **parked**, never guessed. **Confirm
>    the exact converted-deal field + the activity `Who_Id`/`What_Id`/
>    `$se_module` shapes during the live smoke** — they're centralised in
>    `ingest_service.py`'s pure adapters, so a correction is one edit.
> 3. **LOST mapping deferred** — a lost-in-Zoho lead keeps its last in-funnel
>    stage rather than fabricating a `lost_at`/`lost_reason`. WON comes solely
>    from Closed-Won Deals. Revisit if lost-rate reporting is needed.
> 4. **Activity subject = Lead only** in A1 — account/contact-only activities
>    (no resolvable lead) are parked. Customer-subject ingest needs a customer
>    mapping (Track B territory).

#### Phase A2 — (no IL work) — role enum + productivity surfacing
Backend + Intelligence + Frontend only (role enum, admin-gated Team Performance).
Tracked in those services' `execution.md`.

### TRACK B — Order & master visibility (DEFERRED — needs paid Zoho)
> Free edition lacks Sales Orders / Purchase Orders / Products. Not needed for
> productivity. Build only when a paid edition + an order-visibility goal exist.
- **B1 — one-way push:** `clients/zoho` write path, `sync_service`,
  `api/v1/sync.py` (Idempotency-Key + internal key; masters→transactions;
  missing parent → 404), `admin.py` retry, `mappings.py` for the FE badge,
  webhook stub. Field mapping: `../ZOHO_CRM_SPECIFICATION.md` §3. Tests:
  `CLAUDE.md` §14.
- **B2 — lead allotment + task export:** in-app assignment → PATCH Zoho Lead
  owner + create Zoho Task (one-way); reuses the A1 email→user map; amends the
  spec doc.

---

## How to test (you) — once A0/A1 land

```powershell
cd "Integration Layer"
uv sync
uv run alembic upgrade head          # creates integration_db tables
uv run pytest -q                     # respx-mocked Zoho — never hits real Zoho
uv run ruff check ; uv run mypy src
uv run uvicorn app.main:app --reload --app-dir src --port 8001
# then: http://localhost:8001/docs ; GET /health and /health/zoho
```
> Live Zoho is only exercised in a manual smoke test with real `.env` creds —
> never from pytest/CI (`CLAUDE.md` §14).
