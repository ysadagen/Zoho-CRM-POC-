# Frontend — Execution Log

This file is **my contract with the user**, not docs for end-users. It exists
so I never drift from the agreed plan, never re-do work that's already
shipped, and never break a feature from a previous phase while building the
next one.

Re-read this file at the start of every session before writing any code.

The full plan lives at
`C:\Users\Lenovo\.claude\plans\proud-bouncing-dragonfly.md`. This file is the
**delivery view** of that plan: what shipped, when, how to verify it.

---

## Working agreement

1. Deliver **one phase at a time**. After a phase ships, stop and wait
   for the user to test in the browser. Do not start the next phase
   until the user says "next" / "phase N+1" / similar.
2. **Spec-first, test-first.** Every phase: state the spec, write failing
   tests (Red), implement the minimum (Green), refactor. See `CLAUDE.md §0`.
3. Each phase leaves the app in a runnable, green state: `npm run verify`
   passes (lint + build + tests), coverage holds (global ≥ 80 %,
   `lib/**` ≥ 95 %), no TypeScript errors, no broken routes.
4. Each phase ends with a one-line entry in the table below, a bullet list
   of files touched, and a copy-paste **"How to test (you)"** command block
   so the user can verify the phase independently.
5. Never modify Phase N code while implementing Phase N+1 unless the
   change is *required* by N+1 — and even then, call it out explicitly
   in the new phase's notes.
6. Honour the three non-negotiables from `CLAUDE.md §5` in every phase
   that touches them.

---

## Phase status

| # | Phase | Status | Date shipped |
|---|---|---|---|
| 0 | Scaffold | ✅ shipped | 2026-06-01 |
| 0.5 | Test harness (Vitest + RTL + MSW + coverage) + backfill Phase 0 `lib/` tests | ✅ shipped | 2026-06-02 |
| 1 | Design-system primitives + layout shell + toast/error infra | 🔨 partial (shell + dashboard primitives shipped) | 2026-06-02 |
| 2 | Auth (login + register) | ✅ shipped | 2026-06-02 |
| 3 | Dashboard | ✅ shipped (UI + live data) | 2026-06-02 |
| 4 | Items (list + detail + form drawer) + toast infra + logging | ✅ shipped | 2026-06-03 |
| 5 | Customers (list + detail + form drawer) | ✅ shipped | 2026-06-03 |
| 6 | Vendors (list + detail + form drawer + supplied-items terms) | ✅ shipped | 2026-06-03 |
| 7 | Purchase Orders (list + detail + create + receive flow) | ✅ shipped | 2026-06-03 |
| 8 | Sales Orders (list + detail + create with live stock + ship flow) | ✅ shipped | 2026-06-03 |
| 9 | Stock Movements (read-only ledger + manual adjustment modal) | ✅ shipped | 2026-06-03 |
| 10 | Settings (profile + change name + password placeholder) | ✅ shipped | 2026-06-04 |
| 11 | Polish + review (error boundary, README, audit) | ✅ shipped | 2026-06-04 |

---

## Phase 0 — Scaffold

**Goal:** Stand up an empty Vite + React + TypeScript app that compiles
clean, with the design system CSS ported, the API client wired, and the
typed Backend contract stub'd. App boots to a placeholder page.

**Files created:**
- `package.json`, `package-lock.json`
- `vite.config.ts`, `tsconfig.json`, `tsconfig.node.json`
- `index.html`
- `.env.example`, `.gitignore`, `eslint.config.js`, `.prettierrc.json`
- `src/main.tsx`, `src/App.tsx`, `src/env.ts`
- `src/styles/fonts.css`, `src/styles/globals.css`, `src/styles/login.css`
- `src/lib/api/client.ts`, `src/lib/api/errors.ts`,
  `src/lib/api/request-id.ts`, `src/lib/api/types.ts`
- `src/lib/logger.ts`, `src/lib/format.ts`
- `src/types/api.types.ts`, `src/types/enums.ts`
- `public/favicon.svg`

**Deps installed (runtime):**
- `react`, `react-dom`
- `react-router-dom`
- `@tanstack/react-query`
- `axios`
- `react-hook-form`, `zod`, `@hookform/resolvers`

**Deps installed (dev):**
- `@types/react`, `@types/react-dom`, `@types/node`
- `typescript`, `vite`, `@vitejs/plugin-react`
- `eslint`, `@eslint/js`, `typescript-eslint`, `eslint-plugin-react-hooks`,
  `eslint-plugin-react-refresh`, `globals`
- `prettier`

**Out of scope for Phase 0:** any UI components, any routes beyond the
boot placeholder, any actual API calls. Components/pages are built in
Phase 1+.

**How to verify Phase 0:**
1. `cd Frontend`
2. `npm install` *(already done — 211 packages)*
3. *(optional)* `cp .env.example .env` and edit if your Backend isn't at the default URL.
4. `npm run dev` → opens `http://localhost:5173/`; renders the
   "Adagen — Boot OK" card showing API base URL, env, Vite mode, and the
   live result of a probe to the Backend's `/health` endpoint. If the
   Backend is down the probe row says "Cannot reach the server …" with a
   client-generated Request ID.
5. `npm run build` → succeeds; output sizes ≈ 191 KB JS / 23 KB CSS gzipped to 65/5 KB.
6. `npm run lint` → clean (0 errors, 0 warnings).

**What Phase 0 deliberately does NOT do:**
- No routing (no React Router yet). The app is a single mounted page.
- No real UI components. Phase 1 lands the design-system primitives.
- No auth flow, no protected routes. Phase 2.
- No `QueryClientProvider`. Phase 1 wires it before any feature needs it.
- **No tests.** Phase 0 shipped before we locked in TDD — Phase 0.5 pays
  that back before any feature code is written.

---

## Phase 0.5 — Test harness + Phase 0 backfill

**Goal:** Stand up the production-grade test toolchain and bring the Phase 0
foundation under test, so the `spec → red → green → refactor` loop holds from
Phase 1 onward. (See `CLAUDE.md §0`.)

**Scope:**
- Dev deps: `vitest`, `@testing-library/react`, `@testing-library/user-event`,
  `@testing-library/jest-dom`, `jsdom`, `msw`, `@vitest/coverage-v8`.
- `vitest.config.ts` (jsdom env, setup file, coverage thresholds: global
  ≥ 80 %, `lib/**` ≥ 95 %); `src/test/setup.ts` (jest-dom + MSW lifecycle).
- `package.json` scripts: `test`, `test:watch`, `test:coverage`, `verify`.
- Backfill tests for the existing foundation:
  - `lib/api/errors.test.ts` — envelope parse, 422 `detail` → `field`,
    network error, unknown-shape fallback, request-id precedence.
  - `lib/format.test.ts` — currency / qty / signed-qty / date / relative /
    ISO, incl. `null` / `NaN` / empty inputs.
  - `lib/logger.test.ts` — redaction of secret keys, level threshold.
  - `lib/api/client.test.ts` (MSW) — `X-Request-ID` + Bearer attached,
    error → `ApiError`, 401 auth-codes fire the handler, auth-flow exempt.
  - `env.test.ts` — `VITE_APP_ENV` fallback, trailing-slash strip.

**Out of scope:** any UI-component or feature tests — those land with their
own phase, test-first.

**Shipped:**
- `vitest.config` folded into `vite.config.ts` (jsdom, MSW-ready, coverage with
  thresholds: global 80 / `lib/**` 95); `src/test/setup.ts` (jest-dom + cleanup).
- Scripts: `test`, `test:watch`, `test:coverage`, `verify`.
- Backfill tests: `format` (22), `errors` (8), `logger` (4), `dev-logging` (2,
  env-mocked to exercise debug branches), `request-id` (3), `client` (7, MSW).
- `src/env.ts` → `src/config/env.ts` (per the new structure) with `env.test.ts`.

**How to test (you):**
```powershell
cd Frontend
npm install            # picks up the new test dev-deps
npm run test           # all suites, one-shot
npm run test:coverage  # enforces thresholds; opens-able report in coverage/
```

---

## Phase 1 — Design system primitives + layout shell  *(partial — dashboard slice)*

**Goal of this slice:** implement the design's `app/index.html` (the Dashboard)
in React, end-to-end, on the locked feature-first structure — building only the
primitives + chrome the dashboard needs (the rest land with their own pages).

**Folder structure adopted** (feature-first; see `CLAUDE.md §3` for rationale):
added `src/app/` (App, router, routes), `src/config/` (env), and per-feature
`pages/ components/` under `features/`.

**Design source:** ported from the handoff bundle `zoho-crm-inventory`
(`project/app/index.html` + `chrome.js`). The bundle's `styles.css` is
byte-identical to our `globals.css` (verified) — zero drift.

**Shipped:**
- **Icons** — `components/ui/Icon.tsx`: the exact `ADAGEN_ICONS` set ported from
  `chrome.js` (Lucide-style) + the dashboard glyphs (refresh, alert, sync,
  check, clock). Recovered `chrome.js` made the earlier "recreate with Lucide"
  decision moot — exact port gives true parity.
- **Primitives** (`components/ui/`): `Button` + `ButtonLink`, `Badge`, `Card` +
  `CardHeader`, `KpiCard`, `ProgressBar`, `Segmented`. Plus `lib/cx.ts`.
- **Layout** (`components/layout/`): `AppShell`, `Sidebar` (8 nav items, active
  highlight), `Topbar` (route-aware crumb, disabled search, user menu),
  `Footer`, `PageHeader`, `navItems.ts`.
- **App wiring**: `app/App.tsx` (QueryClient + BrowserRouter), `app/router.tsx`
  (AppShell layout route + dashboard + 7 navigable placeholders + 404),
  `app/routes.ts`. `main.tsx` now mounts `@/app/App`.
- **System pages**: `components/PlaceholderPage.tsx`, `components/NotFoundPage.tsx`.
- **Tests**: `Button`, `Badge`, `KpiCard`, `ProgressBar`, `Icon`, full-app
  integration (`app/App.test.tsx`), routing (`app/router.test.tsx`).

**Not yet built (rest of Phase 1):** Input/Select/Textarea/Field/Checkbox,
Modal/Drawer/Tabs/DataTable/Skeleton/EmptyState, toast infra, ErrorBoundary +
PageError. These land as their consuming features need them.

**How to test (you):**
```powershell
cd Frontend
npm install
npm run dev        # http://localhost:5173 → redirects to /dashboard
```
Check in the browser:
- Sidebar: 8 items, **Dashboard** highlighted; click any other → a "coming in
  Phase N" placeholder (nav stays, no dead links). Unknown URL → in-app 404.
- Topbar breadcrumb tracks the active page; search shows "coming soon".
- The dashboard matches `index.html`: 5 KPIs, stock-value chart (7D/30D/90D/YTD
  toggle works), Recent Movements table, Quick Actions, Needs Attention bars,
  CRM Sync card. Footer shows version + `DEV` chip.

```powershell
npm run verify        # lint + build + test — all green
npm run test:coverage # 99.8% lines overall; lib/ ≥ 95%
```

---

## Phase 2 — Auth (login + register)

**Spec:** wire login + register to the real Backend (`POST /api/v1/auth/login`
→ `{access_token, expires_in, user}`; `POST /api/v1/auth/register` → the user,
then auto-login). Persist the session, restore it on reload, guard every app
route, and bounce expired/unauthenticated users to `/login?reason=expired`.

**Shipped:**
- **Session infra** (`src/auth/`): `token-storage` (localStorage, expiry-aware),
  `auth.api` (typed login/register), `AuthContext` + `AuthProvider`
  (login/register/logout, restores session on mount, wires the api client's
  token source + 401-expiry handler), `useAuth`, `ProtectedRoute`.
- **UI**: `components/layout/AuthShell` (two-pane), `features/auth/pages/`
  `LoginPage` + `RegisterPage` (RHF + Zod), `features/auth/components/`
  `PasswordInput` (show/hide) + `AuthAlert` (carries the Request ID on errors),
  new primitives `ui/Input` + `ui/Field`, icons `eye`/`eyeOff`/`arrowRight`.
- **Wiring**: router split into public `AuthShell` routes + `ProtectedRoute`-gated
  `AppShell` routes; `App` now mounts `AuthProvider`; `Topbar` shows the real
  signed-in user with a working **Log out** menu; `globals.css` gains a dropdown
  `.menu-*` primitive + `.is-required` label marker.
- **Tests** (+`src/test/utils.tsx` provider harness): `token-storage`,
  `auth.api` (MSW), `ProtectedRoute`, `LoginPage` (success / bad creds / required),
  `RegisterPage` (success / mismatch / duplicate email), `Topbar` logout;
  updated `App` + `AppRouter` tests for the auth gate. 85 tests green.

**Deliberate deviations from the mock (no dead controls):** dropped the
"Continue with Zoho SSO" button and cosmetic "Keep me signed in" (no backend);
"Need an account?" now links to a real `/register`.

**How to test (you):** the Backend must be running.
```powershell
# Backend (separate terminal), from Code/Backend:
uv run uvicorn app.main:app --reload --app-dir src --port 8000

# Frontend, from Code/Frontend:
npm run dev
```
Walk it in the browser:
1. Visit any URL while logged out → redirected to `/login`.
2. **Register** a new user (`/register`) → auto-logs in → lands on the dashboard.
3. Open the **account menu** (top-right) → **Log out** → back to login.
4. **Log in** with that user → dashboard. Wrong password → inline
   "Invalid email or password." Empty fields → Zod messages.
5. Refresh while logged in → still authenticated (session restored).
6. In devtools set the stored `adagen.session` `expiresAt` to the past → next
   navigation/API call routes to `/login?reason=expired`.

```powershell
npm run verify         # lint + build + test (85 tests) — all green
npm run test:coverage  # 98.5% lines; lib/ ≥ 95%
```

---

## Phase 3 — Dashboard

The Dashboard **UI** shipped in the Phase 1 slice; this phase **replaced the
static `dashboard.seed.ts` with live React Query hooks** now that auth (Phase 2)
provides a bearer token. The section components became data-driven (props →
hooks) with skeleton-loading and error states.

**Spec:** derive the dashboard from the standard Backend list endpoints (there
is no aggregate endpoint — Backend_Reference §13). Show honest figures only,
with skeletons while loading and an in-card error carrying the **Request ID +
Retry** (§5.6 / §5.8) on failure.

**Data wiring (live):**
- **KPIs** (`buildKpis`): Total Stock Value = Σ(stock × price) over the catalog;
  Low Stock Items = count of `LOW_STOCK`/`NO_STOCK`; Open POs / Open SOs = the
  pagination `total` of a `status=DRAFT&limit=1` query (counts without fetching
  rows). The 5th tile, **CRM Sync Health**, is an honest `—` placeholder —
  the Integration Layer is a later phase.
- **Needs Attention**: live low-stock items from `GET /items`, sorted
  most-critical first, top 5, with a "below threshold" ratio bar.
- **Recent Stock Movements**: `GET /stock-movements?limit=5`; `item_id` resolved
  to name + unit via the shared (deduped) items query; signed qty + canonical
  direction/reason badge + humanised reference.
- **Stock-value chart**: headline figure is the live total; the trend line is
  labelled **illustrative** (a historical series is a later reporting phase).
- **Greeting** uses the signed-in user's first name + a time-of-day phrase;
  **Refresh** invalidates the `['dashboard']` query tree.

**Deliberate honesty deviations from the mock (no fabricated data):** dropped
the invented "vs last week" KPI deltas (no historical series); the CRM sync card
is a clearly-marked "not connected yet" placeholder instead of fake
synced/pending/failed counts.

**Known POC simplification:** the catalog-derived figures (Total Stock Value,
low-stock list/count) are computed over the first `limit=100` items — adequate
for the POC dataset; pagination-aware aggregation lands if the catalog grows.

**Shipped:**
- **Data access** (`features/dashboard/api/dashboard.api.ts`): typed
  `fetchDashboardItems` / `fetchRecentMovements` / `fetchDraftPurchaseOrderCount`
  / `fetchDraftSalesOrderCount`.
- **Pure derivations** (`features/dashboard/dashboard.transform.ts`):
  `totalStockValue`, `isLowStock`/`lowStockItems`, `toLowStockVM`,
  `movementBadge`/`movementReference`/`toMovementVM`, `buildKpis`, `greeting`,
  `firstName` — fully unit-tested.
- **Hooks** (`features/dashboard/hooks/useDashboard.ts`): one query per source,
  shared `items` query deduped across cards; `dashboardKeys`.
- **Components**: `KpiRow`, `RecentMovements`, `NeedsAttention`,
  `StockValueChart`, `CrmSyncCard` rewired to live data + loading/empty/error;
  new `components/LoadError.tsx` (Request ID + Retry); new
  `components/ui/Skeleton.tsx` primitive.
- **Page**: `DashboardPage` greets the real user, dates today, Refresh works.
- **Lib**: `format.formatLongDate` ("Thursday, 28 May 2026").
- **Removed**: `dashboard.seed.ts`.
- **Tests** (+co-located): `dashboard.transform` (14), `dashboard.api` (4, MSW),
  `KpiRow` / `RecentMovements` / `NeedsAttention` (success + empty + error/Request
  ID, MSW), `DashboardPage` (greeting + Refresh refetch), `Skeleton` (2),
  `formatLongDate`. Updated `App` / `AppRouter` / `Topbar` / `LoginPage` /
  `RegisterPage` tests to mock the dashboard endpoints + a time-agnostic greeting.
  **116 tests green**, coverage 98.6 % lines (global ≥ 80 %, `lib/**` 100 %).
- **Test harness**: `setup.ts` raises the Testing-Library async timeout and
  `vite.config.ts` the per-test timeout, so the v8-coverage run isn't flaky on
  slower machines.

**How to test (you):** the Backend must be running with some data.
```powershell
# Backend (separate terminal), from Code/Backend:
uv run uvicorn app.main:app --reload --app-dir src --port 8000

# Frontend, from Code/Frontend:
npm run dev
```
Walk it in the browser (log in first):
1. Dashboard greets you by name with today's date.
2. KPIs show live numbers: Total Stock Value, Low Stock count, Open PO/SO counts.
   CRM Sync Health reads "—" (Integration Layer pending).
3. **Needs Attention** lists items at/under threshold (worst first); empty →
   "All stocked up".
4. **Recent Stock Movements** shows the last 5 with item name, signed qty and a
   reference; empty → "No movements yet".
5. Stop the Backend and click **Refresh** → each card shows an error with a
   **Request ID** and a **Retry** that recovers once the Backend is back.

```powershell
npm run verify         # lint + build + test (116 tests) — all green
npm run test:coverage  # 98.6% lines; lib/ 100%
```

---

## Phase 4 — Items (+ toast infrastructure + logging)

**Spec:** Build the Items domain end-to-end against the live Backend (`/items`
CRUD + `/stock-movements` for detail aggregates) — no static data. This phase
also lands the **toast infrastructure** (first feature with mutations; satisfies
§5.6) and **structured mutation/error logging**.

**Shipped — shared infra:**
- **Toasts** (`components/toast/`): `ToastContext` (types + context),
  `ToastProvider` (auto-dismiss 4.5 s / 12 s persist), `ToastHost` (bottom-right
  stack; danger toasts render the **Request ID** via `.req .mono` — §5.6),
  `useToast`. Wired into `app/App.tsx` and the test harness (`test/utils`).
- **`hooks/useApiError`**: canonical mutation-error surface — logs
  `{code, httpStatus, requestId}` via `lib/logger` **and** raises a danger toast
  carrying that Request ID (optionally with a recovery action).
- **`hooks/useDebounce`**: shared (search inputs).
- **`components/errors/PageError`**: full-width read-error card (Request ID +
  Retry) for list/detail pages.
- **UI primitives** (`components/ui/`): `Skeleton`, `Select`, `Textarea`,
  `EmptyState`, `Tabs`, `Pager`, `Drawer` (ESC + scrim close, `aria-modal`,
  mount-on-open). Added `info` + `close` icons.

**Shipped — items feature** (`features/items/`):
- `api/items.api.ts`: `listItems` (limit/offset/type/search), `getItem`,
  `createItem`, `updateItem`, `listItemMovements`.
- `item.schema.ts` (Zod create/edit), `item.transform.ts` (badges, movement
  summary, form→payload mappers — all pure & tested), `items.keys.ts`,
  `hooks/useItems.ts` (queries + create/update mutations that log lifecycle and
  invalidate the items cache).
- **List page**: server-side **type + search** filters with **server
  pagination** (`Pager`, 25/50/100), row→detail, Add/Edit drawer, skeleton /
  empty / error states.
- **Detail page**: header (type + status badges), 5 stat cards derived from the
  movement ledger (current stock, reorder, last movement, lifetime in/out),
  **Overview** + **Movement history** tabs, Edit drawer.
- **Form drawer** (`ItemFormDrawer`): RHF + Zod, create & edit; success →
  toast (+ navigate to detail on create); `422` field → `setError`; other
  errors → danger toast with Request ID. Edit shows SKU/Type read-only (not
  PATCH-able per Backend §9.3).
- Router: `/items` (list) + `/items/:id` (detail) replace the placeholder.

**Logging (best-practice, per CLAUDE.md §9):** mutation success logs
`items.create` / `items.update` with `{itemId, sku}` (no PII); failures log via
`useApiError` with `{code, httpStatus, requestId}` correlating to the Backend
log line; the axios interceptor still logs transport errors. Levels respected
(info for lifecycle, error for failures); secrets redacted by `lib/logger`.

**Deliberate deferrals (no supporting API — honest, not faked):**
- The detail **Vendors** tab (raw items) and **Used-in** tab (finished items)
  are omitted — the Backend has no "item → vendors" or "SO by item" endpoint.
- **Status filter is client-side** over the loaded page (the Backend `/items`
  has no `status` filter — §9.3). The dashboard's `?status=low` deep-link
  pre-selects it. Type + search remain true server filters.
- Catalog-derived numbers respect the Backend's `limit ≤ 100` (POC dataset).

**Tests:** toast (incl. §5.6 Request ID), `useApiError`, `useDebounce`,
`Drawer`/`Tabs`/`Pager`/`Skeleton`, `item.transform`, `items.api` (MSW),
`ItemFormDrawer` (create/validation/409-with-RequestID/422-field/edit),
`ItemsListPage` (list/status-filter/type-filter/create-drawer/error),
`ItemDetailPage` (header/stats/tabs/edit/404). Updated `router` test (Items is
now real). **164 tests green**, coverage **97.7 % lines** (global ≥ 80 %,
`lib/**` 100 %).

**How to test (you):** Backend running with a few items (and ideally a received
PO / shipped SO so movements exist).
```powershell
# Backend (separate terminal), from Code/Backend:
uv run uvicorn app.main:app --reload --app-dir src --port 8000
# Frontend, from Code/Frontend:
npm run dev      # log in first
```
1. **Items** in the sidebar → live table. Filter by **type** (server) and
   **status** (client); type in **search** (debounced) → list narrows.
2. **+ Add Item** → drawer. Submit empty → inline Zod errors. Create a valid
   item → success toast, lands on its **detail** page. Re-create the same SKU →
   danger toast with a **Request ID**.
3. On detail: stat cards, **Overview** + **Movement history** tabs, **Edit** →
   change a field → success toast, values update (SKU/Type are read-only).
4. Stop the Backend, reopen Items → page error with **Request ID** + **Retry**.

```powershell
npm run verify         # lint + build + test (164 tests) — all green
npm run test:coverage  # 97.7% lines; lib/ 100%
```

---

## Phase 5 — Customers

**Spec:** Customers domain against the live Backend (`/customers` CRUD +
`/sales-orders?customer_id` for the detail tab). Reuses every Phase 4 primitive
(Drawer, Tabs, Pager, EmptyState, PageError, toast, `useApiError`,
`useDebounce`) — no new infra.

**Shipped** (`features/customers/`):
- `api/customers.api.ts` (list/get/create/update + `listCustomerSalesOrders`),
  `customer.schema.ts` (one Zod schema for create+edit), `customer.transform.ts`
  (form↔payload, pure & tested), `customers.keys.ts`, `hooks/useCustomers.ts`
  (queries + mutations that log `customers.create/update` and invalidate cache).
- **List page**: server search (debounced) + server pagination, row→detail,
  Add/Edit drawer, skeleton/empty/error states, "Privileged" badge.
- **Detail page**: **Profile** tab (master fields) + **Sales orders** tab (live
  `GET /sales-orders?customer_id`, read-only, status badge), Edit drawer.
- **Form drawer**: company_name (required) + contact/email/phone/code/GSTIN +
  privileged checkbox; success→toast (+navigate on create), `422`→field error,
  other errors→danger toast w/ Request ID.
- Router: `/customers` + `/customers/:id` replace the placeholder.

**Honest deviations (Backend has no field/endpoint):** the form has **no
billing-address / notes** (not on the Backend customer model); the profile shows
a **"Zoho sync — not connected yet"** note (Integration Layer is a later phase);
the list omits **SO-count / revenue** columns (would be an N+1 across customers).

**Tests:** `customer.transform`, `customers.api` (MSW), `CustomerFormDrawer`
(create/validation+email/409-Request-ID/edit), `CustomersListPage`
(list/create-drawer/error), `CustomerDetailPage` (profile/orders-tab/edit/404).
Updated `router` test placeholder → Vendors/Phase 6. **182 tests green**,
coverage **96.5 % lines** (global ≥ 80 %, `lib/**` 100 %).

**How to test (you):** Backend running with a customer or two (and ideally a
sales order for that customer).
```powershell
npm run dev      # log in, then open Customers
```
1. **Customers** → live table; type in **search** (debounced) → narrows.
2. **+ Add Customer** → drawer; empty submit → "Company name is required",
   bad email → "Enter a valid email"; create → success toast, lands on detail.
3. Detail: **Profile** + **Sales orders** tabs; **Edit** → save → toast + update.
4. Stop the Backend, reopen Customers → page error with **Request ID** + Retry.

```powershell
npm run verify         # lint + build + test (182 tests) — all green
```

---

## Phase 6 — Vendors (+ vendor-item terms)

**Spec:** Vendors domain against the live Backend — mirrors Customers, plus the
**vendor-item pricing terms** ("Items supplied") relationship (full CRUD) and a
**Purchase orders** tab. Lands the shared **`Modal`** primitive (delete-confirm;
reused by PO receive / SO ship later).

**Shipped:**
- **Shared:** `components/ui/Modal.tsx` (centred confirm dialog, ESC + backdrop
  close) + test.
- `features/vendors/` — `api/vendors.api.ts` (vendor CRUD + nested term
  create/update/delete + `listVendorPurchaseOrders`), `vendor.schema.ts`
  (vendor + term Zod schemas), `vendor.transform.ts` (pure form↔payload for both
  vendor and term, incl. immutable `item_id` on term edit), `vendors.keys.ts`,
  `hooks/useVendors.ts` (queries + 5 mutations, each logging + invalidating).
- **List page** — server search + pagination, row→detail, add/edit drawer.
- **Detail page** — three tabs: **Profile**, **Items supplied** (terms table
  with Link/Edit/Remove; remove goes through a `Modal` confirm), **Purchase
  orders** (live `GET /purchase-orders?vendor_id`, read-only).
- **Term drawer** — item picker (from the items query) on create, read-only item
  on edit; rate / discount % / effective-from / effective-to; `409
  OVERLAPPING_TERMS` and other errors → danger toast with Request ID.
- Router: `/vendors` + `/vendors/:id` replace the placeholder.

**Honest deviations (Backend has no field/endpoint):** the terms table shows
**rate / discount / effective window** — the spec's *lead-time / MOQ / last-PO*
columns aren't on the Backend `vendor_item_terms` model; the list omits
**items-supplied / PO-count** columns (would be N+1). Item names in the terms
table are resolved by reusing the items query.

**Tests:** `vendor.transform`, `vendors.api` (MSW, incl. nested term routes),
`VendorFormDrawer` (create/validate/409-Request-ID/edit), `VendorTermsTab`
(render/link-drawer/remove-confirm→DELETE), `VendorsListPage`,
`VendorDetailPage` (profile/items-tab/orders-tab/404), `Modal`. Router-test
placeholder → Purchase Orders/Phase 7. **209 tests green**, coverage **94.8 %
lines** (`lib/**` 100 %).

**How to test (you):** Backend running with a vendor (and ideally a PO for it).
```powershell
npm run dev      # log in, open Vendors
```
1. **Vendors** → live table; search; **+ Add Vendor** → drawer → create → lands
   on detail.
2. Detail → **Items supplied**: **Link item** (pick an item, rate, dates) →
   appears in the table; **Edit** changes terms; **Remove** → confirm modal →
   gone. Overlapping dates → danger toast with **Request ID**.
3. **Purchase orders** tab lists this vendor's POs. **Edit** (top-right) updates
   the vendor.
4. Stop the Backend, reopen Vendors → page error with **Request ID** + Retry.

```powershell
npm run verify         # lint + build + test (209 tests) — all green
```

---

## Phase 7 — Purchase Orders (+ receive flow)

**Spec:** Purchase Orders against the live Backend — list (status/vendor
filters), a multi-line **create** screen, detail, and the **receive** flow
(stock IN). Reuses the `Modal` (receive confirm), vendors/items queries for
pickers + id→name resolution.

**Shipped** (`features/purchase-orders/`):
- `api/po.api.ts` (list/get/create/receive), `po.schema.ts` (create + line-item
  Zod, line array `min(1)`), `po.transform.ts` (payload mapper, `lineTotal`,
  `estimatedTotal`, `poStatusBadge`, `receiveDeltas` — pure & tested),
  `po.keys.ts`, `hooks/usePurchaseOrders.ts` (list/detail/create/receive;
  **receive invalidates both PO and item caches** since stock changes).
- **List page** — server **status** (segmented) + **vendor** (select) filters,
  pagination, vendor-name resolution, inline **Receive** on draft rows.
- **Create page** (`/purchase-orders/new`) — RHF + `FormProvider`; vendor +
  expected-delivery + notes + a dynamic **line-items editor** (`useFieldArray`,
  RAW-item picker, qty, optional unit price, per-line + estimated totals); sticky
  footer; saved as Draft. `422 PRICE_UNAVAILABLE` / `409 DUPLICATE_LINE_ITEM` /
  others → danger toast with Request ID.
- **Detail page** — header (vendor link, status, total) + dated stat cards +
  line-items table + notes + **Receive** button (DRAFT only).
- **`ReceivePoModal`** — lists the `+qty unit item` deltas; Confirm → receive →
  "Stock updated." toast; `409 PO_NOT_DRAFT` etc. → Request-ID toast.
- Router: `/purchase-orders`, `/purchase-orders/new`, `/purchase-orders/:id`.
- Promoted `.stat` / `.stat-grid` from `items.css` to `globals.css` (now used by
  two detail pages).

**Honest deviations:** PO list has **no text-search** (Backend filters are
status/vendor/date only); **order date isn't a create field** (server-set);
`unit_price` left blank is **priced by the Backend** from the vendor's active
term (blank + no term → `PRICE_UNAVAILABLE`, surfaced as a toast); the detail
**stock-impact list** is deferred — the Backend doesn't expose a movements
`reference_id` filter yet (a note links it to the audit ledger, Phase 9).

**Tests:** `po.transform`, `po.api` (incl. `/receive`), `PurchaseOrderCreatePage`
(validation / create / PRICE_UNAVAILABLE), `PurchaseOrdersListPage`
(list / status-filter / inline-receive modal), `PurchaseOrderDetailPage`
(header+lines / receive-confirm→POST / 404). Router-test placeholder → Sales
Orders/Phase 8. **228 tests green**, coverage **94.9 % lines** (`lib/**` 100 %).

**How to test (you):** Backend running with a vendor that has item pricing terms.
```powershell
npm run dev      # log in, open Purchase Orders
```
1. **+ New Purchase Order** → pick vendor, add line(s) (item + qty; leave price
   blank to use the vendor term) → **Save as Draft** → lands on detail.
2. On the draft (or inline on the list row) → **Receive** → confirm modal shows
   the stock deltas → **Confirm receive** → "Stock updated."; status flips to
   Received and the item's stock goes up (check the item's detail page).
3. Filter the list by **status** / **vendor**. Stop the Backend → page error
   with **Request ID** + Retry.

```powershell
npm run verify         # lint + build + test (228 tests) — all green
```

---

## Phase 8 — Sales Orders (+ live stock + ship flow)

**Spec:** Sales Orders against the live Backend — list, multi-line **create with
the §5 live-stock indicator**, detail, and the **ship** flow (stock OUT). Mirrors
the PO structure; shared order-line math extracted to `lib/orderMath` (used by
PO + SO).

**Non-negotiable #2 implemented:** each SO create line shows a live `StockChip`
(`ok` / `warn` below-reorder / `short`); the **Create button is disabled while
any line is short**; on `409 INSUFFICIENT_STOCK` at ship, the danger toast
carries a **"Refresh stock"** action that invalidates the items + SO queries.

**Backend reconciliation:** the Backend has **no stock pre-check at create**
(drafts may over-book) and raises `INSUFFICIENT_STOCK` only at `/ship`. So the
StockChip + disable is the client-side create guard, and the `409 → Refresh
stock` handler lives on ship — matching reality while honouring the contract.

**Shipped:**
- **Shared:** `lib/orderMath.ts` (`lineTotal`, `estimatedTotal`) — `po.transform`
  now re-exports it (Phase 7 untouched behaviourally; its tests still pass).
  `components/ui/StockChip.tsx` primitive.
- `features/sales-orders/` — `api/so.api.ts` (list/get/create/ship),
  `so.schema.ts`, `so.transform.ts` (`soStatusBadge`, `soLineStock`,
  `hasShortLine`, `shipDeltas`, payload mapper — pure & tested), `so.keys.ts`,
  `hooks/useSalesOrders.ts` (ship invalidates SO + item caches).
- **List** — status (segmented) + customer (select) filters, pagination,
  customer-name resolution, inline **Ship** on draft rows.
- **Create** (`/sales-orders/new`) — FINISHED-item picker per line, live
  `StockChip`, estimated total, Create disabled while short.
- **Detail** — header (customer link, status, total) + dated stat cards +
  line items + notes + **Ship** button (DRAFT only).
- **`ShipSoModal`** — `-qty unit item` deltas; Confirm → "Order shipped. Stock
  updated."; `INSUFFICIENT_STOCK` → Request-ID toast + "Refresh stock".
- Router: `/sales-orders`, `/sales-orders/new`, `/sales-orders/:id`.

**Honest deviations:** no SO text-search (Backend filters are status/customer/
date); no **cancel** action (Backend state machine is `DRAFT → SHIPPED` only,
no cancel); detail stock-impact list deferred (no movements `reference_id`
filter — Phase 9); create toast says "created" (stock changes on ship, not
create).

**Tests:** `orderMath`, `StockChip`, `so.transform`, `so.api`,
`SalesOrderCreatePage` (validation / **live chip + disable-on-short** / create),
`SalesOrdersListPage` (list / status-filter / inline-ship), `SalesOrderDetailPage`
(header+lines / ship-confirm→POST / **409 INSUFFICIENT_STOCK → Refresh stock** /
404). Router-test placeholder → Stock Movements/Phase 9. **253 tests green**,
coverage **95.0 % lines** (`lib/**` 100 %).

**How to test (you):** Backend running with a FINISHED item that has some stock.
```powershell
npm run dev      # log in, open Sales Orders
```
1. **+ New Sales Order** → pick customer + a finished item; type a qty **above**
   stock → red chip "short by N" and **Create order disabled**; lower it →
   green chip, Create enabled → **Create order** → lands on detail.
2. On the draft (or inline) → **Ship** → confirm modal shows `-qty` deltas →
   **Confirm ship** → "Order shipped. Stock updated."; item stock drops.
3. To see the §5 path: ship an SO whose qty now exceeds stock → danger toast
   with a **Request ID** and a **Refresh stock** button.

```powershell
npm run verify         # lint + build + test (253 tests) — all green
```

---

## Phase 9 — Stock Movements (audit ledger + manual adjustment)

**Spec:** the append-only audit ledger against the live Backend — a read-only,
filterable list plus the **manual-adjustment** modal (the only ledger write).

**Non-negotiable #3 implemented:** the table has **no edit/delete** controls;
the **Reference** column links to the originating PO/SO; the adjustment
**Reason note is `Zod.min(10)`** (accountability gate).

**Shipped** (`features/stock-movements/`):
- `api/sm.api.ts` (`listStockMovements`, `createAdjustment`), `sm.schema.ts`
  (adjustment Zod incl. remarks `min(10)`), `sm.transform.ts`
  (`directionBadge` IN ↑ / OUT ↓, `reasonLabel`, `movementReference`
  → linkable PO/SO or remarks, payload mapper — pure & tested), `sm.keys.ts`,
  `hooks/useStockMovements.ts` (list + adjustment mutation invalidating the
  ledger **and** item caches since stock changes).
- **List page** — item / direction / reason server filters, pagination,
  item-name + reference resolution, signed qty + balance-after columns.
- **`ManualAdjustmentModal`** — item + direction + quantity + reason note;
  success → "Adjustment recorded." + ledger/stock refresh; `404`/`409
  INSUFFICIENT_STOCK`/`422` → danger toast with Request ID.
- Router: `/stock-movements` (single ledger, no detail route) replaces the
  placeholder. Added the `.justify-end` helper to `globals.css`.

**Honest deviations:** **Export CSV** is a disabled Phase-2 placeholder
(UI_SPEC §6.8); the **User** column is omitted (names need the admin-only
`/users`); list filters are item/direction/reason/date (no user filter); item
names + references are resolved by reusing the items query.

**Tests:** `sm.transform`, `sm.api`, `ManualAdjustmentModal` (validation incl.
**10-char remarks** / record / `409 INSUFFICIENT_STOCK`), `StockMovementsListPage`
(render + linked reference / **read-only: no edit·delete** / direction filter /
adjustment modal). Router-test placeholder → Settings/Phase 10. **268 tests
green**, coverage **95.0 % lines** (`lib/**` 100 %).

**How to test (you):** Backend running with some movements (receive a PO / ship
an SO first).
```powershell
npm run dev      # log in, open Stock Movements
```
1. The ledger lists every movement; **Reference** links jump to the PO/SO; rows
   have **no edit/delete** (read-only). Filter by item / direction / reason.
2. **+ Manual Adjustment** → pick item + direction + qty; a reason under 10
   chars is rejected inline. Record → "Adjustment recorded.", new row appears
   and the item's stock updates. An OUT below zero → Request-ID danger toast.

```powershell
npm run verify         # lint + build + test (268 tests) — all green
```

---

## Phase 10 — Settings

**Spec:** a read-only **Profile** (name / email / role), an **Edit name** action,
and a **Change-password placeholder**.

**Shipped** (`features/settings/`):
- `api/settings.api.ts` (`updateProfile` → `PATCH /users/{id}`),
  `settings.schema.ts` (edit-name Zod), `hooks/useUpdateProfile.ts` (mutation
  that logs + syncs the new name into the auth session), `EditNameModal`,
  `SettingsPage` (+ `settings.css`).
- **Auth (additive):** `AuthContext` gained `updateUser(user)`; `AuthProvider`
  persists it to the stored session **and** updates state, so an edited name
  reflects in the topbar and survives reload. Existing auth flows unchanged
  (`ProtectedRoute` test mock updated).
- Router: `/settings` → `SettingsPage`. **All eight nav routes are now real** —
  the now-dead `PlaceholderPage` component and its router test were removed.

**Honest deviation:** the Backend has **no password-change endpoint** (`PATCH
/users/{id}` only accepts `full_name` for self), so **Change password** is a
disabled placeholder with a "not available yet" note — not a dead form.

**Tests:** `settings.api` (MSW PATCH), `SettingsPage` (profile + disabled
password placeholder / **edit-name reflects on the profile** / required-name
validation); router test now asserts the real Settings page. **272 tests
green**, coverage **95.1 % lines** (`lib/**` 100 %).

**How to test (you):**
```powershell
npm run dev      # log in, open Settings
```
1. Profile shows your name, email and role (Operations / Administrator).
2. **Edit name** → change it → Save → "Name updated."; the profile **and the
   top-bar name** update, and the change survives a reload.
3. **Change password** is disabled ("Coming soon") — no Backend endpoint yet.

```powershell
npm run verify         # lint + build + test (272 tests) — all green
```

---

## Phase 11 — Polish + production-readiness review

**Goal:** audit the whole app against the production-grade bar, then close real
gaps. (Skeletons, empty states and the 404 page already shipped with their
features, so this phase focused on the missing error boundary + a codebase
review.)

**Audit findings (clean):**
- **No stray `console.*`** anywhere — every log goes through `lib/logger`
  (redaction + level threshold). No `any`, no `as any`, no `TODO`/`FIXME`,
  no `.only`/`.skip`, no `eslint-disable` in source.
- **Error handling is uniform:** all traffic flows through the one axios
  instance → `ApiError` (no `AxiosError` leaks); mutations surface failures as
  danger toasts carrying the **Request ID** via `useApiError`; read queries use
  inline `PageError` / card states with Retry. The three §5 non-negotiables hold
  (toast Request ID, SO live-stock + disable + Refresh-stock, read-only ledger).
- **Separation of concerns is consistent across all 8 domains:**
  `api/` (typed endpoints) → `hooks/` (React Query + logging + invalidation) →
  `*.transform.ts` (pure, unit-tested) → `components/` (presentational) →
  `pages/` (composition). Shared primitives in `components/ui`, shared logic in
  `lib/` (`orderMath`, `format`, `logger`, `api`).
- **Tests:** 274 across 69 files; coverage **95 % lines** (global ≥ 80 %,
  `lib/**` 100 %), enforced — no skips.

**Gap closed:** there was **no top-level error boundary** (only referenced in
comments since Phase 1). Added `components/errors/ErrorBoundary.tsx` (logs
`ui.crash` through the structured logger, shows a recoverable fallback) and
wired it as the **outermost** wrapper in `app/App.tsx`, so a render crash shows
a "Reload page" fallback instead of a blank screen.

**Also:** removed the now-dead `PlaceholderPage` (all routes are real); refreshed
the README roadmap to reflect phases 0–11 shipped.

**Known, documented deferrals (need Backend/Integration work — not gaps in this
app):** Zoho sync badges + CRM sync card (Integration Layer, later phase);
detail "stock-impact" lists on PO/SO (no movements `reference_id` filter);
list-level item-supplied / PO·SO counts (would be N+1); password change (no
endpoint); Export CSV (Phase-2 placeholder); Playwright E2E of the four journeys
(needs a live Backend — run separately, not in the unit suite).

**How to test (you):**
```powershell
npm run dev      # exercise any flow; force a render error to see the fallback
npm run verify   # lint + build + test (274 tests) — all green
```

---

*All eleven phases shipped. The app is feature-complete against the Phase-1
scope, green end-to-end, and production-grade within the documented deferrals.*

---

## Feedback round 1 — UI refinements (post-Phase-11)

**Goal:** five reviewer asks, all UI. Spec → tests → green, no scope creep.

1. **Dashboard "New Order" split.** Extracted a reusable `components/ui/Menu.tsx`
   (`<Menu>` + `<MenuItem>`/`<MenuLinkItem>`) from the inline topbar pattern —
   closes on outside-click, ESC, and item activation; `role="menu"`/`menuitem`,
   `aria-haspopup`. The dashboard `+ New Order` is now a dropdown → **New Sales
   Order** (`/sales-orders/new`) · **New Purchase Order** (`/purchase-orders/new`).
   Documented as DESIGN_SYSTEM §6.16; added `.menu-pop-left` modifier.
2. **Items: unit price column.** Added a right-aligned mono `Unit price`
   (`formatCurrency(item.unit_price)`) between Unit and Stock.
3. **Quick Actions open the form directly.** PO/SO link to their `/new` create
   pages; Add Item / Add Customer deep-link with `?new=1`, which the Items /
   Customers list pages read to open the create drawer (and strip the param on
   close).
4. **Stock Movements: Customer / Vendor column.** New pure `movementParty()` in
   `sm.transform.ts` joins PURCHASE→PO→vendor and SALE→SO→customer client-side
   (page loads first 100 of each, mirroring the items query); ADJUSTMENT/unresolved
   → em dash. New `party` prop on `StockMovementsTable`.
5. **Back-nav from a movement's item.** The ledger's item link carries
   `state={{ from, fromLabel }}`; `ItemDetailPage` reads it so "← Stock Movements"
   returns to the ledger (defaults to "← Items" elsewhere). `renderWithProviders`
   gained an optional `state` for testing this.

**How to test (you):**
```powershell
npm run verify         # lint + build + 289 tests — all green
npm run test:coverage  # thresholds hold (global ≥ 80%, lib ≥ 95%)
npm run dev            # dashboard New Order menu; Items unit price; Quick
                       # Actions open forms; ledger party column + back-nav
```

---

## Pharma alignment — bringing the Frontend up to the Backend pharma upgrade

The Backend shipped a pharmaceutical-inventory upgrade (see
`../Backend/proposal.md` + `../Backend/execution.md`): item raw/finished detail
blocks, common-pharma fields, lots (`batches`), PO-receive-into-lots, and
FEFO ship. This track aligns the Frontend to `../Backend/docs/Backend_Reference.md`.
Ordered, non-breaking phases.

| Phase | Slice | Status |
|---|---|---|
| FE-0 | Type/enum foundation — mirror the new Backend schema | ✅ **SHIPPED** |
| FE-1 | PO receive → lots (the **breaking** fix) | ✅ **SHIPPED** |
| FE-2 | Items: pharma fields + raw/finished detail blocks (form + detail page) | ✅ **SHIPPED** |
| FE-3 | Batches: new section — list lots, expiry view, opening-balance create | ✅ **SHIPPED** |
| FE-4 | Stock Movements: surface the lot (`batch_id`) on the ledger | ✅ **SHIPPED** |

### FE-0 — Type/enum foundation ✅ SHIPPED (2026-06-12)
- `types/enums.ts`: added `StorageCondition`, `MaterialClassification`,
  `Pharmacopoeia`, `DosageForm`, `DrugSchedule`, `BatchStatus`.
- `types/api.types.ts`: `Item` gains `storage_condition`/`shelf_life_days`/
  `raw_detail`/`finished_detail`; new `RawItemDetail`/`FinishedItemDetail`
  (+ `*Input`); `StockMovement` gains `batch_id`; new `Batch`/`BatchCreateRequest`;
  new `PurchaseOrderReceive*` request types. Additive — no behaviour change.

### FE-1 — PO receive → lots ✅ SHIPPED (2026-06-12)
The Backend now **requires** a per-line lot body on receive, so the old
no-body receive was broken. Fixed:
- `po.api.ts` `receivePurchaseOrder(id, body)`; `useReceivePurchaseOrder` takes
  the body; `po.schema.ts` `poReceiveSchema`; `po.transform.ts`
  `receiveDefaults` + `toReceivePayload` (replaced `receiveDeltas`).
- `ReceivePoModal` rewritten: an RHF form collecting `batch_number` (required),
  `expiry_date` (required), optional `manufacturing_date` / `storage_location`
  per line; submits `{ lines: [...] }`. Design-system fields only.
- Tests updated (po.api, po.transform, PO detail + list pages).

**Verification:** `npm run lint` clean, `tsc -b` clean, **290 tests pass**.

### FE-2 — Items pharma UI ✅ SHIPPED (2026-06-12)
- New `features/items/pharma.ts`: option lists + human label fns for the pharma
  enums (single source for selects + read views).
- `item.schema.ts`: common-pharma fields (`storage_condition`, `shelf_life_days`)
  + type-gated RAW/FINISHED detail fields (all optional).
- `item.transform.ts`: `toCreatePayload`/`toUpdatePayload` build the matching
  detail block (`toUpdatePayload` takes `type`); `itemToEditValues` seeds it.
- `ItemFormDrawer`: grouped "Storage & shelf life" + a **type-conditional**
  Raw/Finished detail section (selects, checkboxes), `watch('type')`-driven.
- `ItemDetailPage`: renders the common fields + the matching detail block with
  human labels.
- Tests: transform cases, a finished-product create flow, and detail-page
  display (raw + finished).

### FE-3 — Batches feature ✅ SHIPPED (2026-06-12)
- New `features/batches/` slice: `api` (list/get/create), `hooks`, `keys`,
  `batch.schema`, `batch.transform` (status badge map + options + payload),
  components (`BatchStatusBadge`, `BatchesTable`, `BatchesToolbar`,
  `BatchFormDrawer`), and `BatchesListPage`.
- Nav entry (`Batches`, `package` icon) + `/batches` route.
- List page: item/status/expiring-before filters, expiry + `is_expired` badge,
  status badge, pager; opening-balance create drawer (item select, batch no.,
  expiry, qty, cost, location, status) handling 404/409/422 via toasts.
- Tests: transform, form drawer (create/validation/§5.6 error toast), list page
  (render/filter/empty/open drawer).

### FE-4 — Stock Movements lot column ✅ SHIPPED (2026-06-15)
- `StockMovementsTable` gains a **Lot** column (after Item); page resolves
  `movement.batch_id` → batch number via a batches lookup (first 100), `—` when
  no lot. Mirrors the item/party resolution. Read-only.
- Test: asserts the lot number + the `Lot` column header render.

**Final verification:** `npm run verify` (lint + build) clean, **306 tests
pass**, `npm run test:coverage` passes (global 95.4% stmts / 84% branch / 82.6%
funcs). Frontend is fully aligned to `../Backend/docs/Backend_Reference.md`.

---

## Feedback round 2 — pharma UX (Batch 1: fast, safe wins) ✅ SHIPPED (2026-06-15)

From operator feedback (12 items across notes + annotated screenshots). Batch 1
delivers the low-risk, high-visibility frontend wins; the deeper batch-workflow
items (item delete, QC status transitions, adjustment-with-batch, SO batch
selection, multi-lot receive, structured-ingredient *input*) are Batch 2/3.

- **Ingredients readable** — `parseIngredients` turns the finished-product
  `ingredients` JSON into readable lines on `ItemDetailPage` (falls back to raw
  text if it isn't JSON).
- **SO line unit price auto-fills** from the selected item's catalog price
  (keeps item/SO price consistent; still editable).
- **Batch record unit cost auto-fills** from the item's price.
- **Dashboard "Recent Stock Movements"** item names are now links to item detail.
- **Required-field `*`** verified already present on the vendor/customer/item/
  batch forms (Field `required`) — no change needed.

**Verification:** `npm run lint` clean, `tsc -b` clean, **309 tests pass**,
coverage 95.3% stmts (exit 0).

## Feedback round 2 — Batch 2: multi-lot receive (#10) ✅ SHIPPED (2026-06-15)

A PO line can now be received as **several lots** (different batch numbers /
expiries arriving in one shipment), not just one.

- `ReceivePoModal` rewritten on `useFieldArray`: each PO line shows its lot
  row(s), an **Add lot** button, and a **Remove lot** button (when >1). A live
  **"Allocated X / Y"** helper turns red and the **Confirm receive** button is
  disabled until the lots' quantities allocate the full line quantity (mirrors
  the SO live-stock §5 pattern). Uses `useWatch` for reliable field-array
  reactivity.
- Each lot row gains a **Quantity** field; a single lot is seeded with the full
  line quantity (the common case — unchanged UX), so existing single-lot
  receives keep working.
- `po.transform`: `receiveDefaults` seeds the lot quantity; `toReceivePayload`
  sends per-lot `quantity`; new `emptyReceiveLot(itemId)` for "Add lot".
- Backend contract (matched): `PurchaseOrderReceiveLine.quantity` optional —
  a single lot may omit it (whole line); split lines must sum to the line qty
  (422 `RECEIVE_QUANTITY_MISMATCH`), duplicate batch per item → 409
  `DUPLICATE_BATCH`.

**Verification:** `tsc -b` clean, `eslint` clean, **312 tests pass** (3 new),
coverage 95.31% (`po.transform.ts` 100%). Backend: **257 pass** (4 new),
ruff + mypy clean.

---

## Feedback round 2 — Batch 2: SO batch selection #9 (+ #6) ✅ SHIPPED (2026-06-15)

A sales-order line can now name the **lot it ships from** — and an item's
Excel-imported stock becomes shippable by recording an opening-balance lot and
selecting it (#6).

- New **"Ship from lot"** column on the SO create line editor (`SoLineItemsEditor`):
  a Select defaulting to **Auto (FEFO)**, populated from the item's *shippable*
  lots (in stock, non-expired, earliest-expiry first). Disabled until an item is
  picked; cleared automatically when the item changes (lots are item-specific).
- `so.transform`: new `shippableLotsByItem(batches, asOf?)`; `toSoCreatePayload`
  carries `batch_id` when chosen. `so.schema` line gains `batch_id` (blank = FEFO).
- Backend contract (matched): line `batch_id` optional; blank → **FEFO,
  unchanged** (all prior ship tests stay green — non-breaking). Set → ship from
  that exact lot. Create validates existence + item-match (`404 BATCH_NOT_FOUND`,
  `422 BATCH_ITEM_MISMATCH`); ship enforces stock/expiry
  (`409 INSUFFICIENT_STOCK` / `BATCH_NOT_SHIPPABLE`).

**Verification:** `tsc -b` clean, `eslint` clean, `build` clean, **315 tests
pass** (3 new), coverage 95.34% (`so.transform.ts` 100% lines). Backend:
**263 pass** (6 new), migration `a3f9c1d27e54` reversible, ruff + mypy clean.

---

**Batch 3 carry-over (was Batch 2 next):**

---

## Feedback round 2 — Batch 3: delete · QC · adjustment-lot · ingredients ✅ SHIPPED (2026-06-15)

The remaining feedback set, all non-breaking and TDD:

- **#1 Item soft-delete** — `ItemDetailPage` gains a **Deactivate** button +
  danger confirm modal → `DELETE /items/{id}` (`useDeleteItem`); navigates back
  with a toast. Inactive items drop out of the default list (Backend filter).
- **#7 QC status transitions** — `BatchesTable` gains per-row **Release / Reject
  / Recall** actions (only the legal ones for the lot's status) →
  `POST /batches/{id}/status` (`useChangeBatchStatus`); recall/reject remove the
  lot from shipping.
- **#8 Adjustment targeting a lot** — `ManualAdjustmentModal` gains an optional
  **Lot** picker populated from the item's lots; `batch_id` flows to the payload
  so the lot quantity moves with the item total.
- **#2 Structured ingredient input** — new `IngredientsEditor` (repeatable
  name/qty/unit rows) replaces the free-text ingredients box on the item form;
  serializes to the JSON string the Backend stores (`serializeIngredients`),
  round-tripping with the detail-page renderer. Legacy free text is preserved as
  the first row.

**Verification:** `tsc -b` clean, `eslint` clean, `build` clean, **326 tests
pass** (+10), coverage 95.41%. Backend: **280 pass** (+17), ruff + mypy clean.

---

**Batch 3 (planned, decisions resolved from the PDF):** item soft-delete; QC
status transitions (release/reject/recall) + enforce RELEASED-on-ship; manual
adjustment with batch selection (updates the lot); SO line **batch selection**
(pick lot / create one when short); **multi-lot receive** (a PO line splits into
many lots); structured ingredient *input*; opening-balance batching for
Excel-imported stock. These are the backend-touching, batch-model-maturation
work (Phase 2 territory).

---

## Feedback round 3 — Items "All →" filter + ingredient picker ✅ SHIPPED (2026-06-16)

Two genuine, code-rooted bugs from the testing team's annotated PDF.

**1. Dashboard "Needs Attention → All →" showed "No items found" (pages 1 & 3).**
Two compounding causes:
- The panel lists items that are `LOW_STOCK` **or** `NO_STOCK` (the screenshot's
  items were all 0-stock = `NO_STOCK`), but the link went to `?status=low`
  (`LOW_STOCK` only) — excluding the very items it showed.
- The Items page filtered `status` **client-side over only the loaded 25 rows**,
  while the pager showed the server's *unfiltered* total → "No items found /
  1-25 of 31".

Fix — status is now a **real server filter** (needs the new Backend `status`
query param, logged in `../Backend/execution.md` Phase 1J):
- `items.api.ts`: `ListItemsParams.statuses?: ItemStatus[]`, sent as repeated
  `status` keys via axios `paramsSerializer: { indexes: null }`.
- `item.transform.ts`: `STATUS_FILTER_TO_STATUSES` maps the segmented value →
  bucket(s); new `attention` = `[LOW_STOCK, NO_STOCK]`.
- `ItemsToolbar`: new **Attention** segment (the dashboard deep-link target).
- `ItemsListPage`: passes `statuses` to the query (removed client-side
  filtering), resets offset when status changes — so rows **and** the pager
  total are now correct across the whole catalog.
- `NeedsAttention`: "All →" now deep-links to `?status=attention`.

**2. Add-Item ingredients should be picked from raw materials (page 2).**
`IngredientsEditor` ingredient name is now a **combobox over the catalog's raw
materials** (`<datalist>`): pick one and its **unit is auto-fetched** from the
item; a free-text name not in the catalog is still accepted (and its unit typed
manually). `ItemFormDrawer` fetches RAW items (`useItemsList(..., {enabled})`,
only when type=FINISHED) and feeds them in. Output JSON is unchanged, so it
round-trips with the detail-page renderer (`parseIngredients`).

**Files touched:** `features/items/api/items.api.ts`,
`features/items/hooks/useItems.ts`, `features/items/item.transform.ts`,
`features/items/components/{ItemsToolbar,IngredientsEditor,ItemFormDrawer}.tsx`,
`features/items/pages/ItemsListPage.tsx`,
`features/dashboard/components/NeedsAttention.tsx` (+ their co-located tests).

**How to test (you):** Backend running (with the Phase 1J status filter) and a
mix of in-stock / low / out-of-stock items.
```powershell
npm run dev      # log in
```
1. **Dashboard → Needs Attention → All →** lands on Items with the **Attention**
   filter active, listing exactly the low + out-of-stock items (no longer
   "No items found"); the pager total matches.
2. **Items toolbar**: OK / Low / Out / Attention now filter server-side — the
   row list and the "N of M" pager agree, across all pages.
3. **+ Add Item → Finished product → Ingredients**: the name field suggests raw
   materials; picking one auto-fills its unit; a custom name is still allowed.

**Verification:** `npm run verify` (lint + build) clean, **334 tests pass**
(+8), `npm run test:coverage` thresholds hold. Backend `pytest` 31 item tests
pass (+3).

---

## Phase 2C.1 — Intelligence foundations ✅ SHIPPED

**Goal:** the wiring every intelligence surface (2C.2–2C.7) builds on, with no
dead UI yet.

**Shipped:**
- **Connectivity** — the AI scores live in the separate **Intelligence service**
  (port 8002), not the Backend. Added `VITE_INTELLIGENCE_BASE_URL`
  (`.env.example`) + `env.intelligenceBaseUrl`. Per the agreed approach we keep
  the **single axios client**: intelligence calls pass a per-request `baseURL`
  override, so the request-ID / 401 / error-envelope contracts still apply
  (Intelligence returns the same `{error:{code,message,request_id}}` shape).
  No second HTTP client.
- **Enums** (`types/enums.ts`) mirroring the Intelligence service:
  `LeadClassification`, `HealthClassification`, `VisitPriority`.
- **`ClassificationBadge`** (`components/ui/`) — maps a classification to the
  shared `Badge` (colour **and** text, a11y §10); a `scale` discriminator
  disambiguates overlapping values (lead MEDIUM = amber vs priority MEDIUM =
  blue). 6 tests.

**Verification:** `npm run verify` clean (lint + build); **341 tests pass**;
coverage thresholds hold.

**Files:** `.env.example`, `src/config/env.ts`, `src/types/enums.ts`,
`src/components/ui/ClassificationBadge.{tsx,test.tsx}`.

**How to test (you):**
```powershell
npm run test -- ClassificationBadge      # the new badge mapping
npm run verify                           # lint + build + full suite
```
> The Intelligence service must be running on **8002** for the 2C.2+ pages to
> load scores: `cd ..\Intelligence; uv run uvicorn app.main:app --app-dir src --port 8002`.

---

## Things this app must NEVER do

Recorded here so a future session doesn't reintroduce them.

1. **Never call `fetch` directly for app traffic.** Use the shared axios
   instance from `src/lib/api/client.ts`. Adding a second HTTP client
   breaks the request-ID and 401 contracts.
2. **Never `console.*` outside `src/lib/logger.ts`.** Logger is the
   only sink — it's where redaction lives and where future remote
   logging hooks in.
3. **Never edit `src/types/api.types.ts` to "fix" a type mismatch with
   the Backend.** The Backend is the source of truth. If types mismatch,
   either fix the call site or open the Backend reference and update
   the type to mirror reality.
4. **Never show a danger toast without a Request ID** (when one is
   available — `ApiError.requestId` always is for Backend errors). This
   is the §5.6 non-negotiable.
5. **Never silently retry a mutation.** Surface the failure with its
   server code so the user can act.
6. **Never store auth tokens in a global JS variable.** Use
   `auth/token-storage.ts` (which uses localStorage) — only place
   tokens live.
7. **Never bypass the design system.** No inline `style={{…}}` for
   colours, spacing, radius, or typography. Use the CSS classes from
   `globals.css` or extend the design system.
