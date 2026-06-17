# Inventory Application — UI Specification (Phase 1)

**Audience:** UI/UX designers building wireframes and visual designs in Figma.
**Status:** Source of truth for what screens, fields, and behaviours the
Phase 1 POC needs. Anything not listed here is out of scope.
**Related:** The application architecture lives in `../README.md`. CRM
features (history, relationship tracking, tasks, reminders) live in **Zoho
CRM**, not in this UI. Design for **operations and inventory workflows**,
not for relationship management.

---

## 1. Product context (1-minute orientation)

The user is a manufacturing business that:

- Buys **raw materials** (e.g. Raw Plastic, Raw Steel) from vendors.
- Manufactures **finished products** (e.g. water bottles in Small / Medium / Large).
- Sells finished products to customers.

The application is the **source of truth for stock**. Every quantity change
is recorded as a stock movement and shown in an audit ledger. Customer and
vendor relationship history lives in Zoho CRM and is **not** part of this UI.

This is a back-office tool, not a consumer product. Visual direction:
**clean, data-dense, professional, calm.** Think Linear / Stripe Dashboard /
Notion — not Shopify or Instagram.

---

## 2. Users

Single role for Phase 1: an authenticated **operations user** who can
perform every action. Role-based access (admin vs. clerk vs. read-only)
is a later phase — design for one role now, but don't paint yourself
into a corner.

Typical day-in-the-life tasks:

1. Check what stock is running low.
2. Create a sales order against current stock.
3. Receive a purchase order and confirm stock has gone up.
4. Investigate why a stock number looks wrong (use the audit ledger).
5. Add a new item, customer, or vendor.

---

## 3. Information architecture

Eight top-level pages. The same nav on every screen.

```
[Dashboard]  [Items]  [Sales Orders]  [Purchase Orders]
[Customers]  [Vendors]  [Stock Movements]  [Settings]
```

Plus an **Auth area** (login, change password) which uses a minimal layout
without the main nav.

---

## 4. Global UI elements (present on every authenticated screen)

### 4.1 Top header

| Region | Contents |
|---|---|
| Left | App logo / name |
| Centre | (Phase 2) Global search box |
| Right | Environment badge (`dev` / `staging` chip; hidden in prod) • Notifications bell (Phase 2) • User menu (avatar → name, role, "Profile", "Change password", "Log out") |

### 4.2 Left side navigation (or top tabs — designer's choice)

- Eight items listed in §3.
- Each item: icon + label.
- Active item highlighted.
- Collapsible to icons-only on narrow screens (≥ 1024 px).

### 4.3 Page header (inside each page)

| Region | Contents |
|---|---|
| Left | Breadcrumb (e.g. Items › Raw Plastic) + page title |
| Right | Primary action button(s) (e.g. "+ New Sales Order") |

### 4.4 Footer

Minimal: version number, environment, "© Company". No marketing links.

---

## 5. Design system primitives (build these first as components)

Designing these once lets every page reuse them.

### 5.1 Buttons

- **Primary** (filled, brand colour) — for the *one* main action per page (e.g. "Create", "Save", "Receive").
- **Secondary** (outline) — for non-destructive alternatives (e.g. "Cancel", "Back").
- **Destructive** (red) — for delete/cancel-order/wipe-style actions. Always confirmed via modal.
- **Ghost / link** — for table row actions ("View", "Edit").
- **Icon-only** — for compact toolbars, with tooltip.

Sizes: small (in tables), default (forms), large (hero CTAs). Disabled and loading states required for each.

### 5.2 Status badges / chips

A consistent colour palette across the app. Examples:

| Badge | Used for |
|---|---|
| `RAW` (blue) / `FINISHED` (purple) | Item type |
| `OK` (green) / `LOW` (amber) / `OUT` (red) | Stock status |
| `DRAFT` (grey) / `RECEIVED` (green) | Purchase order status |
| `DRAFT` (grey) / `CONFIRMED` (green) / `CANCELLED` (red) | Sales order status |
| `IN` (green ↑) / `OUT` (red ↓) | Stock movement direction |
| `Synced` (green) / `Pending` (amber) / `Failed` (red) | Zoho CRM sync status |

### 5.3 Forms

- Required-field indicator (`*` or asterisk colour).
- Inline error message under each field (no modal alerts for validation).
- Help text under field labels where useful.
- Sticky footer with "Cancel" + "Save" on long forms.
- Autosave is **not** required for Phase 1 — explicit Save.

### 5.4 Data tables

The single most-used component. It must support:

- Column sorting (click header).
- Filters in a row above the table.
- Server-driven pagination (page size 25 by default; selector for 25 / 50 / 100).
- Row hover state.
- Row click → opens detail view.
- Action buttons on the right of each row (View, Edit; "..." menu if more).
- Empty state (see §5.7).
- Loading skeleton rows during fetch.
- Sticky header on scroll for long tables.

### 5.5 Modals

- Centred, max 600 px wide.
- Title, body, footer with action buttons.
- Used for: confirmations of stock-changing actions, quick "Add new" forms invoked from autocompletes (e.g. "+ Create customer" inline on the SO form).

### 5.6 Toasts

- Success (green), info (blue), warning (amber), error (red).
- Top-right corner, auto-dismiss after ~4 s.
- Show the **request id** on errors (e.g. *"Failed to save. ID: abc-123-def"*) — this is how ops and developers correlate a user complaint to a server log line. **Important — do not skip this.**

### 5.7 Empty states

Every list view, every tab. Components needed:

- Friendly illustration or icon.
- One-line headline ("No purchase orders yet").
- One-line subtext explaining when this list fills up.
- Primary CTA button (e.g. "+ New Purchase Order").

### 5.8 Loading + error states

- **Loading:** skeleton placeholders for tables and cards (not blank screens, not spinners).
- **Error:** full-page error card with retry button + the request id.

---

## 6. Page-by-page specifications

For each page below: **purpose**, **layout**, **fields**, **actions**,
**states**.

---

### 6.1 Login

**Purpose:** Authenticate an operations user.

**Layout:** Single centred card, no main nav.

**Fields:**
- Email (required, validated)
- Password (required, masked, with show/hide toggle)
- "Remember me" checkbox (Phase 2 — optional)

**Actions:**
- **Primary:** "Log in" button (loading state).
- Link: "Forgot password?" (Phase 2 — link to a placeholder)

**States:** loading, success → redirect to Dashboard, error → inline message under password field ("Invalid email or password").

---

### 6.2 Dashboard

**Purpose:** "What needs my attention today?" — surface alerts and quick actions.

**Layout:** A grid of cards (4 columns desktop, 1 column mobile).

**Cards / tiles:**

1. **Low-stock alerts**
   - List of items at or below their reorder threshold.
   - Each row: SKU, name, current stock vs. threshold, "View item" link.
   - Empty state: "All items are above their reorder thresholds."

2. **Today's sales orders**
   - Count of SOs created today.
   - Total revenue today.
   - "View all" link.

3. **Open purchase orders**
   - Count of POs in `DRAFT`.
   - Total expected qty.
   - "View all" link.

4. **Recent stock movements**
   - Last 10 movements, compact list: time, item, direction badge, qty.
   - "View ledger" link.

5. **Zoho sync health** (small banner if there are failed syncs)
   - Count of failed syncs.
   - "View details" → opens sync log (Phase 2).

**Top-right actions on the dashboard:** "+ New Sales Order", "+ New Purchase Order".

---

### 6.3 Items

The catalogue of raw materials and finished products. Single table, with a
`type` column distinguishing them.

#### 6.3.1 Items — list

**Filters row:**
- Type: All / Raw / Finished (segmented control)
- Status: All / OK / Low / Out (segmented control)
- Text search: SKU or name
- "Clear filters"

**Table columns:**
| Column | Notes |
|---|---|
| SKU | Monospaced font |
| Name | Bold, clickable → detail |
| Type | Badge: RAW / FINISHED |
| Unit | kg / pcs / L |
| Current stock | Right-aligned, numeric |
| Reorder threshold | Right-aligned, numeric, grey if empty |
| Status | Badge: OK / LOW / OUT |
| Actions | "View", "Edit" |

**Page header action:** "+ Add Item".

#### 6.3.2 Items — detail

**Header:**
- Item name (large)
- SKU + Type badge + Status badge
- "Edit" button (right-aligned)

**Summary row (key stats as cards):**
| Card | Value |
|---|---|
| Current stock | `123 kg` |
| Reorder threshold | `50 kg` |
| Last movement | `2 hours ago` |
| Total inbound (lifetime) | `2,400 kg` |
| Total outbound (lifetime) | `2,277 kg` |

**Tabs:**

- **Overview** — all master fields: SKU, name, description, type, unit, current stock, reorder threshold, default unit price, created/updated timestamps.
- **Movement history** — embedded stock-movement table filtered to this item; columns: timestamp, IN/OUT badge, reason, qty, balance after, reference (linked to PO/SO), user.
- **Vendors** *(raw items only)* — table of suppliers with terms (vendor name, unit price, lead time, MOQ, last PO date). Action: "+ Link vendor" → modal to attach a vendor with terms.
- **Used in** *(finished items only)* — recent sales orders that included this item.

#### 6.3.3 Items — create / edit form

| Field | Type | Required | Notes |
|---|---|---|---|
| SKU | text | ✓ | Unique, validated server-side |
| Name | text | ✓ |  |
| Description | textarea | — | Up to 500 chars |
| Type | radio | ✓ | RAW / FINISHED |
| Unit of measure | dropdown | ✓ | kg, pcs, L, m, set |
| Initial stock | number | — | Create only; defaults to 0 |
| Reorder threshold | number | — | Used for low-stock alerts |
| Default unit price | currency | — | Autofilled into SOs |

Form actions: **Cancel** • **Save**.

---

### 6.4 Sales Orders

#### 6.4.1 Sales Orders — list

**Filters:** Status (All / Draft / Confirmed / Cancelled) • Customer (autocomplete) • Date range • Text search (SO number).

**Columns:** SO number • Customer • Date • Status badge • Items count • Total amount • Sync badge • Actions (View).

**Page header action:** "+ New Sales Order".

#### 6.4.2 Sales Orders — detail

**Header:** SO number, customer link, date, status badge, total amount, "View in Zoho CRM" link (if synced).

**Body:**
- Customer block (name, email, phone — read-only summary)
- Line items table (item, qty, unit price, line total)
- Stock impact panel: list of stock movements generated by this SO, linked
- Notes
- Audit footer: created by, created at, last sync attempt, request id of last operation

**Actions:** "Cancel order" (only if status allows; destructive, confirmation required).

#### 6.4.3 Sales Orders — create form (the most important screen)

| Field | Behaviour |
|---|---|
| Customer | Autocomplete by name/email. Inline "+ Create customer" opens a modal with the customer create form (§6.5.3). |
| Order date | Date picker, defaults to today. |
| Line items table | Each row: **item picker** (autocomplete, FINISHED only) → **qty** input → **unit price** (autofilled, editable) → **line total** (computed). "+ Add row" button. Remove icon per row. |
| **Live stock indicator** | Right of qty input: green chip `12 in stock` or red chip `Only 3 available — short by 2`. Updates as qty changes. Submit is disabled if any row is short. |
| Notes | Textarea, optional. |
| Total | Computed, sticky footer. |

**Actions:** **Cancel** • **Create order**.

**On submit:**
- Server confirms stock availability and creates the SO.
- Toast: *"SO-1042 created. Stock updated."*
- Redirect to detail view.
- On insufficient stock (race condition): toast in red with the conflicting item and the option to "Refresh stock".

---

### 6.5 Customers (deliberately light — relationship work lives in Zoho)

#### 6.5.1 Customers — list

**Filters:** text search • date range.
**Columns:** Name • Email • Phone • SO count • Total revenue • Created date • Zoho sync • Actions (View, Edit).
**Page header action:** "+ Add Customer".

#### 6.5.2 Customers — detail

Two tabs:
- **Profile** — all master fields, sync status, "Open in Zoho CRM" link.
- **Sales orders** — embedded SO list filtered to this customer.

#### 6.5.3 Customers — create / edit form

| Field | Type | Required |
|---|---|---|
| Name | text | ✓ |
| Email | email | — |
| Phone | tel | — |
| Billing address | multi-line | — |
| GSTIN / Tax ID | text | — |
| Notes | textarea | — |

---

### 6.6 Vendors

Mirror of Customers, plus the **supplied items** relationship.

#### 6.6.1 Vendors — list

Same columns as Customers but with "Items supplied" count instead of revenue, and "PO count" instead of SO count.

#### 6.6.2 Vendors — detail

Three tabs:
- **Profile** — same fields as customer + contact person.
- **Items supplied** — inline-editable table (`vendor_item_terms`):
  - Columns: Item • Unit price • Lead time (days) • MOQ • Last PO date • Actions (Edit, Remove)
  - "+ Link item" button → modal to add an item with terms.
- **Purchase orders** — embedded PO list filtered to this vendor.

#### 6.6.3 Vendors — create / edit form

Same as customer + **Contact person** field.

---

### 6.7 Purchase Orders

#### 6.7.1 Purchase Orders — list

**Filters:** Status (All / Draft / Received) • Vendor • Date range • Text search.
**Columns:** PO number • Vendor • Created date • Expected delivery • Status badge • Items count • Total • Actions (View; "Receive" inline button if Draft).
**Page header action:** "+ New Purchase Order".

#### 6.7.2 Purchase Orders — detail

**Header:** PO number, vendor link, dates, status, total, "View in Zoho CRM" link (if synced), big "Receive" button (only if status is Draft).

**Body:** line items table, notes, stock impact (visible only after receive), audit footer.

#### 6.7.3 Purchase Orders — create form

| Field | Behaviour |
|---|---|
| Vendor | Autocomplete; inline "+ Create vendor". |
| Order date | Defaults to today. |
| Expected delivery date | Optional. |
| Line items | Each row: **item picker** (RAW only) → **qty** → **unit price** (autofilled from vendor's `vendor_item_terms`, editable). |
| Notes | Optional. |

**Actions:** **Cancel** • **Save as Draft**.

POs are always saved as Draft. Stock is **not** changed until "Receive".

#### 6.7.4 Receive flow (critical)

Triggered by the "Receive" button on a Draft PO.

1. Confirmation modal:
   - Title: "Receive Purchase Order PO-0042"
   - Body: a list of "+100 kg Raw Plastic, +50 kg Raw Steel" showing the delta about to be applied.
   - Footer: **Cancel** • **Confirm receive** (primary).
2. On confirm:
   - Loading state on the button.
   - On success: status flips to Received, toast *"Stock updated."*, the "Receive" button disappears, the stock-impact section appears with linked stock movements.
   - On failure (e.g. already received elsewhere): error toast with request id.

---

### 6.8 Stock Movements (the audit ledger)

The "trust" page. Read-only. Append-only — no edit, no delete.

#### 6.8.1 Stock Movements — list

**Filters:** Item (autocomplete) • Direction (All / IN / OUT) • Reason (All / Purchase / Sale / Adjustment) • Date range • User.

**Columns:**
| Column | Notes |
|---|---|
| Timestamp | Date + time, local TZ |
| Item | Linked to item detail |
| Direction | Badge with arrow: IN ↑ / OUT ↓ |
| Reason | Badge: Purchase / Sale / Adjustment |
| Qty | Right-aligned |
| Balance after | Right-aligned, monospaced |
| Reference | Linked to PO or SO if applicable |
| User | Who made it happen |

**Page header actions:** "Export CSV" (Phase 2 — placeholder), "+ Manual Adjustment".

#### 6.8.2 Manual Adjustment form (modal)

| Field | Type | Required | Notes |
|---|---|---|---|
| Item | autocomplete | ✓ |  |
| Direction | radio | ✓ | IN / OUT |
| Quantity | number | ✓ |  |
| **Reason note** | textarea | ✓ | Free text, min 10 chars. **Required to enforce accountability.** |

**Actions:** Cancel • **Record adjustment** (primary).

**On submit:** toast *"Adjustment recorded."* and the new row appears at the top of the table.

---

### 6.9 Settings

#### 6.9.1 Profile

Read-only display of: name, email, role (`Operations`). Buttons: "Edit name", "Change password".

#### 6.9.2 Change password form

Fields: current password, new password, confirm new password. Validation: min 12 chars, recommend strength meter. Action: Save.

---

## 7. Workflows (user journeys) the design should make easy

These are the flows worth storyboarding in Figma:

1. **"Quickly create a sales order while a customer is on the phone."**
   Login → Sales Orders → "+ New Sales Order" → customer autocomplete → 2 line items with live stock indicator → submit. **Time budget: under 30 seconds for a 2-line order.**

2. **"Receive a shipment that just arrived at the warehouse."**
   Login → Purchase Orders → filter Draft → click row → "Receive" → confirm modal → see updated stock. **One screen, three clicks.**

3. **"Why does the system show 12 kg of Raw Plastic when we expect 20 kg?"**
   Stock Movements → filter by Raw Plastic → scan recent rows → click reference link to see the PO/SO that consumed it. The audit story must be **legible without explanation.**

4. **"Add a new finished product to start manufacturing a new bottle size."**
   Items → "+ Add Item" → fill form → save → land on item detail. **One form, no surprises.**

---

## 8. Out of scope — do **not** design these for Phase 1

- Production planning / bill of materials / MRP
- Accounting integration, invoices, payments, tax filing screens
- Barcode scanning UI
- Multi-warehouse / multi-location stock views
- Two-way Zoho CRM features (timelines of calls, emails, meetings, tasks, follow-ups) — those live in Zoho
- Reports / BI dashboards beyond the simple dashboard described above
- Dark mode
- Native mobile app
- Multi-currency / multi-language
- Bulk import / export beyond a single "Export CSV" link on Stock Movements (which is a Phase-2 placeholder)
- Notification preferences, email digests
- Public-facing pages (landing, marketing, signup)

If the team is unsure whether something is in scope, the answer is **no for Phase 1**.

---

## 9. Responsive expectations

Designed primarily for **desktop (≥ 1280 px)**. Tablet (≥ 768 px) should be
usable. Mobile (< 768 px) is **not** a Phase 1 target — degrade gracefully
(tables scroll horizontally, nav becomes a hamburger) but no mobile-specific
designs are required.

---

## 10. Accessibility baseline

- Colour contrast: WCAG AA minimum (4.5:1 for text).
- Every interactive element has a visible focus state.
- Form fields have visible labels (no placeholder-as-label).
- Status badges convey state with both colour and text/icon (no colour-only signalling).
- Keyboard navigation works for all primary flows.

---

## 11. Visual direction (for the moodboard)

- **Tone:** professional, calm, data-dense — closer to Linear / Stripe / Notion than to a B2C app.
- **Density:** comfortable, not cramped. Operations users scan tables for hours; reduce visual noise.
- **Typography:** one humanist sans (body), one monospaced (numbers, SKUs, IDs).
- **Colour:** restrained palette, one brand colour, four-five semantic colours (success, warning, error, info, neutral).
- **Iconography:** consistent set (Lucide, Phosphor, or similar — pick one and stick to it).
- **Numbers:** right-aligned, monospaced, with thousands separators.
- **Empty states:** friendly but not cartoonish.

---

## 12. Deliverables expected from the design team

For each page in §6:

1. **Wireframe** (low-fi) showing layout + content hierarchy.
2. **Hi-fi visual** in the agreed style.
3. **States:** default, loading, empty, error, success (where applicable).
4. **Interactions:** hover, focus, disabled, active.
5. **Responsive variants:** desktop default + tablet collapse behaviour.

For the design system (§5):

- A Figma component library covering every primitive.
- A documented colour + typography + spacing scale.

---

## 13. Open questions to resolve with product

The design team should ask before they start:

1. What does the brand look like? Logo, colour, voice?
2. Currency: single currency assumed? Symbol and position?
3. Date format: `28 May 2026` vs. `2026-05-28` vs. locale-aware?
4. Tax ID label: `GSTIN`, `VAT`, generic `Tax ID`? Country?
5. Default page size for tables: 25 OK?
6. Should the "Sync to Zoho" status be visible to every user or only to admins?
7. Is there a target persona name we should use throughout the prototype (e.g. "Priya, the warehouse supervisor")?

---

This document is intentionally exhaustive about Phase 1 and silent about
Phase 2+. If a screen, field, or behaviour is **not** listed here, treat it
as out of scope and ask before designing it.
