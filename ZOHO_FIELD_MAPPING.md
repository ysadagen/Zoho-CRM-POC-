# Zoho CRM ↔ App Field Mapping

This is the single source of truth for field mapping between Zoho CRM and the
app's database. Both `Integration_Layer/src/app/services/ingest_service.py`
(Track A — Zoho → App) and any future `sync_service.py` (Track B — App →
Zoho) should implement against this document, not their own ad-hoc field
lists. The Track A pipeline drifted from its own field requirements multiple
times during this engagement precisely because no single spec existed —
this doc exists to stop that.

**Method note:** field lists below come from two sources —

- **App side:** read directly from the live SQLAlchemy models
  (`Backend/src/app/models/`) on 2026-06-24 — these are exact.
- **Zoho side:** the OAuth grant in use lacks `ZohoCRM.settings.fields.READ`,
  so `/settings/fields?module=X` isn't queryable via API. Instead, the
  authoritative field lists below come from **Zoho's own "Export → All
  Fields" CSV export per module, run 2026-06-25** — this is the true,
  complete field set per module (not a list-view's limited columns; an
  earlier "fields in current view" export was caught giving an incomplete
  list and discarded). Confirmed modules: **Leads, Accounts, Deals, Calls,
  Meetings, Tasks, Products, Sales_Orders, Purchase_Orders**. **Vendors and
  Users are still pending an "All Fields" re-export** (Zoho's daily export
  limit was hit) — treat those two sections as the older, view-limited list
  until re-exported.

---

## Status summary (as of 2026-06-25)

**Resolved decisively:**
- **`district`** (Lead) — confirmed it genuinely doesn't exist anywhere in Zoho (not a native concept). A real decision is still needed: add a custom field, or accept app-only.
- **`pincode`** and **`customer_id`** (Lead) — turned out to be **free wins**: both fields (`Zip_Code`, `Converted_Account`) already exist on Zoho Leads, just weren't in the ingest pipeline's `fields=` request list. No custom fields needed — just a one-line code change to `Integration_Layer/src/app/clients/zoho/endpoints.py`'s `MODULE_FIELDS["Leads"]` entry.
- **Accounts / Products / Sales_Orders / Purchase_Orders** — confirmed these modules already exist in the org with shapes compatible with the existing Track B design in `ZOHO_CRM_SPECIFICATION.md`.

**Still genuinely missing — needs a real decision (custom field vs. app-only):**
- Lead: `quantity`, `item_id`, `estimated_budget`, `dealer_potential`, `required_by_date`.
- Customer/Account: `gstin`, `customer_code`, `is_privileged`, `competitive_risk_level`.

**Still pending:**
- **Vendors** and **Users** modules were exported with the old, view-limited method (not "All Fields") — both need a re-export once Zoho's daily export limit resets, to close out the last two unconfirmed sections (§2.2's `Calls`/`Meetings`/`Tasks` owner resolution depends on Users; Track B's Vendor sync depends on Vendors).

**Not yet decided (action pending from the open items in §6):**
- Whether to apply the two free wins (`Zip_Code`, `Converted_Account`) now or hold until the full doc — including Vendors/Users — is finalized.

---

## 0. DB schema completeness check (done — see below)

Before mapping anything, every field used by the four scoring engines
(`LeadScoringInputs`, `CustomerHealthInputs`, `RepEffortInputs`,
`BeatCustomerInput`) was cross-checked against the live model columns.
**Result: zero missing columns.** Every field a scoring engine needs already
exists in the schema. The work below is entirely about *connecting* those
existing columns to Zoho, not adding new ones.

---

## 1. Entity inventory (both directions)

| App entity | Zoho counterpart | Track A (Zoho→App) | Track B (App→Zoho) |
|---|---|---|---|
| Lead | Leads module | ✅ Built | ❌ N/A (leads originate in either system independently) |
| SalesActivity | Calls / Events / Tasks modules | ✅ Built (lead-linked only) | ❌ Not built |
| Lead (won) | Deals module | ✅ Built (Closed-Won only) | ❌ Not built |
| Customer | Accounts module | ❌ Not built | 📝 Designed in `ZOHO_CRM_SPECIFICATION.md` §3.1, not implemented |
| Item | Products module | ❌ Not built | 📝 Designed (§3.3), optional, not implemented |
| SalesOrder | Sales Orders module | ❌ Not built | 📝 Designed (§3.4), not implemented |
| Invoice / Payment | — | ❌ Not built | ❌ Not designed or built |
| User (rep) | Zoho Users | Used read-only for owner-email attribution only | ❌ Not synced as records |
| Vendor / PurchaseOrder | Vendor / Purchase Order modules | N/A | 📝 Designed (§3.2, §3.5), not implemented |

---

## 1.1 Full physical table inventory (26 tables, both Backend `inventory_db` and Intelligence's own tables)

This is §1 above broken down to the literal table level, including the
tables that were never in scope for §1 (scoring/snapshot tables and
infrastructure tables) so the *complete* picture is in one place.

### Business entities — actual Zoho sync candidates

| Table | What it's for | Zoho status |
|---|---|---|
| `leads` | Core Lead record | ✅ **Mapped (Track A)** — Zoho `Leads`→app. Several fields still gap (`quantity`, `item_id`, `estimated_budget`, `dealer_potential`, `required_by_date`, `district` — see §4) |
| `lead_stage_history` | Tracks every stage transition a lead goes through (used by Effort/Efficiency's "progressed" metric) | Indirectly driven by ingest's `Lead_Status` mapping — not directly Zoho-mapped itself |
| `sales_activities` | Calls/Visits/Meetings/Follow-ups logged against a lead or customer | ✅ **Mapped (Track A)** — Zoho `Calls`/`Events`/`Tasks`→app. Gap: only Lead-linked activities ingest; customer-linked Zoho activity is silently parked |
| `customers` | Core Customer record | ❌ **Not built (Track B)** — maps to Zoho `Accounts`; design exists in `ZOHO_CRM_SPECIFICATION.md` §3.1, confirmed compatible shape, not implemented |
| `items`, `finished_item_details`, `raw_item_details` | Product/SKU master (+ pharma-specific subtype detail) | ❌ **Not built (Track B)** — maps to Zoho `Products`; confirmed compatible shape, not implemented |
| `sales_orders`, `sales_order_items` | Customer orders + line items | ❌ **Not built (Track B)** — maps to Zoho `Sales_Orders` module (confirmed already exists in the org); also about to gain `due_date`/`paid_amount`/`paid_date` per `INVOICE_TO_SALES_ORDER_MIGRATION_PLAN.md` |
| `vendors` | Supplier master | ❌ **Not built (Track B)** — maps to Zoho `Vendors`; export still pending an "All Fields" re-export |
| `purchase_orders`, `purchase_order_items` | Orders placed to vendors | ❌ **Not built (Track B)** — maps to Zoho `Purchase_Orders` module (confirmed exists) |
| `invoices`, `payments` | AR/billing | Not Zoho-mapped in either direction today, and per `INVOICE_TO_SALES_ORDER_MIGRATION_PLAN.md`, **planned for removal** — payment tracking is moving onto `sales_orders` |
| `customer_targets` | Sales targets per customer/period (feeds Customer Health) | **Reconsidered — recommend adding to Track B scope.** "No Zoho module exists" isn't actually a reason to exclude (same situation as `gstin`/`dealer_potential`, which *are* getting custom fields) — the real question is whether reps work inside Zoho day-to-day, in which case seeing "this account is at 60% of its quarterly target" on the Account record is standard, useful CRM context. Proposed: custom `Target Quantity`/`Target Revenue`/period fields on Accounts. |
| `stock_movements` | Inventory ledger (every stock in/out) | Deliberately **excluded** per `ZOHO_CRM_SPECIFICATION.md` §3.6 — too granular for CRM. **Confirmed still correct** — reps need "is this in stock" (via `Item.stock_quantity`→`Quantity in Stock`, once Track B for Items exists) and "what did the customer receive" (via Sales Order sync), not a raw movement ledger. |
| `vendor_item_terms` | Per-vendor pricing/lead-time terms for an item | Deliberately **excluded** per the same spec — purely operational. **Confirmed still correct** — procurement works only in the app, never in Zoho's PO module, so there's no user who'd benefit from seeing vendor pricing/lead-time terms inside Zoho. |
| `users` | App accounts (reps/admins) | Used **read-only** to attribute Zoho record owners by email match — never created/synced as Zoho records themselves |

### AI/scoring tables — never touch Zoho, by design

| Table | What it's for |
|---|---|
| `lead_scores` | Snapshot history of every Lead Scoring computation |
| `customer_health_scores` | Snapshot history of every Customer Health computation |
| `effort_efficiency_scores` | Snapshot history of every rep's Effort/Efficiency computation |
| `visit_priority_scores` | Snapshot history of every Beat Planning computation |
| `scoring_configs` | Versioned weight/band configs for all 4 engines |

Per `Intelligence/CLAUDE.md`: "Scores are never pushed back to Zoho" — these are pure outputs of the AI layer, computed *from* data that's partly Zoho-sourced, but the scores themselves stay internal.

### Infrastructure — not data at all

| Table | What it's for |
|---|---|
| `alembic_version` | Backend's own migration-tracking pointer |
| `alembic_version_intelligence` | Intelligence's own separate migration chain |

**Summary: of the 26 tables, only 3 are actually mapped to Zoho today** (`leads`, `sales_activities`, and indirectly `lead_stage_history`) — all one-way, Zoho→app. Everything else business-relevant is designed for Track B but unbuilt, invoices/payments are being phased out rather than mapped, and the 5 scoring tables plus 2 alembic tables were never meant to touch Zoho at all.

---

## 2. Track A (Zoho → App) — current implementation

### 2.1 Leads

Source: `ingest_service.py` `_lead_create_payload` / `_lead_update_payload` / `_add_optional_lead_fields`.

| App column (`leads` table) | Zoho field (Leads module) | Mapped today? | Notes |
|---|---|---|---|
| `contact_name` | `Full_Name` / `Last_Name` / `Company` (first non-empty) | ✅ | |
| `source` | `Lead_Source` (via `_SOURCE_MAP`) | ✅ | Unmapped Zoho values fall back to `OTHER` |
| `stage` | `Lead_Status` (via `_STATUS_MAP`) | ✅ | Unmapped Zoho values fall back to `NEW` |
| `assigned_to_user_id` | `Owner.email` → app `users.email` | ✅ | Unmatched email → record `PARKED`, never guessed |
| `source_created_at` | `Created_Time` | ✅ | |
| `phone` | `Phone` | ✅ (optional) | |
| `email` | `Email` | ✅ (optional) | |
| `state` | `State` | ✅ (optional) | |
| `city` | `City` | ✅ (optional) | |
| `customer_id` | `Converted_Account` | ❌ (field exists, not pulled — see §4) | Confirmed via All-Fields export: a direct `Converted Account` field exists on Leads, separate from `Converted Deal`. This is a **better** path to `customer_id` than going through the Deal — add to `fields=` list. |
| `item_id` | — | ❌ | **Confirmed absent.** No product/item reference field exists on standard Leads. See §4 |
| `quantity` | — | ❌ | **Confirmed absent.** See §4 |
| `estimated_budget` | — | ❌ | **Confirmed absent.** Closest standard field is `Annual_Revenue` (company-level, not deal-level) — not a real substitute. See §4 |
| `dealer_potential` | — | ❌ | **Confirmed absent.** `Rating` (Hot/Warm/Cold-style field) exists but maps to lead quality generally, not dealer potential specifically — could be repurposed but isn't a clean fit. See §4 |
| `required_by_date` | — | ❌ | **Confirmed absent.** See §4 |
| `district` | — | ❌ | **Confirmed absent** — Zoho's structured Address has Street/City/State/Zip/Country but **no district field**; India-specific subdivision isn't a native Zoho concept. See §4 |
| `pincode` | `Zip_Code` (shown as "Address - Zip / Postal Code") | ❌ (field exists, not pulled) | **Field exists and is mapped to nothing today** — simple fix, add `Zip_Code` to the `fields=` list. |
| `won_value` | `Amount` (via linked Deal, see §2.3) | ✅ (indirect) | Only set once the linked Deal is Closed-Won |
| `won_at` | `Closing_Date` (via linked Deal) | ✅ (indirect) | |
| `lost_at`, `lost_reason` | `Reason_For_Loss` exists on **Deals**, not Leads | ❌ | No direct Lead-side lost-reason field; would need the same Deal-linkage pattern as won_value/won_at |
| `notes` | `Description` | ❌ | Field exists, not currently pulled |

`fields=` param actually sent to Zoho today: `id,Owner,Full_Name,Last_Name,Company,Lead_Source,Lead_Status,Created_Time,Phone,Email,State,City,Converted_Deal`.

**Confirmed-existing Lead fields not currently pulled at all** (from the All-Fields export, beyond what's analyzed above): `Title`, `Salutation`, `Fax`, `Mobile`, `Website`, `Industry`, `No_of_Employees`, `Annual_Revenue`, `Rating`, `Skype_ID`, `Secondary_Email`, `Twitter`, `Converted_Contact`, `Is_Converted`, plus the structured address sub-fields (`Street`, `Zip_Code`) beyond `State`/`City`. None of these are currently needed by any scoring engine, so leaving them unpulled is a deliberate, reasonable choice — not a gap.

### 2.2 Activities (Calls / Events / Tasks → `sales_activities`)

| App column | Calls | Events | Tasks |
|---|---|---|---|
| `type` | hard-coded `CALL` | `VISIT` if `Location` set, else `MEETING` | hard-coded `FOLLOW_UP` |
| `rep_user_id` | `Owner.email` → app user | same | same |
| `lead_id` | resolved via `Who_Id`/`What_Id` + `$se_module == "Leads"` | same | same |
| `occurred_at` | `Call_Start_Time` | `Start_DateTime` | `Created_Time` or `Due_Date` |
| `duration_minutes` | `Call_Duration_in_seconds` ÷ 60 (only if ≥ 60s) | computed from `Start_DateTime`/`End_DateTime` | not set |
| `customer_id` | ❌ never set | ❌ never set | ❌ never set |
| `remarks` | ❌ not pulled | ❌ not pulled | ❌ not pulled |

**Known structural gap:** any Zoho Call/Event/Task whose `$se_module` is **not** `"Leads"` (e.g. logged against an Account/Contact instead) is parked with `"no subject lead"` and silently dropped — there is currently no path for activities tied to a Customer/Account rather than a Lead, because `customer_id` is never populated. This matters for Customer Health's engagement/communication-gap inputs, which read from `SalesActivity.customer_id` — Zoho-sourced activity **cannot** currently feed Customer Health at all, only Lead-side engines.

### 2.3 Deals (Closed-Won only → backfills Lead)

| App column (`leads` table) | Zoho field (Deals module) | Mapped today? |
|---|---|---|
| `won_value` | `Amount` | ✅ (only if `Stage == "Closed Won"` and `Amount > 0`) |
| `won_at` | `Closing_Date` | ✅ (same condition) |
| (link) | `Converted_Deal` on the originating Lead → `crm_mappings` | ✅ |

Every other Deal field (`Stage` values other than Closed Won, pipeline, probability, etc.) is ignored entirely — Deals are only ever consulted as a backfill source for an already-ingested Lead.

---

## 3. Track B (App → Zoho) — designed, not built

A full design already exists in `ZOHO_CRM_SPECIFICATION.md` §3 for Customer→Account, Vendor→Vendor, Item→Product, SalesOrder→Sales Order, PurchaseOrder→Purchase Order, including a custom-fields checklist (§6.1: `Inventory ID`, `GSTIN`, `Reorder Threshold`, `Inventory URL` per module).

**Caveat found while writing this doc:** that spec references app field names (`customers.name`, `customers.billing_address`, `items.default_unit_price`) that **do not match the current live model** — the actual `Customer` model has `company_name` (not `name`) and a single `address: Text` field (not a structured `billing_address`), and `Item` has `unit_price` (not `default_unit_price`). Before implementing Track B, that spec's field references need to be reconciled against the real models, the same way this document reconciles Track A.

Also previously assumed-but-disproven: Track B does **not** require a paid Zoho edition — a live write test (`POST /Accounts`) against the current org succeeded with `201 Created`. The deferral is a scope/priority decision, not a platform limitation.

### 3.1 Confirmed Zoho-side shape (from All-Fields exports, 2026-06-25)

- **Accounts**: has structured `Billing Address` *and* `Shipping Address` (each with Street/City/State/Zip/Country/Lat/Long as separate fields) — richer than the app's single `Customer.address: Text` blob. Mapping Customer→Account will need to either parse `address` into parts or accept everything landing in one Zoho address sub-field. No `GSTIN` or `Inventory ID` custom field exists yet — confirmed absent, matches the spec's plan to add them.
- **Products**: confirmed fields include `Unit Price`, `Usage Unit`, `Quantity in Stock`, `Reorder Level` — close to `Item.unit_price`/`unit_of_measure`/`stock_quantity`/`reorder_threshold`. No `Inventory ID` custom field yet.
- **Sales_Orders module already exists in this Zoho org** with `SO Number`, `Account Name`, `Status`, billing/shipping address sub-fields, `Sub Total`/`Grand Total` — matches the shape `ZOHO_CRM_SPECIFICATION.md` §3.4 assumes. No `Inventory ID`/`Inventory URL` custom field yet.
- **Purchase_Orders module already exists** too, same shape as Sales Orders, linked to `Vendor Name` instead of `Account Name`.

---

## 4. Existing app columns with no Zoho counterpart yet

These columns already exist in the schema (per §0, no DB work needed) but have no Zoho field feeding them today. This is the real mapping work — for each row, decide "add a Zoho custom field" vs. "accept as app-only, never synced."

All rows below are now **confirmed** against the All-Fields export (2026-06-25), not proposals.

| Entity | App column (already exists) | Zoho status |
|---|---|---|
| Lead | `quantity`, `item_id` | **Confirmed: no standard Zoho field exists.** Needs a new custom field on Leads (and ideally a lookup to Products for `item_id`) |
| Lead | `estimated_budget` | **Confirmed absent.** Needs a custom currency field on Leads |
| Lead | `dealer_potential` | **Confirmed absent.** Needs a custom picklist field on Leads |
| Lead | `required_by_date` | **Confirmed absent.** Needs a custom date field on Leads |
| Lead | `district` | **Confirmed absent** — not a native Zoho concept (no district anywhere in the structured Address block). Needs a custom field if district-level granularity matters, or accept `state`+`city` only |
| Lead | `pincode` | **Confirmed present** as `Zip_Code` — no custom field needed, just add it to the ingest `fields=` list |
| Lead | `customer_id` | **Confirmed present** as `Converted_Account` — no custom field needed, just add it to the ingest `fields=` list (better than the current Deal-based workaround) |
| Customer | `gstin` | **Confirmed absent** on Accounts — needs custom field for Track B (per existing `ZOHO_CRM_SPECIFICATION.md` §6.1 plan) |
| Customer | `customer_code` | **Confirmed absent** — `Account Number` exists but is a different Zoho-managed concept; would still want a dedicated `Inventory ID` custom field (per existing plan) for clean round-tripping |
| Customer | `is_privileged`, `competitive_risk_level` | **Confirmed absent** — both need new custom fields on Accounts for Track B |
| Item | (whole entity) | Products module **confirmed to exist** with a compatible shape (`Unit Price`, `Usage Unit`, `Quantity in Stock`, `Reorder Level`) — Track B for Items is more feasible than previously known, just needs the `Inventory ID` custom field per the existing plan |

---

## 5. Data population gaps (unrelated to Zoho mapping — won't be fixed by it)

These are columns that exist and are correctly designed, but are frequently
`NULL`/unpopulated for real records, independent of any Zoho sync. No amount
of field mapping work addresses these — they need to be populated through
normal inventory/finance workflows (or seeded for testing).

- **`Item.standard_cost`** — nullable, often empty (confirmed directly on "test company"'s items during this session). Feeds Customer Health margin quality and Lead Scoring product margin; both fall back to defaults when this is `NULL`.
- **`CustomerTarget`** — often no row exists at all for a given customer/period. Feeds Customer Health volume achievement; falls back to default (50) without it.
- **`Invoice` / `Payment`** — often no invoices exist for shipped orders. Feeds Customer Health DSO and payment-risk components; both fall back to defaults without them.

---

## 6. Open items before any further sync code is written

1. ~~Verify the §4 "needs a custom field" rows against the live Zoho org~~ — **done**, via the All-Fields export. Two quick wins identified: add `Zip_Code` and `Converted_Account` to the Lead `fields=` list — both already exist, no custom field needed, no code risk.
2. Decide, per remaining §4 row (`quantity`, `item_id`, `estimated_budget`, `dealer_potential`, `required_by_date`, `district`, and the Customer/Account fields), whether to add the Zoho custom field or accept app-only.
3. Reconcile `ZOHO_CRM_SPECIFICATION.md` §3's stale field names (`customers.name`, `billing_address`, `items.default_unit_price`) against the real model columns before implementing Track B.
4. Decide whether Customer-linked (non-Lead) Zoho activities should ever be ingested — currently structurally impossible (§2.2).
5. Populate the §5 data gaps through normal data-entry/seeding — independent of any of the above.
6. Re-export **Vendors** and **Users** with "All Fields" once Zoho's daily export limit resets, to close out the last two unconfirmed sections.
