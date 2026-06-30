# Remove Invoice/Payment, move payment tracking onto SalesOrder

**Status: planned, not implemented.** This is a design document for a future
change — no code has been written against this plan yet.

## Context

While auditing Zoho field mapping (`ZOHO_FIELD_MAPPING.md` §5), we flagged
that `Invoice`/`Payment` rows are frequently never created for real sales
orders — a manual, separate step nobody reliably does — which leaves
Customer Health's DSO and payment-risk scoring components permanently
defaulted. Rather than bolt on invoice-auto-creation, the decision is to
remove the Invoice/Payment entities entirely and track payment state (due
date, amount paid, last paid date) directly on `SalesOrder`, since that's
the one record that already exists for every real transaction and already
has the DRAFT→SHIPPED lifecycle this naturally hangs off of.

**Explicit tradeoff being accepted:** the current `Payment` model supports
multiple partial payments per invoice, each with its own date/amount (full
history). Collapsing onto `SalesOrder.paid_amount` + `SalesOrder.paid_date`
keeps only a **running total and the most recent payment date** —
per-payment history is lost. DSO and overdue/outstanding calculations still
work correctly (they only ever needed the cumulative state), but you can no
longer answer "list every individual payment made against this order."
Confirmed acceptable per explicit user choice.

**Confirmed zero Frontend impact** — no invoice/payment UI exists anywhere
in `Frontend/`.

## Backend changes

**`src/app/models/sales_order.py`** — add to `SalesOrder`:
- `due_date: Date | None` — null until shipped.
- `paid_amount: Numeric(14,2)`, default `0`, not null.
- `paid_date: Date | None`.
- New CHECK constraints: `paid_amount >= 0` and `paid_amount <= total`.

**`src/app/services/sales_order_service.py`**:
- `ship_so()` (lines 221-307): when setting `status=SHIPPED` / `shipped_date`, also set `due_date = shipped_date + timedelta(days=_PAYMENT_TERMS_DAYS)`. Add a module-level constant `_PAYMENT_TERMS_DAYS = 30` (Phase-1 default, same style as other small constants in this codebase, e.g. `_EXPIRY_SKEW_SECONDS` in the Integration Layer's `token_service.py`).
- New method `record_payment(so_id, payload, *, actor_id) -> SalesOrder`: lock the row, 404 if missing, 409 `SALES_ORDER_NOT_SHIPPED` if `status != SHIPPED`, 409 `OVERPAYMENT` if `paid_amount + payload.amount > total`, else update `paid_amount += payload.amount`, `paid_date = payload.paid_date`, commit, refresh, return. Mirrors the overpayment-prevention rule from the old `invoice_service.record_payment` (lines 90-129).

**`src/app/repositories/sales_order_repo.py`** — no new query methods needed; `record_payment` just updates the already-fetched row via the service's existing lock/fetch pattern (same as `ship_so`).

**`src/app/schemas/sales_order.py`**:
- Extend `SalesOrderRead` (lines 78-97) with `due_date: date | None`, `paid_amount: Decimal`, `paid_date: date | None`, and derived `outstanding: Decimal`, `is_paid: bool`, `is_overdue: bool` — same derivation logic as the old `InvoiceRead.from_invoice` (lines 91-114 of the old `schemas/invoice.py`): `outstanding = total - paid_amount`, `is_paid = outstanding <= 0`, `is_overdue = outstanding > 0 and due_date is not None and due_date < today`.
- New `SalesOrderPaymentCreate(BaseModel)`: `paid_date: date`, `amount: Decimal = Field(gt=0)`.

**`src/app/api/v1/sales_orders.py`** — new route `POST /sales-orders/{so_id}/payments` (201, returns `SalesOrderRead`), same auth (`_CurrentUser`) as the other three routes (lines 40-130).

**Remove entirely:**
- `src/app/models/invoice.py`
- `src/app/repositories/invoice_repo.py`
- `src/app/services/invoice_service.py`
- `src/app/schemas/invoice.py`
- `src/app/api/v1/invoices.py`
- `tests/test_invoices.py`
- The invoice router import + mount in `src/app/main.py` (lines 30, 270)

**Migration** — new Alembic revision, `down_revision` = current head (`f4b6c8e0a3d5_add_invoices_and_payments`):
- `upgrade()`: add `due_date`, `paid_amount`, `paid_date` columns + the two CHECK constraints to `sales_orders`; then drop `payments`, drop `invoices`, drop `invoice_number_seq` (same order as that migration's own `downgrade()`, lines 78-81).
- `downgrade()`: recreate `invoice_number_seq`/`invoices`/`payments` (mirroring `f4b6c8e0a3d5`'s `upgrade()`), then drop the 3 new `sales_orders` columns/constraints.

**Tests** — replace `test_invoices.py`'s 9 cases with equivalent coverage in `test_sales_orders.py` (or a new file): ship sets `due_date` correctly; payment happy path updates `outstanding`; full payment sets `is_paid`; overpayment → 409; payment on a DRAFT (unshipped) order → 409; payment on unknown order → 404; DB-level CHECK constraint test for `paid_amount` bounds.

## Intelligence service changes

**`src/app/models/sales_order.py`** — mirror the same 3 new columns (`due_date`, `paid_amount`, `paid_date`) onto Intelligence's own read-only `SalesOrder` model, matching its existing pattern of mirroring only the columns the engines need.

**Remove entirely:**
- `src/app/models/invoice.py` (Invoice + Payment mirror classes)
- Their imports/exports in `src/app/models/__init__.py` (lines 21, 41, 46)

**`src/app/repositories/customer_metrics_repo.py`** — rewrite two methods to query `SalesOrder` instead of `Invoice`/`Payment`:
- `dso_days()` (lines 98-129): filter `SalesOrder.customer_id`, `status == SHIPPED`, `paid_amount >= total` (fully paid), `paid_date` in `[since, as_of]`; weighted average of `(paid_date - shipped_date)` weighted by `total` — same shape as today, just reading from one table instead of joining two.
- `outstanding_totals()` (lines 131-161): for `SHIPPED` orders, `outstanding = total - paid_amount`; `total_outstanding` = sum where `outstanding > 0`; `overdue_outstanding` = sum where `outstanding > 0 and due_date < as_of`.

No changes needed in `services/scoring/customer_health.py` — `CustomerHealthInputs.dso_days`/`overdue_outstanding`/`total_outstanding` field names and consumption (`_payment_discipline`, `_payment_risk`) stay identical; only how the orchestrator gathers them changes.

**Tests:**
- `tests/factories.py` — remove `make_invoice`/`make_payment` (lines 130-158); the existing `make_sales_order` factory (line 97) needs to support setting `due_date`/`paid_amount`/`paid_date`/`status=SHIPPED` directly for test setup.
- `tests/scoring/test_customer_health.py`'s DSO band-edge test (line 68) needs **no change** — confirmed it constructs `CustomerHealthInputs(dso_days=...)` directly and tests the pure banding function, never touching the repo query.
- Add a new repository-level test for the rewritten `dso_days()`/`outstanding_totals()` against real `SalesOrder` rows (no equivalent test existed for the old Invoice-based queries, so this is net-new coverage, not a replacement).

## Verification (once implemented)

1. Backend: `uv run pytest`, `uv run ruff check`, `uv run mypy src` — all green (per `CLAUDE.md` Definition of Done).
2. Intelligence: same three commands in its own venv.
3. Manual end-to-end: create a sales order, ship it (confirm `due_date` auto-set to shipped_date+30), record a partial payment (confirm `outstanding`/`is_paid` correct, `dso_days` still `None` since not fully paid), record the final payment (confirm `is_paid=true`, `paid_date` set), then call Intelligence's `GET /intelligence/customer-health/{id}` for that customer and confirm `payment_discipline`/`payment_risk` now reflect real computed values instead of falling back to defaults.
4. Confirm 409 `OVERPAYMENT` and 409 `SALES_ORDER_NOT_SHIPPED` both still fire correctly.
5. Update `ZOHO_FIELD_MAPPING.md`'s §5 "Data population gaps" section afterward — the `Invoice`/`Payment` gap entry should be replaced with a note that payment tracking now lives on `SalesOrder` and is auto-populated at ship time (due_date) plus via the new payments endpoint.
