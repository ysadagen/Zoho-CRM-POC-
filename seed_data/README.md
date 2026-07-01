# Seed data — pgAdmin import guide

13 CSVs, ~300–400 rows each (700 for `items`, since it feeds the two 1:1
detail tables — see note below). All UUIDs, FKs, enums and CHECK
constraints are pre-validated against the schema in `Backend/src/app/models/`
and `Backend/migrations/versions/`.

## Import order (must follow — respects foreign keys)

Run migrations first (`alembic upgrade head`) so tables/enums/sequences exist,
then in pgAdmin right-click each table → **Import/Export Data...** → Import,
in this exact order:

1. `01_users.csv` → `users`
2. `02_customers.csv` → `customers`
3. `03_vendors.csv` → `vendors`
4. `04_items.csv` → `items`
5. `05_raw_item_details.csv` → `raw_item_details`
6. `06_finished_item_details.csv` → `finished_item_details`
7. `07_vendor_item_terms.csv` → `vendor_item_terms`
8. `08_purchase_orders.csv` → `purchase_orders`
9. `09_purchase_order_items.csv` → `purchase_order_items`
10. `10_batches.csv` → `batches`
11. `11_sales_orders.csv` → `sales_orders`
12. `12_sales_order_items.csv` → `sales_order_items`
13. `13_stock_movements.csv` → `stock_movements`

## pgAdmin import settings

- Format: CSV, Header: Yes, Delimiter: `,`, Quote: `"`
- Leave "NULL string" blank-default behavior on — empty CSV fields are written
  for nullable columns (`phone`, `gstin`, `received_date`, `batch_id`, etc.)
  and should import as SQL `NULL`, not empty string. If your pgAdmin version
  imports blanks as empty string instead, set the import dialog's **NULL
  Columns** option to match, or run afterward:
  `UPDATE <table> SET <col> = NULL WHERE <col> = '';` for the optional text
  columns.
- All UUID columns are already valid v4 UUIDs as text — Postgres casts them
  on import.
- Timestamps are ISO-8601 with `+00:00` offset; dates are `YYYY-MM-DD`.

## Row counts and why `items` is 700, not ~350

| table | rows |
|---|---|
| users | 350 |
| customers | 350 |
| vendors | 350 |
| items | 700 (350 RAW + 350 FINISHED) |
| raw_item_details | 350 |
| finished_item_details | 350 |
| vendor_item_terms | 380 |
| purchase_orders | 350 |
| purchase_order_items | 416 |
| batches | 380 |
| sales_orders | 350 |
| sales_order_items | 408 |
| stock_movements | 400 |

`raw_item_details` and `finished_item_details` are strict 1:1 children of
`items`, split by `items.type`. To land both detail tables in the 300–400
range, `items` itself needed ~700 rows (350 of each type) — every RAW item
has exactly one `raw_item_details` row and every FINISHED item has exactly
one `finished_item_details` row, never both.

Line-item tables (`purchase_order_items`, `sales_order_items`) average
~1.2 lines per order so both the header and line tables land near 400 rows
together, rather than forcing unrealistic 1-line-per-order orders.

## Data profile

Indian pharma distributor: GSTINs, INR pricing, Indian city addresses,
real INN generic drug names (Paracetamol, Azithromycin, Metformin, etc.)
with fictional brand names (no real trademarks used), pharmacopoeia
standards (IP/BP/USP/EP/JP), drug schedules (NONE/H/H1/X), dosage forms,
batch/expiry (FEFO) tracking, QC batch statuses.

## What's guaranteed vs. simplified

Guaranteed (re-checked programmatically, `verify.py` in the generator
folder, 0 errors): every FK resolves, every UNIQUE/CHECK constraint in the
SQLAlchemy models and Alembic migrations holds (non-negative quantities,
`status` ↔ `received_date`/`shipped_date` consistency, `(po,item)` /
`(so,item)` / `(item,batch_number)` uniqueness, 1:1 RAW/FINISHED detail
split, etc.), and every `stock_movements` row is arithmetically self
consistent (`stock_after = stock_before ± quantity`, never negative).

Simplified: `stock_movements` rows are generated in processing order
(PO receipts → opening-balance lots → SO shipments → manual adjustments),
not strictly re-sorted by timestamp across an item's whole history, and
`items.stock_quantity` is set from that same processing-order running
total rather than a live trigger-maintained aggregate — consistent with
this schema's documented design (`items.stock_quantity` is an independent
authoritative field, not DB-derived from movements).
