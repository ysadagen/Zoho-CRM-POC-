# Proposal — Pharmaceutical Inventory: Raw / Finished Segregation + Batch Tracking

**Status:** Aligned to your ERD (`diagram-export-6-12-2026`) · **Scope:** Backend
DB structure only · **No application code yet.**

This revision locks the **four focus tables** — `items`, `batches`,
`raw_item_details`, `finished_item_details` — to match your schema diagram
exactly. **Every other table is treated as "correct as-is" per your
instruction**; your diagram is the master for those and this document does not
re-propose them (see §A on the few places the diagram differs from the live DB).

---

## 0. Decisions (locked)

| # | Question | Call |
|---|---|---|
| 1 | Stock source of truth | **Phased** — `items.stock_quantity` aggregate now, per-batch later |
| 2 | Rename `items` → `items_master`? | **No** — master stays named `items`; 4 FKs untouched |
| 3 | Batch-track raw materials too? | **Yes** — `batches` covers RAW and FINISHED |
| 4 | QC / quarantine workflow now? | **Minimal** — `batch_status` enum on `batches` now (full quarantine *workflow* still later) |
| 5 | Backfill legacy batches? | **No fabricated batches** — see §7.1 |
| 6 | Production / manufacturing (raw→finished)? | **Out of scope now** |
| 7 | Multi-location seam | **Kept** — `batches.storage_location varchar(120)` |
| 8 | Exact subtype columns | **Locked to the diagram** (§4) |

---

## 1. Final shape (TL;DR)

Master product table + two 1:1 detail tables + the batch (lot) table. The four
focus tables are below; the ledger link (`stock_movements.batch_id`) is shown in
your diagram and noted in §A.

```
                       ┌─────────────────────────────┐
                       │            items            │  the PRODUCT (stable SKU;
                       │  common + common-pharma cols │   PK & existing FKs intact)
                       │  stock_quantity = aggregate  │
                       └──┬───────────┬───────────┬───┘
              1:1 (RAW)   │           │ 1:1 (FIN) │ 1:N
                ▼         │           ▼           ▼
   ┌────────────────────┐│ ┌──────────────────────┐ ┌───────────────────────┐
   │  raw_item_details  ││ │ finished_item_details│ │        batches        │ the LOT
   │  (PK=item_id)      ││ │ (PK=item_id)         │ │ batch_no, mfg, expiry, │ (mfg/expiry/
   └────────────────────┘│ └──────────────────────┘ │ per-lot quantity, cost │  lot stock)
                         │                           └───────────────────────┘
```

- **item = product** (one row, stable SKU, referenced by POs/SOs/movements/terms).
- **batch = a physical lot** of that product (1:N): batch number, mfg/expiry,
  its own on-hand quantity.
- Phase 0 is additive — new tables + (per your diagram) a nullable
  `stock_movements.batch_id`. Existing behaviour and the 200+ tests stay green.

---

## 2. Current state — what we must not break

**Stock keystone:** `StockMovementService.record_movement` is the only writer of
`items.stock_quantity` (locks the row `FOR UPDATE`, computes `stock_after`,
rejects negative OUT, inserts the ledger row in one session). **Untouched in
Phase 0.**

**Four FKs point at `items.id`** (all `ON DELETE RESTRICT`):
`stock_movements.item_id`, `purchase_order_items.item_id`,
`sales_order_items.item_id`, `vendor_item_terms.item_id`. **All stay** — because
`item` remains the product (not the lot).

**Derived, not stored:** `ItemRead.status` (`IN_STOCK`/`LOW_STOCK`/`NO_STOCK`)
keeps working — stock stays aggregate in Phase 0.

---

## 3. Your field lists → final placement (with the one refinement)

Per-lot fields (batch number, mfg date, expiry) live on **`batches`**, not on the
item — one product has many lots over time; putting them on the item would force
a new item row per lot and break SKU identity + the four FKs.

| Original field (your list) | Lands in | Column |
|---|---|---|
| Id / SKU / Name / Category | `items` | `id` / `sku` / `name` / `category` |
| Unit Price | `items` | `unit_price` |
| Stock | `items` | `stock_quantity` (aggregate) |
| Unit of Measurement | `items` | `unit_of_measure` |
| Reorder Threshold | `items` | `reorder_threshold` |
| Storage Condition | `items` | `storage_condition` |
| Shelf Life | `items` | `shelf_life_days` |
| **Batch Number** | **`batches`** | **`batch_number`** |
| **Manufacturing Date** | **`batches`** | **`manufacturing_date`** |
| **Expiry Date** | **`batches`** | **`expiry_date`** |
| Material Classification | `raw_item_details` | `material_classification` |
| Dosage (Strength) / Dosage Form / Pack Size | `finished_item_details` | `strength` / `dosage_form` / `pack_size` |
| List of Ingredients / Container spec | `finished_item_details` | `ingredients` / `container_specification` |
| Brand / Generic name | `finished_item_details` | `brand_name` / `generic_name` |
| Selling Price | `finished_item_details` | `selling_price` |
| Product License / Registration code | `finished_item_details` | `license_number` / `registration_code` |

---

## 4. Final schema — the four focus tables (per the diagram)

Conventions: UUID PKs; `Numeric(20,4)` for inventory quantity; `Numeric(12,2)`
for money; `timestamptz` for `created_at`/`updated_at`; audit columns
`created_by_user_id` / `updated_by_user_id` (FK → `users.id`, RESTRICT).

### 4.1 `items` (master)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `sku` | `varchar(64)` UNIQUE | unchanged |
| `name` | `varchar(160)` | **diagram value** (live DB = 255) — see §A.1 |
| `type` | `item_type` enum | `RAW` / `FINISHED` |
| `category` | `varchar(80)` | **diagram value** (live DB = 64) — see §A.1 |
| `unit_of_measure` | `varchar(30)` | **diagram value** (live DB = 32) — see §A.1 |
| `description` | `text` | |
| `stock_quantity` | `numeric(20,4)` | aggregate (Phase 0 authoritative); CHECK ≥ 0 |
| `reorder_threshold` | `numeric(20,4)` | CHECK ≥ 0 / NULL |
| `unit_price` | `numeric(12,2)` | CHECK ≥ 0 |
| `storage_condition` | `storage_condition` enum | **NEW** |
| `shelf_life_days` | `integer` | **NEW** — product default; can default a batch's expiry |
| `is_active` | `boolean` | |
| `created_by_user_id` | uuid FK → `users.id` | |
| `updated_by_user_id` | uuid FK → `users.id` | |
| `created_at` / `updated_at` | `timestamptz` | |

Only `storage_condition` + `shelf_life_days` are added. No existing column is
removed. (Optional `is_batch_tracked`/`hsn_code`/`gst_rate` from the prior draft
are **dropped** — not in your diagram.)

### 4.2 `raw_item_details` (1:1 with `items`, PK = `item_id`)

| Column | Type | Notes |
|---|---|---|
| `item_id` | uuid **PK + FK** → `items.id` (RESTRICT) | shared PK = the 1:1 link |
| `material_classification` | `material_classification` enum | **NEW enum** (§4.5) |
| `pharmacopoeia` | `pharmacopoeia` enum | **NEW enum** (§4.5) |
| `is_hazardous` | `boolean` | |
| `created_by_user_id` / `updated_by_user_id` | uuid FK → `users.id` | |
| `created_at` / `updated_at` | `timestamptz` | |

### 4.3 `finished_item_details` (1:1 with `items`, PK = `item_id`)

| Column | Type | Notes |
|---|---|---|
| `item_id` | uuid **PK + FK** → `items.id` (RESTRICT) | shared PK |
| `generic_name` | `varchar(255)` | |
| `brand_name` | `varchar(255)` | |
| `strength` | `varchar(64)` | e.g. "500 mg" |
| `dosage_form` | `dosage_form` enum | **NEW enum** (§4.5) |
| `pack_size` | `varchar(64)` | |
| `ingredients` | `text` | list of ingredients |
| `container_specification` | `varchar(255)` | |
| `selling_price` | `numeric(12,2)` | customer price; CHECK ≥ 0 |
| `license_number` | `varchar(64)` | |
| `registration_code` | `varchar(64)` | |
| `mrp` | `numeric(12,2)` | Max Retail Price; CHECK ≥ 0 |
| `drug_schedule` | `drug_schedule` enum | **NEW enum** (§4.5) |
| `is_prescription_required` | `boolean` | |
| `created_by_user_id` / `updated_by_user_id` | uuid FK → `users.id` | |
| `created_at` / `updated_at` | `timestamptz` | |

### 4.4 `batches` (1:N from `items`) — the lot table

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `batch_number` | `varchar(64)` | internal/manufacturer lot no. |
| `batch_status` | `batch_status` enum | **NEW** — lot QC state (§4.5); default `QUARANTINE` |
| `batch_received_date` | `date` | **NEW** — when this lot entered inventory; nullable |
| `manufacturing_date` | `date` | nullable |
| `expiry_date` | `date` **NOT NULL** | drives FEFO + alerts (pharma integrity — §B.2 locked) |
| `quantity` | `numeric(20,4)` | on-hand for **this** lot; CHECK ≥ 0 |
| `initial_quantity` | `numeric(20,4)` | as-received, for traceability |
| `unit_cost` | `numeric(12,2)` | landed cost of this lot (valuation); nullable |
| `storage_location` | `varchar(120)` | physical location seam (decision #7); nullable |
| `vendor_id` | uuid FK → `vendors.id` (RESTRICT) | supplier of this lot; nullable |
| `received_via_po_id` | uuid FK → `purchase_orders.id` (RESTRICT) | provenance; nullable |
| `item_id` | uuid FK → `items.id` (RESTRICT) | which product |
| `created_by_user_id` / `updated_by_user_id` | uuid FK → `users.id` | |
| `created_at` / `updated_at` | `timestamptz` | |

**Constraints:** `UNIQUE (item_id, batch_number)`; CHECK `quantity >= 0`;
CHECK `initial_quantity >= 0`; CHECK `expiry_date >= manufacturing_date` (when
both set). **Indexes:** `(item_id, expiry_date)` for FEFO; `(expiry_date)` for
expiry reports; `(batch_status)` for the QC queue.

### 4.5 New enum types (values proposed — confirm in §B)

| Enum | On | Proposed values |
|---|---|---|
| `storage_condition` | `items` | `AMBIENT`, `COLD_CHAIN_2_8`, `FROZEN`, `CONTROLLED` |
| `material_classification` | `raw_item_details` | `API`, `EXCIPIENT`, `SOLVENT`, `REAGENT`, `PACKAGING` |
| `pharmacopoeia` | `raw_item_details` | `IP`, `BP`, `USP`, `EP`, `JP`, `NONE` |
| `dosage_form` | `finished_item_details` | `TABLET`, `CAPSULE`, `SYRUP`, `SUSPENSION`, `INJECTION`, `OINTMENT`, `CREAM`, `GEL`, `DROPS`, `POWDER`, `INHALER`, `OTHER` |
| `drug_schedule` | `finished_item_details` | `NONE`, `H`, `H1`, `X` (extend as needed) |
| `batch_status` | `batches` | `QUARANTINE` (default on receipt), `RELEASED`, `EXPIRED`, `REJECTED`, `RECALLED` |

> Postgres enums grow via `ALTER TYPE … ADD VALUE` in a migration — additive and
> safe. `API` = Active Pharmaceutical Ingredient.

**Type↔detail invariant** (service + ideally a DB trigger): `type = RAW` ⇒
exactly one `raw_item_details`, zero `finished_item_details` (mirror for FINISHED).

---

## 5. ERD — the four focus tables + their links

Your `diagram-export-6-12-2026` is the master for the whole DB. The Mermaid below
mirrors the **four focus tables** and how they attach to the rest (other tables
shown as stubs — see them in your diagram).

```mermaid
erDiagram
    items ||--o| raw_item_details : "1:1 (RAW)  [NEW]"
    items ||--o| finished_item_details : "1:1 (FINISHED)  [NEW]"
    items ||--o{ batches : "has lots  [NEW]"
    items ||--o{ stock_movements : "item_id (existing)"
    items ||--o{ purchase_order_items : "item_id (existing)"
    items ||--o{ sales_order_items : "item_id (existing)"
    items ||--o{ vendor_item_terms : "item_id (existing)"
    batches ||--o{ stock_movements : "batch_id (per diagram, nullable)"
    vendors ||--o{ batches : "vendor_id (nullable)  [NEW]"
    purchase_orders ||--o{ batches : "received_via_po_id (nullable)  [NEW]"
    users ||--o{ items : "audit"
    users ||--o{ batches : "audit"

    items {
        uuid id PK
        varchar sku UK "64"
        varchar name "160"
        item_type type "RAW | FINISHED"
        varchar category "80"
        varchar unit_of_measure "30"
        text description
        numeric stock_quantity "20,4 aggregate"
        numeric reorder_threshold "20,4"
        numeric unit_price "12,2"
        storage_condition storage_condition "NEW"
        integer shelf_life_days "NEW"
        boolean is_active
        uuid created_by_user_id FK
        uuid updated_by_user_id FK
    }
    raw_item_details {
        uuid item_id PK_FK
        material_classification material_classification
        pharmacopoeia pharmacopoeia
        boolean is_hazardous
        uuid created_by_user_id FK
        uuid updated_by_user_id FK
    }
    finished_item_details {
        uuid item_id PK_FK
        varchar generic_name "255"
        varchar brand_name "255"
        varchar strength "64"
        dosage_form dosage_form
        varchar pack_size "64"
        text ingredients
        varchar container_specification "255"
        numeric selling_price "12,2"
        varchar license_number "64"
        varchar registration_code "64"
        numeric mrp "12,2"
        drug_schedule drug_schedule
        boolean is_prescription_required
        uuid created_by_user_id FK
        uuid updated_by_user_id FK
    }
    batches {
        uuid id PK
        varchar batch_number "64"
        batch_status batch_status "NEW, default QUARANTINE"
        date batch_received_date "NEW"
        date manufacturing_date
        date expiry_date "NOT NULL, indexed"
        numeric quantity "20,4 lot on-hand"
        numeric initial_quantity "20,4"
        numeric unit_cost "12,2"
        varchar storage_location "120"
        uuid vendor_id FK "nullable"
        uuid received_via_po_id FK "nullable"
        uuid item_id FK
        uuid created_by_user_id FK
        uuid updated_by_user_id FK
    }
    stock_movements {
        uuid id PK
        uuid item_id FK
        uuid batch_id FK "per diagram, nullable"
    }
    purchase_orders { uuid id PK }
    sales_order_items { uuid id PK }
    purchase_order_items { uuid id PK }
    vendor_item_terms { uuid id PK }
    vendors { uuid id PK }
    users { uuid id PK }
```

---

## 6. Stock model — phased (locked)

- **Phase 0–1:** `items.stock_quantity` stays the source of truth;
  `batches.quantity` maintained alongside; a reconciliation test asserts
  `items.stock_quantity == Σ(batch.quantity)` for batch-tracked items. Existing
  endpoints, ledger and `status` behave identically.
- **Phase 2+:** flip the source of truth to per-batch quantities behind the same
  `record_movement` chokepoint.

---

## 7. Migration strategy — phased, non-breaking

**Phase 0 — structure only (additive)**
1. `ALTER items` add `storage_condition`, `shelf_life_days` (+ resize columns
   only if §A.1 confirmed).
2. `CREATE` the new enums (§4.5), then `raw_item_details`,
   `finished_item_details`, `batches`.
3. (Per diagram) `ALTER stock_movements` add nullable `batch_id`.
4. Backfill the detail row per existing item by `type` (NULLs) — §7.1.
5. ORM models + **read** schemas expose new fields; create/update endpoints
   unchanged. All current tests stay green.

**Phase 1** — batch CRUD + PO *receive* creates a batch & stamps `batch_id`;
expiry / "expiring soon" reports.
**Phase 2** — SO *ship* consumes earliest-expiry lots first (FEFO).
**Phase 3 (optional)** — flip stock to batches; later: QC `status`,
production/BOM, real `locations` table.

Phases 0–1 are additive → clean `downgrade()`.

### 7.1 Legacy stock & batches (decision #5)

No fabricated batches with placeholder expiry (a pharma system must never carry
fake expiry). Phase 0 backfills only the **detail** rows (NULLs). Existing stock
stays the item-level aggregate (batch-less legacy); a Phase-1 opening-balance
action records real batch + expiry for existing physical stock when known.

---

## 8. Whole-DB sanity checks (kept in mind)

- `vendor_item_terms` is product-level pricing → unaffected. ✔
- PO/SO **lines** stay product-level; lot linkage is recorded on
  `stock_movements.batch_id`, not on the order line. ✔
- `ItemRead.status` keeps working (aggregate stock). ✔
- `batches.quantity` is `Numeric(20,4)` to match `items.stock_quantity`. (The
  existing ledger's `Numeric(14,3)` is a pre-existing inconsistency — separate
  cleanup, not this change.)

---

## 9. Impact assessment — Phase 0

| Area | Impact |
|---|---|
| `items.id` PK & the 4 FKs | unchanged |
| `record_movement` keystone | unchanged |
| Existing `items` columns | unchanged in *meaning* (size deltas pending §A.1) |
| `/items`, `/stock-movements`, PO/SO endpoints | unchanged behaviour |
| `ItemRead.status` | unchanged |
| Existing 200+ tests | stay green; new tests for new tables |

---

## A. Where the diagram differs from the live DB (heads-up, not in scope)

Per your instruction the non-focus tables are "correct as-is", so this is just a
flag for when we eventually implement — **no action requested now.**

- **A.1 — `items` column sizes (LOCKED: keep current `255`/`64`/`32`).**
  The diagram shows `name(160)`/`category(80)`/`unit_of_measure(30)`, but
  narrowing `name`/`unit_of_measure` risks truncating existing rows for no real
  benefit. To honour "don't disturb", Phase 0 **keeps the live sizes** and does
  not ALTER them. (Override if you want the exact diagram sizes.)
- **A.2 — `batches.expiry_date` (LOCKED: `NOT NULL`).** Pharma must always know a
  lot's expiry.
- **A.3 — other tables (not in scope).** Your diagram models `stock_movements`
  with a single `movement_type` (live DB has `direction` + `reason`), and
  `created_by` (live: `created_by_user_id`); `vendors`/`customers` omit
  `vendor_code`/`customer_code`/`gstin`; `users` has `role` (live: `is_admin`);
  `purchase_orders`/`sales_orders` carry `source_type`/`source_reference`/
  `currency`/`total_amount`. These are **considered correct per your
  instruction** — we'd reconcile diagram-vs-live for these in their own track if
  ever needed.

---

## B. Decisions — locked for Phase 0

1. **`items` sizes** — keep current `255/64/32` (no risky narrowing). ✔ (§A.1)
2. **`batches.expiry_date`** — `NOT NULL`. ✔ (§A.2)
3. **Enum values** (§4.5) — building with the proposed sets (incl.
   `batch_status` = `QUARANTINE`/`RELEASED`/`EXPIRED`/`REJECTED`/`RECALLED`,
   default `QUARANTINE`). Adjusting an enum later is an additive
   `ALTER TYPE … ADD VALUE` — say the word if you want different values.
4. **`selling_price` vs `unit_price` for SO defaults** — keep current behaviour
   (default from `unit_price`) in Phase 0; revisit in Phase 1. ✔

---

## C. Phase 0 — IMPLEMENTED ✅ (additive structure)

Built to the decisions above. **Purely additive — no existing behaviour
changed.**

**Migration:** `migrations/versions/e7b2a9c4d1f8_add_pharma_batch_and_item_detail_tables.py`
(chains off head `4be90595bc88`). Creates the 6 enums, adds
`items.storage_condition` / `items.shelf_life_days`, creates
`raw_item_details` / `finished_item_details` / `batches`, adds nullable
`stock_movements.batch_id`, and backfills one detail row per existing item
(with a guard that raises if any item is left unclassified).

**Code:** new ORM models `RawItemDetail` / `FinishedItemDetail` / `Batch`
(registered in `models/__init__.py`); `Item` + `StockMovement` extended;
`ItemCreate`/`ItemUpdate`/`ItemRead` expose the two new common fields;
`ItemService.create` now also creates the matching 1:1 detail row in the
same transaction (invariant: every item owns exactly one detail row).

**Verification (all green):**
- `ruff check` + `ruff format --check` — clean (81 files).
- `mypy src` — clean (64 files).
- `pytest` — **222 passed** (206 existing + 16 new); the suite bootstrap runs
  the new migration end-to-end, so the migration itself is proven.
- Migration **down→up round-trip** verified against the test DB.

> Test bootstrap (`tests/conftest.py`) now invokes Alembic via
> `sys.executable -m alembic` instead of `uv run alembic` (the latter is
> blocked by local Application Control).

**To apply on your dev DB:**
```powershell
docker compose up -d            # from Code/ (if not already running)
python -m alembic upgrade head  # from Code/Backend, venv active
```

## D. Next — Phase 1 (not built yet)

Batch CRUD endpoints, PO *receive* creating a batch + stamping
`stock_movements.batch_id`, subtype detail fields on the item create/update
surface, and expiry / "expiring soon" reporting. Scoped as its own slice
when you're ready.
