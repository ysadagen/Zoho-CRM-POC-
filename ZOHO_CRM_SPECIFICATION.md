# Zoho CRM — System Specification (Phase 1)

**Audience:** CRM administrators configuring Zoho, sales/operations team
using Zoho day-to-day, and engineers building the Integration Layer.
**Counterpart:** `Frontend/UI_SPECIFICATION.md` (the inventory web app).
**Architecture:** `README.md` (the project root).
**Sequencing:** `ZOHO_INTEGRATION_EXECUTION_PLAN.md` (the cross-service plan).

> **⚠️ Scope note (current engagement) — read first.** This document specifies the
> **push** integration (inventory app → Zoho), which the cross-service plan calls
> **Track B**. For the present setup (Zoho **Free**, 3 users, rep-productivity
> goal), **Track A — ingest (Zoho → app, feeding the AI effort/efficiency
> engine) — is built first**, and this push track is **deferred**: Zoho Free
> lacks the Sales Order / Purchase Order / Product modules, so push needs a paid
> edition. This doc stays authoritative for the **field mapping and push
> behaviour** once Track B is unblocked; for sequencing and the ingest design,
> `ZOHO_INTEGRATION_EXECUTION_PLAN.md` governs.

This document answers two questions:

1. **What will exist in Zoho CRM as a result of the integration?**
2. **What capabilities does the CRM team get from Zoho — for free, without us
   building anything?**

---

## 1. The mental model (one minute)

The inventory web app is the **source of truth for stock and operational
records**. Zoho CRM is the **relationship and visibility layer**.

| Lives in inventory app | Lives in Zoho CRM |
|---|---|
| Stock quantities, items, vendor terms | Customer / vendor master records (mirrored) |
| Sales orders, purchase orders (creation, fulfilment, stock impact) | Sales orders, purchase orders (mirrored for relationship history) |
| Stock movements (the append-only ledger) | — |
| Receipts, audit | Tasks, calls, meetings, notes, reminders against customers/vendors |
| Pricing, terms | Dashboards and reports across customers/vendors |
| Source of truth for **what happened** | Source of truth for **the relationship around what happened** |

**Sync direction for the push (Track B):** **one-way** — inventory app → Zoho
CRM. Zoho is not the source of truth for any business state. Changes made in
Zoho do **not** flow back into inventory.

> **Track A (ingest), built first, is also one-way — the other direction:** Zoho
> **Leads / Activities / Deals** are pulled into the app to feed the AI
> productivity engine. This is additive and **app-canonical** (the app stays the
> system of record; the AI scores app-owned data) and does **not** make Zoho a
> source of truth for any inventory state. See `ZOHO_INTEGRATION_EXECUTION_PLAN.md`
> §4.

---

## 2. Which Zoho CRM modules are in use

Zoho ships with many modules. We deliberately use a small subset.

| Zoho module | What we put in it | Maps to |uv run pytest -q
...                                                                                                                                                                                                  [100%]
3 passed in 0.36s
uv run ruff check
All checks passed!
uv run ruff check
All checks passed!
uv run mypy src
Success: no issues found in 18 source files
|---|---|---|
| **Accounts** | Companies the business sells to | `customers` table in inventory_db |
| **Vendors** | Companies the business buys from | `vendors` table |
| **Products** | Raw materials and finished products | `items` table |
| **Sales Orders** | Each sale, with line items | `sales_orders` + `sales_order_items` |
| **Purchase Orders** | Each purchase, with line items | `purchase_orders` + `purchase_order_items` |
| **Tasks / Calls / Meetings / Notes** | CRM team's relationship activity | — *(created and lived in Zoho only)* |

Modules we **do not** use in Phase 1:

- Leads (we're not running a lead-gen funnel)
- Deals / Pipelines (we're not tracking opportunities)
- Quotes, Invoices (handled outside Zoho; possibly later phases)
- Cases, Solutions (no support workflow yet)
- Campaigns (no marketing automation)
- Price Books (single-tier pricing is enough for Phase 1)

If a module is not listed in the first table, **do not configure it** for
this POC.

---

## 3. What gets synced — record by record

For each entity, the inventory app pushes a record to Zoho the **first time**
that entity is created locally, then **updates** that Zoho record on
subsequent local changes.

The Integration Layer keeps a mapping (`crm_mappings` table) of
`local_id ↔ zoho_id` per entity type, so every later update knows which
Zoho record to touch.

### 3.1 Customer → **Account**

| Zoho field | Source | Notes |
|---|---|---|
| Account Name | `customers.name` | Required |
| Email | `customers.email` | Optional |
| Phone | `customers.phone` | Optional |
| Billing Address (Street/City/State/Postal/Country) | `customers.billing_address` | Parsed if structured, or one free-text field |
| Industry | hard-coded `"Manufacturing — Customer"` | Lets reports filter our records out from any other Zoho data |
| Description | `customers.notes` | Optional |
| **Custom field:** `Inventory ID` | `customers.id` (UUID) | Read-only in Zoho; used for traceability |
| **Custom field:** `GSTIN` | `customers.gstin` | Indian GST registration number |
| Account Owner | mapped from inventory user (Phase 2) | Phase 1: a single service account |

### 3.2 Vendor → **Vendor**

| Zoho field | Source | Notes |
|---|---|---|
| Vendor Name | `vendors.name` | Required |
| Email | `vendors.email` |  |
| Phone | `vendors.phone` |  |
| Address fields | `vendors.address` |  |
| Category | hard-coded `"Manufacturing — Raw Material Supplier"` |  |
| Description | `vendors.notes` |  |
| **Custom field:** `Inventory ID` | `vendors.id` |  |
| **Custom field:** `GSTIN` | `vendors.gstin` |  |

### 3.3 Item → **Product**

Optional for Phase 1 — only worth syncing if the CRM team wants to see
product details on Zoho sales/purchase order line items.

| Zoho field | Source | Notes |
|---|---|---|
| Product Name | `items.name` | Required |
| Product Code | `items.sku` |  |
| Product Category | `items.type` (RAW / FINISHED) |  |
| Unit Price | `items.default_unit_price` |  |
| Usage Unit | `items.unit_of_measure` | kg, pcs, L, etc. |
| **Custom field:** `Inventory ID` | `items.id` |  |
| **Custom field:** `Reorder Threshold` | `items.reorder_threshold` | Visible only; Zoho does **not** drive stock decisions |

**Note:** Zoho's Products module also has a `Qty in Stock` field. We **do not** sync this. Stock is owned by the inventory app and would be misleading inside Zoho.

### 3.4 Sales Order → **Sales Order**

| Zoho field | Source | Notes |
|---|---|---|
| Subject | `sales_orders.so_number` (e.g. `SO-1042`) |  |
| Account Name | resolved via `crm_mappings` from the local customer | Links to the Zoho Account |
| Status | `sales_orders.status` (DRAFT / CONFIRMED / CANCELLED) |  |
| Order Date | `sales_orders.order_date` |  |
| Sub Total / Grand Total | computed from line items |  |
| Description | `sales_orders.notes` |  |
| **Custom field:** `Inventory ID` | `sales_orders.id` |  |
| **Custom field:** `Inventory URL` | deep-link back into the web app | Lets a CRM user jump straight to the record |
| Line items (Products subform) | `sales_order_items` rows | Each: Product (resolved via mapping), Qty, Unit Price, List Price, Discount = 0 |

### 3.5 Purchase Order → **Purchase Order**

Same shape as Sales Order, but linked to a Vendor and using
`purchase_orders` data. Status values: DRAFT / RECEIVED.

### 3.6 What is **not** synced

- **Stock movements** (`stock_movements` ledger) — too detailed for CRM, and
  CRM users don't need the audit trail. They see net positions via SO/PO
  history.
- **`vendor_item_terms`** — purely an operational concern.
- **Internal users** (the app's `users` table) — not synced as Zoho users.

---

## 4. Sync mechanics (so the CRM team understands what to expect)

These properties matter because they shape the user experience in Zoho.

| Property | Behaviour |
|---|---|
| **Direction** | One-way: inventory app → Zoho. Changes in Zoho do not flow back. |
| **Latency** | Near-real-time. The Integration Layer is called immediately after a successful local commit. Typical end-to-end < 5 s. |
| **Failure handling** | If Zoho is unreachable or returns an error, the local operation is **not rolled back**. The failure is logged in `sync_logs` and a retry runs in the background. Inventory ops never block on Zoho. |
| **Idempotency** | Retries are safe. Every sync request carries an `Idempotency-Key`; duplicate requests do not create duplicate Zoho records. |
| **Record updates** | The same Zoho record is reused for every update — no proliferation of duplicate records. |
| **Manual edits in Zoho** | Are **not** overwritten on every sync — we update only the fields the inventory app owns. Free-text fields like Notes added in Zoho survive. *(Exact list of owned-fields confirmed in §3 above.)* |
| **Deletes** | If a customer/vendor/order is deleted in the inventory app (Phase 2+), the corresponding Zoho record is **archived/inactive**, not hard-deleted, so history is preserved. Phase 1 does not support deletes. |

---

## 5. What the CRM team gets — for free — from Zoho

The reason for using Zoho at all is that it gives us a lot of capability
without us building any of it. Here's what the operations / sales team can
do in Zoho **once records start syncing**:

### 5.1 Per-record activity timeline

Open any **Account (customer)** or **Vendor** in Zoho. You see:

- A timeline of every related **Sales Order / Purchase Order**.
- Every **Call, Meeting, Task, Note, Email** the team has logged against
  that record.
- Created/modified history of the record itself.

This is the relationship view that the inventory app deliberately does not
offer.

### 5.2 Activities the team can log against any customer/vendor

| Activity | What it captures |
|---|---|
| **Task** | A to-do with due date, owner, priority. Reminders fire via email/in-app/mobile push. |
| **Call** | Inbound or outbound call log, duration, outcome, notes. |
| **Meeting** | Scheduled or past meeting with participants and notes. |
| **Note** | Free-text note attached to the record (with attachments). |
| **Email** | Integrated email — sent emails are auto-logged against the customer. Inbound emails too, if mailbox is connected. |

### 5.3 Reminders and follow-ups

Tasks have due dates and reminders. Zoho sends an email / mobile push when a
task is due. Use this for: *"Call XYZ Industries next Friday about the
re-order"* or *"Vendor invoice follow-up — Monday."*

### 5.4 Reports & dashboards (out-of-the-box)

Zoho includes pre-built reports plus a drag-and-drop report builder.
Useful Phase-1 dashboards include:

- Top customers by revenue (last 30 / 90 / 365 days)
- Top vendors by spend
- Sales orders by status / by month
- Purchase orders pending receipt > N days
- Customer accounts created this month
- Activity load by user (sales rep workload)

These need ~30 minutes of configuration per dashboard — no code.

### 5.5 Email integration

Connect each team member's email (Gmail / Outlook / Zoho Mail). Inbound and
outbound emails to a customer's known address are automatically logged on
the Account record. The thread becomes part of the relationship timeline.

### 5.6 Workflow rules (no-code automation)

The CRM admin can configure rules like:

- *"When a Sales Order is created with total > ₹5,00,000, assign it to the
  senior sales manager."*
- *"When a Vendor record has no activity in 90 days, create a task to
  check in."*
- *"When a Purchase Order is marked Received, send the vendor a thank-you
  email."*

All point-and-click, no engineering.

### 5.7 Approvals

For Phase 1 probably not needed, but available: multi-step approval flows
(e.g. "POs over ₹10L need owner approval").

### 5.8 Mobile app

Zoho CRM ships native iOS + Android apps. Field sales can pull up customer
records, log calls, and create tasks from anywhere.

### 5.9 Search & filters

Global search across all modules. Per-module filters and saved views.
Useful for: *"Show me all customers in Karnataka with revenue > ₹1L this
year."*

### 5.10 User access controls

Roles, profiles, data-sharing rules. We won't configure deep RBAC for the
POC, but it's there when you need it.

---

## 6. What we will configure in Zoho before go-live

This is the Zoho-admin checklist, not the engineering checklist.

### 6.1 Custom fields

Per §3, add these custom fields to the corresponding modules:

| Module | Custom field | Type | Notes |
|---|---|---|---|
| Accounts | `Inventory ID` | Single-line text, read-only | Mark as "lookup key" for the sync |
| Accounts | `GSTIN` | Single-line text | Validate format |
| Vendors | `Inventory ID` | Single-line text, read-only |  |
| Vendors | `GSTIN` | Single-line text |  |
| Products | `Inventory ID` | Single-line text, read-only |  |
| Products | `Reorder Threshold` | Number | Display only |
| Sales Orders | `Inventory ID`, `Inventory URL` | Text + URL |  |
| Purchase Orders | `Inventory ID`, `Inventory URL` | Text + URL |  |

### 6.2 Layouts

Reorder fields on each module's detail page so the CRM team sees the
sync-relevant fields first:

- **Accounts:** Account Name • GSTIN • Phone/Email • Billing Address • Inventory ID (small, bottom)
- **Sales Orders:** SO Subject • Account • Status • Line Items • Inventory URL (button)
- Same pattern for Vendors and Purchase Orders.

### 6.3 Workflow rules (optional, Phase-1 nice-to-have)

Two rules worth setting up early so the CRM team feels the value:

1. *"When a new Account is created via API, assign a task to the sales rep
   to make a welcome call within 2 working days."*
2. *"When a Sales Order is created, post a notification to the
   `#sales-orders` Slack/Teams channel (via Zoho's webhooks)."* — only if
   Slack/Teams is in use.

### 6.4 Dashboards

Build the five dashboards listed in §5.4. Share them with the operations
team's role.

### 6.5 Authentication

The integration uses a dedicated **OAuth Self Client** in the Zoho API
Console:

- Scope: `ZohoCRM.modules.ALL`, `ZohoCRM.users.READ`.
- Refresh token issued once, stored in `integration_db.zoho_tokens`.
- A dedicated Zoho user (e.g. `integration-bot@<your-domain>`) is the owner
  of all API-created records. This keeps the audit trail clean — every
  sales rep can see *"created by integration-bot"* and know it came from
  the inventory app, not from a colleague.

---

## 7. What we will **not** configure or use (Phase 1)

Explicitly out of scope so nobody spends an afternoon on it:

- **Two-way sync.** No Zoho-side change flows back into inventory. A change
  made in Zoho stays in Zoho.
- **Zoho as the order-creation UI.** Sales orders are created in the
  inventory app, not in Zoho. The Zoho Sales Orders module is read-only for
  the team (visible, not actionable).
- **Zoho Inventory module.** Despite the name, that's a separate Zoho
  product — we are using **Zoho CRM** only.
- **Zoho Books / accounting / invoicing.** Out of scope.
- **Lead/Deal pipelines.** Out of scope.
- **Marketing campaigns / mass email.** Out of scope.
- **Workflow rules that mutate inventory data** (e.g. "auto-update stock"
  from Zoho). Inventory state is owned exclusively by the inventory app.
- **Webhooks from Zoho into the inventory app.** Phase 1 architecture has
  the webhook endpoint **stubbed** in the Integration Layer, but we do not
  drive any business behaviour from Zoho events yet.
- **Zoho's Stock / Inventory built-in fields.** Ignored — would confuse
  users about where stock truly lives.

---

## 8. Day-in-the-life — what the team will actually do in Zoho

Five realistic scenarios that the configuration should support out of the box.

1. **Sales rep prepping for a customer visit**
   *Opens Zoho mobile → searches "ABC Industries" → sees the Account page →
   scans the last 6 sales orders, last call log, open tasks, the GSTIN, and
   the address → leaves a Note: "Quoted them on 500 units of Large bottles
   during the visit."*

2. **Operations manager spotting a slow follow-up**
   *Opens the saved view "Vendors with no activity in 90 days" → picks one
   → assigns a task to the buyer to call them.*

3. **Owner reviewing the month**
   *Opens the "Top customers by revenue — this month" dashboard → drills
   into the top customer → sees every order, every call, every note from
   the month.*

4. **Sales person creating a reminder**
   *Opens an Account → "+ Task" → "Follow up on bulk order quotation, due
   Friday" → assigned to themselves → gets a notification on Friday
   morning.*

5. **Admin investigating a duplicate**
   *Search returns two Accounts named "XYZ Traders" → opens both → notices
   one has a populated `Inventory ID` field and one doesn't → confirms the
   one without it is a duplicate created manually before the sync ran →
   merges them inside Zoho's merge UI.*

---

## 9. Open questions to resolve before go-live

The Zoho admin should resolve these with the operations lead:

1. **Indian GST vs. other tax regimes** — confirm the `GSTIN` field name
   and any regional tax fields needed.
2. **Currency** — single currency assumed. Symbol and position should
   match the inventory app.
3. **Time zone** — what's the org's primary TZ? Records' "created at"
   should display in that TZ in Zoho's UI.
4. **Record owner** — Phase 1 plan is a single `integration-bot` user owns
   every synced record. Phase 2 might map the inventory app user to a
   Zoho user. Confirm OK.
5. **Vendors module visibility** — by default Zoho hides the Vendors module
   from most users. Confirm which Zoho roles need it enabled.
6. **Sales Order numbering** — the inventory app generates `SO-####`
   numbers. Zoho also has its own auto-numbering. We will **disable** Zoho's
   auto-numbering and use ours, so numbers match across both systems.
   Confirm OK.
7. **Email integration** — which team members will connect their mailbox?
8. **Notifications** — which roles should get email/push when a new SO
   creates? When a PO is marked received?

---

## 10. Success criteria for Phase 1 (Zoho side)

The integration is "done" when, after a day of normal inventory app use:

- Every customer created in the inventory app appears as an Account in
  Zoho within seconds, with all mapped fields populated correctly.
- Every vendor likewise appears as a Vendor record.
- Every sales order and purchase order appears under the correct account
  / vendor with full line items, status, and totals.
- A CRM user opening any Account sees the timeline of related orders.
- The sales team can add Tasks, Notes, and Activities against Accounts and
  Vendors and they persist (purely Zoho-side).
- Failed syncs are visible to the admin via `sync_logs` (Phase 1) or a
  Zoho-side notification (Phase 2).

If any of these don't hold, Phase 1 is not done.

---

## 11. Related documents

- `README.md` — full system architecture and business scope.
- `Frontend/UI_SPECIFICATION.md` — the inventory web app the operations team uses.
- `Integration Layer/CLAUDE.md` — the engineering contract for the service
  doing the sync.
- `Backend/CLAUDE.md` — the engineering contract for the inventory backend.
