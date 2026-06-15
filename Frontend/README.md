<div align="center">

# Adagen Inventory Manager : Frontend

**A clean, data-dense React SPA for back-office inventory operations.**
Raw materials, finished products, vendors, customers, purchase & sales orders,
and an append-only stock audit ledger — backed by the Inventory API.

`React 18` · `TypeScript (strict)` · `Vite` · `TanStack Query` · `React Router` · `Axios` · `React Hook Form + Zod`

**Status:** Phase 1 POC — under active, phase-by-phase development.

</div>

---

## Table of contents

- [Overview](#overview)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Environment variables](#environment-variables)
- [Available scripts](#available-scripts)
- [Testing (TDD)](#testing-tdd)
- [Design system](#design-system)
- [Engineering conventions](#engineering-conventions)
- [The three non-negotiables](#the-three-non-negotiables)
- [Project status & roadmap](#project-status--roadmap)
- [Where this fits](#where-this-fits-in-the-system)
- [Key documents](#key-documents)

---

## Overview

This is the user-facing application for a manufacturing business that buys raw
materials from vendors, manufactures finished products, and sells them to
customers. The app is the **source of truth for stock** — every quantity change
is recorded as an immutable stock movement and shown in an audit ledger.

It is a **back-office tool**: professional, calm, and data-dense (Linear /
Stripe / Notion in spirit — not a consumer app). It talks **only** to the
Inventory Backend over HTTP with a Bearer JWT; it does **not** talk to Zoho CRM
or the Integration Layer directly. Customer/vendor relationship history lives in
Zoho CRM and is intentionally out of scope here.

**Primary user journeys** (the flows the UI is optimised for):

1. Create a sales order against live stock — in under 30 seconds for a 2-line order.
2. Receive a purchase order and confirm stock went up — one screen, three clicks.
3. Investigate a stock figure via the audit ledger and follow it to its source PO/SO.
4. Add a new item / customer / vendor — one form, no surprises.

---

## Tech stack

| Concern | Choice | Why |
|---|---|---|
| Build | **Vite** | Fast dev server + native ESM, first-class TS/React |
| Language | **TypeScript (strict)** | `strict`, `noUncheckedIndexedAccess`, no `any` |
| UI | **React 18** | Industry standard; concurrent-ready |
| Routing | **React Router v6** | SPA routing, protected routes |
| Server state | **TanStack Query v5** | Caching, retries, invalidation — no hand-rolled fetch state |
| HTTP | **Axios** (one shared instance) | Interceptors for auth + request-ID + error normalization |
| Forms | **React Hook Form + Zod** | Typed schemas, field-level validation mirroring the API |
| Styling | **Plain CSS + design tokens** | The handed-off design system is the contract; see [Design system](#design-system) |
| Lint / format | **ESLint + typescript-eslint** / **Prettier** | Consistent, enforced style |
| Test | **Vitest + React Testing Library + jsdom + MSW** | Spec-/test-driven; see [Testing](#testing-tdd) |

> **Deliberately not used:** Tailwind, CSS-in-JS, Redux/Zustand/MobX, Next.js.
> The design ships as a complete CSS system and there's no client-state
> complexity beyond what React Query + a thin `AuthContext` cover. Adding any of
> these requires an explicit go-ahead.

---

## Architecture

A strict, **one-way layered** dependency graph — the same discipline as the
Backend. Each layer knows only about the layer below it.

```
pages  →  feature components  →  feature.api.ts  →  lib/api/client  →  Backend
                                  ↑
                          types/ · hooks/ · components/ui/
```

| Layer | Owns | Must not |
|---|---|---|
| `features/*/pages` | Route shell, URL state, composition | Call axios directly; hold business rules |
| `features/*/*.api.ts` | One typed fn per Backend endpoint | DOM, JSX, React hooks |
| `components/ui/` | Pure presentational primitives | Data fetching, business rules |
| `components/layout/` | App chrome | Feature knowledge |
| `lib/api/` | Axios instance, interceptors, error normalization | Feature knowledge |
| `auth/` | Token, session, `ProtectedRoute` | Feature endpoints (except `auth.api.ts`) |
| `types/` | Type definitions mirroring Backend schemas | Runtime code |

**Cross-cutting guarantees** (wired in `lib/`):

- **One axios instance.** Every request carries a client-generated
  `X-Request-ID`; the response interceptor normalizes *all* errors to a single
  `ApiError` type — components never see an `AxiosError`.
- **Auth.** Bearer token injected per request; a `401` with an auth-failure code
  clears the session and redirects to `/login` (login/register flows exempted).
- **No silent retries on mutations** — the Backend's idempotency surfaces as
  state codes (`PO_NOT_DRAFT`, `SO_NOT_DRAFT`), which the user must see.
- **Structured logging** through a single `logger` sink with secret redaction —
  no stray `console.*` in feature code.

---

## Project structure

```
Frontend/
├── index.html
├── package.json · vite.config.ts · tsconfig*.json · eslint.config.js · .prettierrc.json
├── .env.example                     # copy to .env; VITE_API_BASE_URL, VITE_APP_ENV
├── CLAUDE.md                        # engineering contract (read before contributing)
├── DESIGN_SYSTEM.md                 # the single point of contact for all UI design
├── UI_SPECIFICATION.md              # per-page field/state requirements
├── execution.md                     # phase-by-phase delivery log
├── public/
└── src/
    ├── main.tsx                     # entry — QueryClient, Router, AuthProvider, ToastHost
    ├── App.tsx                      # router root
    ├── env.ts                       # the only place import.meta.env is read
    ├── styles/                      # fonts.css · globals.css (design system) · login.css
    ├── lib/
    │   ├── api/                     # client.ts · errors.ts · request-id.ts · types.ts
    │   ├── logger.ts                # structured browser logger (redacts secrets)
    │   └── format.ts                # currency / date / qty formatters
    ├── auth/                        # AuthContext · ProtectedRoute · token-storage · auth.api.ts
    ├── components/
    │   ├── ui/                      # design-system primitives (Button, Input, Badge, DataTable, …)
    │   ├── layout/                  # AppShell, Sidebar, Topbar, Footer, PageHeader, AuthShell
    │   ├── toast/                   # ToastHost + useToast
    │   └── errors/                  # ErrorBoundary + PageError
    ├── features/                    # one folder per domain: items, customers, vendors,
    │   │                            #   purchase-orders, sales-orders, batches, stock-movements, …
    ├── hooks/                       # cross-feature hooks (useDebounce, usePagination, …)
    └── types/                       # hand-typed mirrors of Backend schemas + enums
```

> The folder layout is **canonical** (`CLAUDE.md §3`). New top-level folders
> require a discussion first.

---

## Getting started

### Prerequisites

- **Node.js ≥ 20** and npm
- The **Inventory Backend** running locally (this app is useless without it)

### 1 — Start the Backend

From `Code/Backend/` (see its README for full setup):

```powershell
uv run uvicorn app.main:app --reload --app-dir src --port 8000
```

It should be reachable at `http://localhost:8000` (resource endpoints live under
`/api/v1`; `/health` is unprefixed).

### 2 — Install & configure the Frontend

```powershell
# from Code/Frontend/
npm install
Copy-Item .env.example .env      # then edit if your Backend isn't on the default URL
```

### 3 — Run the dev server

```powershell
npm run dev
```

Opens at **http://localhost:5173**. With the Backend up, you'll see a live
health probe succeed (Phase 0 boot screen until Phase 1+ lands the real UI).

---

## Environment variables

All Frontend config is **public** (it ships in the JS bundle) — never put
secrets here. `.env.example` is the source of truth for which variables exist;
`import.meta.env` is read **only** in `src/env.ts`.

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Base URL of the Inventory Backend (no trailing slash) |
| `VITE_APP_ENV` | `dev` | UI environment label shown in the chrome — `dev` \| `staging` \| `prod` |

---

## Available scripts

```powershell
npm run dev            # dev server with hot reload (http://localhost:5173)
npm run build          # type-check (tsc -b) + production bundle
npm run preview        # serve the production build locally
npm run lint           # ESLint
npm run format         # Prettier --write

# Testing (lands in Phase 0.5 — see roadmap)
npm run test           # Vitest, one-shot (CI mode)
npm run test:watch     # Vitest watch (the TDD loop)
npm run test:coverage  # coverage report; enforces thresholds
npm run verify         # lint + build + test — the full gate before "done"
```

---

## Testing (TDD)

This project is **spec-driven and test-driven** — the same bar as the Backend
(which shipped with 206 tests). It is not optional.

**The loop, every change:** `spec → red → green → refactor`. State the spec,
write the failing test first, implement the minimum to pass, then refactor with
tests green.

**Stack:** Vitest (runner) · React Testing Library + `user-event` (component &
interaction) · jsdom (environment) · **MSW** (mock the network, never the axios
instance) · `@vitest/coverage-v8` (coverage).

**Coverage bar (enforced, must not regress):** global ≥ 80 %, `lib/**` ≥ 95 %.

**What each layer must cover:**

| Layer | Tests |
|---|---|
| `lib/` (errors, format, logger, env) | Pure logic — every branch (~100 %) |
| `lib/api/client` | Request-ID + Bearer attached, error → `ApiError`, 401 handler, auth-flow exemption (via MSW) |
| `components/ui/*` | Render + every state (default/disabled/loading/error) + interactions |
| `features/*` | Happy path + each error path + each non-negotiable (MSW-mocked) |

Tests are co-located: `format.ts` → `format.test.ts`, `Button.tsx` →
`Button.test.tsx`. No skipped/`.only` tests; every bug fix lands with a
regression test. Full rules in `CLAUDE.md §0`.

---

## Design system

**`DESIGN_SYSTEM.md` is the single point of contact for everything visual.**
Read it before adding any colour, spacing, font, or component.

The system is layered: **design tokens** (CSS custom properties in
`src/styles/globals.css`) → **component classes** (`globals.css`) → **React
primitives** (`src/components/ui/*`) → a **living `/playground` gallery** that
renders every component and state. The brand is locked to **Bone / Ink / Ember /
Amber** with **Cabin Sketch** (logo), **Croissant One** (titles), and **Inter**
(everything else).

> **Golden rule:** no inline `style={{…}}` for colour, spacing, radius, or
> typography — use a token or an existing class. See `DESIGN_SYSTEM.md`.

---

## Engineering conventions

`CLAUDE.md` is the working contract. In short:

- **Write only what's needed** — no speculative abstractions or unused knobs.
- **Strict types everywhere** — no `any`, no unexplained casts.
- **Real error handling & structured logging** — not decorative.
- **Self-explanatory code** — names over comments; comment *why*, not *what*,
  and only where the logic is genuinely complex.
- **DRY on the third repeat**, not before.
- **No dead code**, no `TODO` without an owner.

Definition of Done for any change: spec captured · tests written first and green
· coverage holds · `npm run lint` + `npm run build` clean · non-negotiables
intact · `execution.md` updated.

---

## The three non-negotiables

Repeated, explicit requirements — checked at every review:

1. **Request ID on every error toast.** `ApiError.requestId` renders as a second
   line in danger toasts so a user complaint correlates to a server log line.
2. **Live stock indicator on SO create.** Each line shows a stock chip
   (enough / short / below-min); the Create button is disabled while any line is
   short; a `409 INSUFFICIENT_STOCK` offers a "Refresh stock" action.
3. **Stock Movements is a read-only audit ledger.** No edit, no delete; the
   reference column links to the originating PO/SO; manual adjustments require a
   ≥ 10-char reason.

---

## Project status & roadmap

Delivered **one phase at a time**; each phase leaves the app green (`npm run
verify` passes) and ends with copy-paste verification steps in `execution.md`.

| # | Phase | Status |
|---|---|---|
| 0 | Scaffold (Vite + TS, API client, design tokens, typed contract) | ✅ shipped |
| 0.5 | Test harness (Vitest + RTL + MSW + coverage) + Phase 0 backfill | ✅ shipped |
| 1 | Design-system primitives + layout shell + toast/error infra | ✅ shipped |
| 2 | Auth (login + register) | ✅ shipped |
| 3 | Dashboard (live data) | ✅ shipped |
| 4 | Items (list + detail + form drawer) | ✅ shipped |
| 5 | Customers | ✅ shipped |
| 6 | Vendors (+ supplied-items terms) | ✅ shipped |
| 7 | Purchase Orders (+ receive flow) | ✅ shipped |
| 8 | Sales Orders (+ live stock + ship flow) | ✅ shipped |
| 9 | Stock Movements (read-only ledger + manual adjustment) | ✅ shipped |
| 10 | Settings (profile + edit name) | ✅ shipped |
| 11 | Polish (error boundary, README, review) | ✅ shipped |
| FE-0…4 | **Pharma alignment** — item raw/finished detail blocks + common-pharma fields, **Batches** (lots) section, PO receive-into-lots, lot column on the ledger | ✅ shipped |

> All domains are wired to the live Backend with full create/detail/action
> flows, **306 tests** and coverage held at **≥ 80 % global / 95 %+ `lib/`**.
> The **pharmaceutical-inventory** model is surfaced end-to-end: items carry
> raw/finished pharma attributes, lots (`Batches`) are created (opening-balance +
> PO receive) and tracked by expiry/status, and every stock movement is
> lot-linked. See `execution.md` (the "Pharma alignment" section) for the
> per-phase delivery log + verification steps.

---

## Where this fits in the system

This is one of three services in the Zoho CRM POC:

- **Frontend** (this repo) — React SPA; the operations UI.
- **Backend** — FastAPI; the **source of truth** for all inventory data.
- **Integration Layer** — FastAPI; owns the Zoho CRM sync (built last).

The Frontend depends only on the Backend. Zoho sync status surfaces in the UI as
read-only badges once the Integration Layer is connected (a later phase).

---

## Key documents

| Document | Purpose |
|---|---|
| `CLAUDE.md` | Engineering contract — read before contributing |
| `DESIGN_SYSTEM.md` | Single point of contact for all UI design |
| `UI_SPECIFICATION.md` | Per-page fields, states, and behaviours |
| `execution.md` | Phase-by-phase delivery log + verification steps |
| `../Backend/docs/Backend_Reference.md` | Authoritative API contract (endpoints, errors, pagination) |

---

<div align="center">
<sub>Adagen Inventory Manager · Phase 1 POC · Proprietary — internal use only.</sub>
</div>
