# execution.md — Integration Layer

Living phase log for the Integration Layer. The architecture contract is
`CLAUDE.md`; the cross-service master plan (and the reconciliation of the Zoho
PDF vs. the repo spec) is `../ZOHO_INTEGRATION_EXECUTION_PLAN.md`. Read both
before starting a phase.

**Service:** FastAPI on **:8001**, owns `integration_db`, the only service that
talks to Zoho. Backend → IL over an internal API key; IL → Zoho over OAuth.

---

## Decisions in force (from the master plan)

- **D-1 — mappings only.** Local↔Zoho link lives in `crm_mappings`
  `(entity_type, local_id) → zoho_id`; our UUID is written into Zoho's
  `Inventory ID` custom field. **No `zoho_crm_id` columns on Backend tables.**
- **D-2 — spec-core first.** One-way push (Customers/Vendors/Items/SO/PO) ships
  before any collaboration features. Leads stay app-canonical; Zoho gets
  one-way ingest (activities) and one-way export (assignment/tasks) only.
- **Guardrails:** inventory never blocks on Zoho; AI engines run with no Zoho;
  idempotency on every sync; bounded inline retries, no queue infra.

---

## Phase log

### Phase 0 — Scaffold + Zoho prerequisites — ⏳ NOT STARTED
- `src/app/` skeleton per `CLAUDE.md` §3 (core/config, database, logging,
  exceptions, security).
- First Alembic migration: `zoho_tokens`, `crm_mappings`, `sync_logs`,
  `idempotency_keys`, `webhook_events` (+ indexes from `CLAUDE.md` §10).
- `token_service` (get-or-refresh) + `/health`, `/health/zoho`.
- Zoho-side (manual, no code): OAuth self-client + scopes, `integration-bot`
  user, custom fields (see master plan §5), data-centre URLs in `.env`.
- **Done when:** IL boots, `/health` green, token refresh works against a
  `respx` mock, migrations apply on `integration_db`.

### Phase 1 — One-way push core — ⏳ NOT STARTED
- `clients/zoho/` (`ZohoClient`, `endpoints`, `errors`): auth header, timeout,
  retry on 5xx/conn, 401→refresh-once-retry-once, 429→Retry-After.
- `services/`: `mapping_service`, `sync_service` (idempotency → resolve mapping
  → Zoho upsert → log), `webhook_service` (stub dispatch).
- `api/v1/`: `sync.py` (customers/vendors/items/sales-orders/purchase-orders —
  `Idempotency-Key` + internal key required), `admin.py`
  (`GET /sync-logs`, `POST /sync-logs/{id}/retry`), `mappings.py`
  (`GET /mappings?entity_type=&local_id=` for the FE badge), `webhooks.py`
  (`POST /webhooks/zoho` — verify + persist + 200, no dispatch).
- Field mapping per `../ZOHO_CRM_SPECIFICATION.md` §3 and PDF §2.
- **Tests (CLAUDE.md §14):** happy path · idempotent replay (no 2nd Zoho call) ·
  conflict 409 · Zoho 4xx→UpstreamError · 5xx exhausted→`FAILED`+502 ·
  401→refresh+retry · 429→Retry-After · webhook valid/dup/invalid-sig.
- **Done when:** create/update customer round-trips to Zoho; SO links to Account
  + Product_Details; no duplicate on replay; the verification checklist
  (master plan §6, Phase 1) passes.

### Phase 3 — Zoho Activities → AI ingest — ⏳ NOT STARTED (after Phase 1)
- One-way pull of Zoho Activities → map via `crm_mappings` → write to the
  Backend's activities API (never a cross-DB write). Idempotent, watermarked,
  flag `ZOHO_ACTIVITY_INGEST_ENABLED`.
- **Done when:** a mapped Zoho meeting appears in the app timeline; re-pull
  creates no duplicate; engines unaffected when the flag is off.

### Phase 4 — Lead allotment & tasks (export) — ⏳ NOT STARTED (last)
- On in-app lead assignment: PATCH Zoho Lead owner + create Zoho Task
  (one-way export). `POST /crm/users/sync` to resolve `email → zoho_user_id`
  (stored in `integration_db`, not on Backend `users`).
- Amends `../ZOHO_CRM_SPECIFICATION.md` (leads/tasks/user-sync were out of
  scope) — update that doc in the same change.
- **Done when:** assigning a lead in-app produces a Zoho task for the rep,
  idempotently; AI lead scores unaffected.

> Phase 2 (role enum + sales-productivity) is **Backend/Intelligence/Frontend
> only — no IL work**; tracked in those services' `execution.md`.

---

## How to test (you) — once Phase 0/1 land

```powershell
cd "Integration Layer"
uv sync
uv run alembic upgrade head          # creates integration_db tables
uv run pytest -q                     # respx-mocked Zoho — never hits real Zoho
uv run ruff check ; uv run mypy src
uv run uvicorn app.main:app --reload --app-dir src --port 8001
# then: open http://localhost:8001/docs ; GET /health and /health/zoho
```

> Live Zoho is only exercised in a manual smoke test with real `.env` creds —
> never from pytest/CI (CLAUDE.md §14).
