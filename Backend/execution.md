# execution.md — Inventory Backend build log

Phase-by-phase log + contracts for the **pharmaceutical-inventory upgrade**.
Companion to:

- `proposal.md` — the design + decisions (raw/finished segregation + batches).
- `docs/Backend_Reference.md` — the *current* schema & API (source of truth).
- `CLAUDE.md` — the engineering contract (spec-driven + test-driven, §5).

Work is spec-driven and test-driven. **Each phase is its own slice: spec →
red → green → verify → stop for review.** No bonus features; nothing built
until the phase's open decisions (`[DECIDE]`) are resolved.

---

## Roadmap (do these IN ORDER — later slices depend on earlier ones)

| Phase | Slice | Status | Depends on |
|---|---|---|---|
| 0 | Additive structure (tables, enums, detail-row wiring) | ✅ **SHIPPED** | — |
| 1A | Pharma attributes on items (detail read/write) | ✅ **SHIPPED** | 0 |
| 1B | Batch CRUD + expiry | ✅ **SHIPPED** | 0 |
| 1C | PO receive → batch | ✅ **SHIPPED** | 1B |
| 1D | SO ship → FEFO | ✅ **SHIPPED** | 1B (1C helpful) |
| 1E | Multi-lot PO receive (#10) | ✅ **SHIPPED** | 1C |
| 1F | SO batch selection (#9, + #6) | ✅ **SHIPPED** | 1B, 1D |
| 1G | Item soft-delete via DELETE (#1) | ✅ **SHIPPED** | — |
| 1H | QC status transitions + ship gating (#7) | ✅ **SHIPPED** | 1B, 1D |
| 1I | Adjustment targeting a lot (#8) | ✅ **SHIPPED** | 1B |
| 2 | Flip stock source-of-truth to batches · further QC policy | 🔭 Later | 1A–1I |

**Non-negotiable across all phases:** the stock keystone
(`StockMovementService.record_movement`) stays the *only* writer of
`items.stock_quantity`. New flows extend it (set `batch_id`); they never
bypass it. Existing endpoints keep working unchanged unless a slice's spec
explicitly says otherwise.

---

## Phase 0 — additive structure ✅ SHIPPED (2026-06-12)

**Goal:** put the pharma schema in place with zero behaviour change.

**Shipped:**
- Migration `e7b2a9c4d1f8_add_pharma_batch_and_item_detail_tables` (chains off
  head `4be90595bc88`): 6 enums; `items.storage_condition` /
  `items.shelf_life_days`; `raw_item_details`, `finished_item_details`,
  `batches`; nullable `stock_movements.batch_id`; backfill of one detail row
  per existing item (with a guard that raises if any item is unclassified).
- ORM: `RawItemDetail`, `FinishedItemDetail`, `Batch` (+ enums); `Item` &
  `StockMovement` extended; all registered in `models/__init__.py`.
- Schemas: `ItemCreate`/`ItemUpdate`/`ItemRead` expose `storage_condition` +
  `shelf_life_days`.
- Service: `ItemService.create` also creates the matching 1:1 detail row in the
  same transaction (invariant: every item owns exactly one detail row).
- Test infra: `conftest.py` bootstraps Alembic via `sys.executable -m alembic`
  (not `uv run`, which local Application Control blocks).

**Verification:** `ruff check` + `ruff format --check` clean; `mypy src` clean;
**`pytest` 222 passed** (206 existing + 16 new); migration down→up round-trip
verified; applied to the dev DB.

**Files:** `models/{item,stock_movement,raw_item_detail,finished_item_detail,batch,__init__}.py`,
`schemas/item.py`, `services/item_service.py`, `migrations/versions/e7b2a9c4d1f8_*.py`,
`tests/{test_item_details,test_batches}.py`, `tests/conftest.py`.

**How to test (you):**
```powershell
docker compose up -d            # from Code/
python -m alembic current       # from Code/Backend — expect e7b2a9c4d1f8
python -m pytest -q             # 222 passed
```

---

## Phase 1A — Pharma attributes on items ✅ SHIPPED (2026-06-12)

**Decision A1 resolved:** nested detail blocks (`raw_detail` / `finished_detail`).

**Shipped:**
- Schemas `RawItemDetailIn`/`RawItemDetailRead` (`schemas/raw_item_detail.py`) and
  `FinishedItemDetailIn`/`FinishedItemDetailRead` (`schemas/finished_item_detail.py`).
  `ItemCreate`/`ItemUpdate` accept an optional, type-matched detail block;
  `ItemRead` returns the matching one (`In` doubles for create + partial patch
  via `exclude_unset`).
- `Item` gained `raw_detail` / `finished_detail` relationships
  (`uselist=False, lazy="selectin", cascade="all, delete-orphan"`) — reads
  eager-load, no N+1, no `MissingGreenlet`.
- `ItemService`: `create` attaches the matching detail via the relationship and
  applies client-sent fields; `update` partial-patches the matching detail and
  re-fetches via `get` (fresh `updated_at` + loaded detail); a mismatched block
  raises `ValidationError("ITEM_DETAIL_TYPE_MISMATCH")` → **422** (one rule,
  used by both create and update).
- No migration — the columns/tables shipped in Phase 0.

**Verification:** `ruff` + `ruff format` clean; `mypy src` clean (66 files);
**`pytest` 231 passed** (222 prior + 9 new 1A tests). No new endpoints, so no
new routes — the existing item routes carry the richer schema.

**Files:** `schemas/{raw_item_detail,finished_item_detail,item}.py`,
`models/item.py`, `services/item_service.py`, `tests/test_item_details.py`.

**How to test (you):**
```powershell
python -m pytest -q tests/test_item_details.py   # detail create/read/patch/422
```

### Original spec (for reference)

**Goal:** let the API read & write the subtype detail fields (raw vs finished)
so a pharma item can actually record its attributes. Completes the raw/finished
*segregation*. No stock logic — lowest risk.

**Endpoints:** no new routes. Extend the existing item surface:
- `POST /items` — accept an optional, type-matched detail block.
- `PATCH /items/{id}` — patch the detail block.
- `GET /items/{id}` and `GET /items` — return the matching detail block.

**Schemas (planned):**
- `RawItemDetailIn` — `material_classification?`, `pharmacopoeia?`,
  `is_hazardous?` (default false).
- `FinishedItemDetailIn` — `generic_name?`, `brand_name?`, `strength?`,
  `dosage_form?`, `pack_size?`, `ingredients?`, `container_specification?`,
  `selling_price?` (≥0), `license_number?`, `registration_code?`, `mrp?` (≥0),
  `drug_schedule?`, `is_prescription_required?` (default false).
- `ItemCreate += raw_detail: RawItemDetailIn | None`,
  `finished_detail: FinishedItemDetailIn | None`. **Validator:** only the block
  matching `type` may be present (RAW ⇒ no `finished_detail`, and vice-versa) →
  else `422`.
- `ItemRead += raw_detail: RawItemDetailOut | None`,
  `finished_detail: FinishedItemDetailOut | None` — only the matching one is
  populated.
- `ItemUpdate += raw_detail / finished_detail` (partial patch of the matching
  type only).

**Model change:** add `Item.raw_detail` / `Item.finished_detail` relationships
(`uselist=False`, `lazy="selectin"`) so reads eager-load the detail and avoid
N+1 / `MissingGreenlet`. (Schema/columns already exist — no migration.)

**Service:** `create` fills the detail row from the payload (today it creates an
empty one); `update` patches it; `get`/`list_` eager-load it.

**Business rule:** an item's detail row always matches its `type`; `type` stays
immutable (already enforced — not patchable), so the detail kind never has to
switch.

**Errors:** `422` for a wrong-type detail block or an invalid enum value.

**Tables touched:** none (structure shipped in Phase 0).

**`[DECIDE]` A1:** nested detail blocks (recommended, explicit, typed) vs
flattening the fields onto the item. Recommendation: **nested**.

**Test plan:** create RAW with `raw_detail` → persists & GET returns it; create
FINISHED with `finished_detail`; `finished_detail` on a RAW item → 422; invalid
enum → 422; PATCH updates detail fields; `GET /items` list includes detail (no
N+1); item created without a detail block still gets its (empty) row.

---

## Phase 1B — Batch CRUD + expiry ✅ SHIPPED (2026-06-12)

**Decisions resolved:** **B1** = opening-balance association (recording a lot
associates *existing* stock, no net change; new stock arrives via PO receive in
1C). **B2** = no movement for the association (pure metadata — it changes no
totals). **B3** = no status-transition workflow; `batch_status` is settable on
create (default `QUARANTINE`), the QC workflow stays deferred to Phase 2.

**Shipped:**
- Endpoints (`api/v1/batches.py`, mounted in `main.py`):
  `POST /batches`, `GET /batches` (filters `item_id` / `status` / `expiring_before`,
  paginated, soonest-expiry-first), `GET /batches/{id}`.
- `schemas/batch.py` — `BatchCreate` (validates expiry ≥ manufacture, qty > 0),
  `BatchRead` (+ computed `is_expired`), `BatchList`.
- `repositories/batch_repo.py` — `add`, `get_by_id`, `get_by_item_and_number`,
  `sum_quantity_for_item`, `list_`.
- `services/batch_service.py` — `create` locks the item row (`FOR UPDATE`),
  rejects unknown item (`404 ITEM_NOT_FOUND`), duplicate
  (`409 DUPLICATE_BATCH`), and over-batching
  (`409 BATCH_EXCEEDS_UNBATCHED_STOCK` when `Σ lot qty + new > item stock`);
  sets `initial_quantity = quantity`; writes **no** ledger movement.
- No migration — the `batches` table shipped in Phase 0.

**Verification:** `ruff` + `ruff format` clean; `mypy src` clean (70 files);
**`pytest` 246 passed** (231 prior + 15 new 1B tests, incl. the no-stock-change /
no-movement invariant, the cumulative reconciliation rule, and the filters).

**Files:** `schemas/batch.py`, `repositories/batch_repo.py`,
`services/batch_service.py`, `api/v1/batches.py`, `main.py`,
`tests/test_batch_api.py`.

**How to test (you):**
```powershell
python -m pytest -q tests/test_batch_api.py
```

### Original spec (for reference)

**Goal:** create/list/inspect lots per item and report on expiry. Introduces how
batch quantity relates to item stock.

**Endpoints (planned):**
- `POST /items/{item_id}/batches` — create a lot (`batch_number`, `expiry_date`
  [required], `manufacturing_date?`, `quantity`, `unit_cost?`, `vendor_id?`,
  `storage_location?`).
- `GET /items/{item_id}/batches` — list lots; filters: `status`,
  `expiring_before`, `include_expired`.
- `GET /batches/{id}` — one lot.
- `GET /batches?expiring_before=YYYY-MM-DD` (or `/reports/expiring?within_days=N`)
  — expiry report across items.

**THE key decision — `[DECIDE]` B1: how does a batch's quantity relate to
`items.stock_quantity`?** Phase 0 kept `items.stock_quantity` authoritative.
Options:
1. **Opening-balance association (recommended for B).** A batch created here
   *associates existing* stock with a lot and causes **no net stock change**.
   Guard: `Σ(batch.quantity for item) ≤ items.stock_quantity` (you can only
   batch stock you already have). Transitional invariant during rollout:
   `Σ batches.quantity ≤ items.stock_quantity`, trending to `==` as legacy
   stock is fully batched. *New* stock then enters via PO receive (1C), which
   creates a lot **and** an IN movement together.
2. **Batch-creates-stock.** A batch with `quantity` records an IN movement
   (adds to item stock). Simpler, but can't represent "assign existing legacy
   stock to a lot" without double-counting.

Recommendation: **Option 1** for 1B + new stock via 1C. Decide before building.

**`[DECIDE]` B2:** do we need a `MovementReason.OPENING` value (additive
`ALTER TYPE` migration), or does opening-balance association record **no**
movement (pure metadata) since it changes no totals? Leaning: no movement for
pure association; revisit if an audit trail for the association is wanted.

**QC release:** `batch_status` exists but the transition workflow
(QUARANTINE→RELEASED, etc.) stays deferred (proposal decision #4). A minimal
`PATCH /batches/{id}` for status could be a 1B micro-add or wait for Phase 2 —
`[DECIDE]` B3.

**Errors:** `404 ITEM_NOT_FOUND`; `409 DUPLICATE_BATCH` (unique
`(item_id, batch_number)`); `422` (expiry before manufacture, negatives);
`409` if Option 1 and `quantity` exceeds unbatched remainder.

**Test plan:** create lot → appears in list; duplicate batch number → 409;
expiry < manufacture → 422; expiry report returns lots within window, excludes
expired unless asked; reconciliation rule from B1 enforced.

---

## Phase 1C — PO receive → batch ✅ SHIPPED (2026-06-12)

**Decision C1 resolved:** operator-supplied batch numbers.

**Shipped:**
- `POST /purchase-orders/{id}/receive` now **requires a body** —
  `{ lines: [{ item_id, batch_number, expiry_date, manufacturing_date?, storage_location? }] }`,
  one entry per PO line, matched by `item_id`. (Contract change from the
  no-body Phase-7 receive; existing receive tests updated.)
- `PurchaseOrderReceive` / `PurchaseOrderReceiveLine` schemas (expiry ≥
  manufacture validated).
- `record_movement` gained an optional `batch_id` passthrough (additive —
  existing callers unaffected); `StockMovementRead` now exposes `batch_id`.
- `receive_po` (one transaction): validate entries cover exactly the PO's lines
  (`422 RECEIVE_LINES_MISMATCH`) → pre-check each lot number is free
  (`409 DUPLICATE_BATCH`) → per line (item-sorted): create a `batches` row
  (qty = line qty, `unit_cost` = line price, `vendor_id` = PO vendor,
  `received_via_po_id` = PO, `batch_received_date` = today, status QUARANTINE)
  then `record_movement(IN, PURCHASE, batch_id=<lot>)` → flip RECEIVED →
  commit. Any failure rolls back the whole receive (no partial lots/stock).
- No migration — uses Phase-0 columns.

**Verification:** `ruff` + `ruff format` clean; `mypy src` clean (70 files);
**`pytest` 250 passed** (246 prior + 4 new 1C tests; existing receive tests
updated to the new contract). The 401 auth-wall test still holds (security
dependency resolves before body validation).

**Files:** `schemas/purchase_order.py`, `schemas/stock_movement.py`,
`services/purchase_order_service.py`, `services/stock_movement_service.py`,
`api/v1/purchase_orders.py`, `tests/test_purchase_orders.py`.

**How to test (you):**
```powershell
python -m pytest -q tests/test_purchase_orders.py
```

### Original spec (for reference)

**Goal:** receiving a purchase order creates a lot per line and records the IN
movement against that lot.

**Endpoint change:** `POST /purchase-orders/{id}/receive` — today takes no body.
It will require per-line batch info: `batch_number`, `expiry_date`,
`manufacturing_date?`, `unit_cost?`. **This is a contract change** to receive
(`[DECIDE]` C1: batch_number operator-supplied (recommended — it's the
manufacturer lot) vs auto-generated).

**Flow (extends, never bypasses, the keystone):** inside the existing single
receive transaction, for each line: create a `batch`
(`received_via_po_id = po.id`, `vendor_id = po.vendor_id`,
`initial_quantity = quantity`), then `record_movement(IN, PURCHASE,
batch_id=<new batch>, reference_type='PURCHASE_ORDER', reference_id=po.id)`.
Item stock, the ledger, and the batch all move together or not at all.

**Errors:** `409 PO_NOT_DRAFT` (existing); `422` for missing/invalid batch info;
`409 DUPLICATE_BATCH`.

**Test plan:** receive a 2-line PO → 2 lots created, 2 IN movements each with
`batch_id` set, item stock += sums, PO → RECEIVED; missing batch info → 422;
re-receiving → 409; rollback leaves no partial lots.

---

## Phase 1D — SO ship → FEFO ✅ SHIPPED (2026-06-12)

**Decision D1 resolved:** consume any **non-expired** lot regardless of
`batch_status` (QC RELEASED-only gating arrives with the QC workflow in
Phase 2). Recommended over-coverage rule adopted: ship draws only from
lots; if non-expired lots can't cover a line it's `409 INSUFFICIENT_STOCK`
**even when `items.stock_quantity` looks sufficient** — the uncovered part
would be untraceable (unbatched) stock, which a pharma system must not ship.

**Shipped:**
- `BatchRepository.list_consumable_for_item(item_id, as_of)` — non-expired,
  in-stock lots, earliest-expiry first, `FOR UPDATE` (serialises concurrent
  ships, prevents over-consumption).
- `SalesOrderService.ship_so` now consumes each line FEFO via
  `_consume_line_fefo`: sums available non-expired lots → `409` if short →
  else draws earliest-expiry first, decrementing each lot and recording one
  OUT/SALE movement per lot touched (each with `batch_id`). Item stock and lot
  quantities drop by the same amount, preserving `Σ lot ≤ item stock`. Whole
  ship still rolls back on any failure (atomic).
- **No route/schema change** — FEFO is automatic, so `/ship` stays body-less.
- No migration.

**Verification:** `ruff` + `ruff format` clean; `mypy src` clean (70 files);
**`pytest` 253 passed** (250 prior + 3 new 1D tests; 4 existing ship tests
updated to give their stock a lot first, since only lot-tracked stock ships now).
New tests pin: FEFO order (earliest lot drained first, one movement per lot),
expired lots excluded (→ 409), and unbatched stock not shippable (→ 409 with
full rollback).

**Files:** `repositories/batch_repo.py`, `services/sales_order_service.py`,
`tests/test_sales_orders.py`.

**How to test (you):**
```powershell
python -m pytest -q tests/test_sales_orders.py
```

> **Phase 1 is complete (1A–1D).** Items carry pharma attributes; lots are
> created (opening-balance + PO receive) and consumed FEFO on ship; every
> movement is lot-linked. Remaining for a production pharma cutover: **Phase 2**
> — QC release workflow (gate shipping on RELEASED) and flipping the stock
> source-of-truth to batches (so all stock is lot-tracked, no "unbatched"
> remainder).

### Original spec (for reference)

**Goal:** shipping a sales order consumes stock **First-Expiry-First-Out** across
lots.

**Flow:** `POST /sales-orders/{id}/ship` — for each line, walk that item's lots
by `expiry_date` ascending, decrement `batch.quantity` across as many lots as
needed, and `record_movement(OUT, SALE, batch_id=<lot>, ...)` **once per lot
touched** (a line may now span several movements). Skip expired lots.

**`[DECIDE]` D1 — eligibility:** consume only `RELEASED` lots, or any
non-expired lot regardless of `batch_status`? Since the QC *workflow* is
deferred (everything defaults to QUARANTINE), consuming RELEASED-only would
block all shipping. Recommendation: **for 1D, consume any non-expired lot
regardless of status**, and tighten to RELEASED-only when the QC release flow
ships in Phase 2.

**Errors:** `409 SO_NOT_DRAFT` (existing); `409 INSUFFICIENT_STOCK` when the
sum of eligible lots can't cover the line (whole order rolls back).

**Test plan:** ship a line spanning 2 lots → consumes earliest-expiry first,
2 OUT movements with `batch_id`; expired lots skipped; insufficient eligible
stock → 409 + full rollback; item stock decremented by the shipped total.

---

## Phase 1E — Multi-lot PO receive (#10) ✅ SHIPPED (2026-06-15)

**Spec.** A PO line can be received as several lots in one shipment.
`PurchaseOrderReceiveLine` gains an optional per-lot `quantity`; `receive_po`
groups lots by item via `_lots_by_item`, resolves quantities, and creates one
`batches` row + one IN movement **per lot**. Backward-compatible: a single lot
may omit `quantity` (takes the whole line — the 1C contract). Split lines must
sum to the line quantity.

**Errors:** `422 RECEIVE_QUANTITY_MISMATCH` (lots don't sum / split lot omits
qty), `409 DUPLICATE_BATCH` (same number twice in the payload or already used),
`422 RECEIVE_LINES_MISMATCH` (lots don't cover the lines). No migration (uses the
existing `batches` table). **257 → tests; +4 multi-lot.**

---

## Phase 1F — SO batch selection (#9, + #6) ✅ SHIPPED (2026-06-15)

**Spec.** A sales-order line may name the lot it ships from.
`sales_order_items` gains a nullable `batch_id` FK→`batches` (migration
`a3f9c1d27e54`, reversible). `SalesOrderLineCreate`/`Read` gain `batch_id`.
`create_so` validates a chosen lot's existence + item-match (stock/expiry are
left to ship, like quantity). `ship_so` branches: `batch_id` set →
`_consume_line_from_batch` (lock the lot, require non-expired + ≥ line qty, one
OUT movement); `batch_id` NULL → **FEFO, unchanged** (every prior ship test
stays green — non-breaking). #6 is delivered because Excel-imported stock becomes
shippable by recording an opening-balance lot and selecting it.

**Errors:** `404 BATCH_NOT_FOUND`, `422 BATCH_ITEM_MISMATCH` (create);
`409 INSUFFICIENT_STOCK` (chosen lot too small), `409 BATCH_NOT_SHIPPABLE`
(chosen lot gone / wrong item / expired) at ship — whole ship rolls back.
**263 tests; +6.**

---

## Phase 1G — Item soft-delete (#1) ✅ SHIPPED (2026-06-15)

`DELETE /items/{id}` → `ItemService.soft_delete` sets `is_active=false` (204,
idempotent, 404 if unknown). `GET /items` excludes inactive unless
`include_inactive=true` (`ItemRepository.list_`). No migration (`is_active`
exists). No hard delete — history (movements/lots/POs/SOs) is preserved.

## Phase 1H — QC status transitions + ship gating (#7) ✅ SHIPPED (2026-06-15)

`POST /batches/{id}/status` → `BatchService.change_status`, validated against
`_ALLOWED_TRANSITIONS` (QUARANTINE→RELEASED/REJECTED, RELEASED→RECALLED; else
`409 INVALID_BATCH_TRANSITION`). New `SHIPPABLE_BATCH_STATUSES = {QUARANTINE,
RELEASED}` filters FEFO (`batch_repo.list_consumable_for_item`) and the explicit
SO lot pick (`_consume_line_from_batch` → `409 BATCH_NOT_SHIPPABLE`), so a
recall/reject immediately removes stock from sale. **Deliberately NOT enforcing
RELEASED-only** (QUARANTINE still ships) — that policy would block currently
shippable received stock; left as a separate decision.

## Phase 1I — Adjustment targeting a lot (#8) ✅ SHIPPED (2026-06-15)

`AdjustmentCreate.batch_id` optional. `record_adjustment` → `_apply_batch_delta`
locks the lot, validates item-match (`422 BATCH_ITEM_MISMATCH`), and moves the
lot quantity with the item total in one transaction (OUT can't drive a lot
negative → `409 INSUFFICIENT_STOCK`). Blank `batch_id` = item-aggregate only
(unchanged). (#2 structured-ingredient *input* is frontend-only — storage stays
the JSON-in-text `finished_detail.ingredients`, so no backend change.)

**Verification (1E–1I):** `pytest` **280 passed**, `ruff` + `mypy` clean,
migration `a3f9c1d27e54` reversible.

## Phase 1J — Server-side `status` filter on `GET /items` ✅ SHIPPED (2026-06-16)

From testing-team feedback: the dashboard "Needs Attention → All →" deep-link
landed on an Items list that showed "No items found" while the pager said
"1-25 of 31". Root cause was twofold (the frontend half is logged in
`../Frontend/execution.md`); the backend half: there was **no way to filter
items by their derived stock-health status**, so the frontend filtered the
loaded page client-side — wrong totals, and matches beyond page 1 were invisible.

`GET /items` now accepts a **repeatable** `status` query param
(`list[ItemStatus] | None`): `?status=LOW_STOCK&status=NO_STOCK` returns
everything in *any* of the requested buckets (the "needs attention" view).
`ItemRepository._status_predicate` is the SQL mirror of the computed
`ItemRead.status` rule (kept in lock-step with the schema, cross-referenced in
both files); `list_` ORs the per-status predicates. No migration — `status` is
derived, never stored. Threaded through `ItemService.list_` unchanged otherwise.

**Verification:** `pytest tests/test_items.py` **31 passed** (+3: single-status
buckets, multi-status any-of, no-threshold → IN_STOCK); full suite `ruff` +
`mypy` clean.

---

## Open decisions to resolve before each slice

- **A1** — nested vs flat detail representation → **RESOLVED: nested** (shipped in 1A).
- **B1** — batch↔stock reconciliation → **RESOLVED: opening-balance association** (shipped in 1B; new stock via 1C).
- **B2** — movement for association → **RESOLVED: no movement** (pure metadata, no net change).
- **B3** — QC status PATCH in 1B → **RESOLVED: deferred** (status settable on create; transition workflow is Phase 2).
- **C1** — operator-supplied vs auto-generated batch numbers → **RESOLVED: operator-supplied** (shipped in 1C).
- **D1** — RELEASED-only vs any-non-expired consumption → **RESOLVED: any
  non-expired** (shipped in 1D; tighten to RELEASED-only when QC ships).

*Resolve the relevant `[DECIDE]`s, then we build that one slice, test it green,
and stop for review before the next.*
