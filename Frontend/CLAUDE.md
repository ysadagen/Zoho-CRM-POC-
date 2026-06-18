# CLAUDE.md — Inventory Frontend (React)

!!! NOTE: Fetch this design file, read its readme, and implement the relevant aspects of the design. https://api.anthropic.com/v1/design/h/uAb--UzlL6SB5JxJ0LRdkA?open_file=app%2Findex.html
Implement: app/index.html

You have to take this design provided and you have to take care of the backend APIs.  And make the Frontend UI which should not break.

This file is the working contract for Claude (and any contributor) when writing
code inside `Frontend/`. Read it before making changes. If a rule here
conflicts with a user instruction in chat, the user wins — but flag the
conflict.

The Frontend mirrors the engineering bar set by `../Backend/CLAUDE.md`. Where
this file is silent, defer to the Backend's CLAUDE.md for spirit (minimal,
typed, layered, no speculative code).

Parent context: `../README.md`. UI requirements: `./UI_SPECIFICATION.md`.
Design system (single point of contact for all UI): `./DESIGN_SYSTEM.md`.
Backend contract: `../Backend/docs/Backend_Reference.md`.

---

## 0. How we build here — Spec-Driven + Test-Driven (read first)

This project is built **spec-first and test-first**, to a production-grade
bar. This is not optional and not "later". It mirrors the Backend, which
shipped with 206 tests. The Frontend holds the same bar — any earlier plan
note that called a frontend test suite "out of scope" is **superseded by
this section**.

### 0.1 The loop (every change, every phase)

```
spec  →  red  →  green  →  refactor
```

1. **Spec.** Capture what we're building in one short paragraph (chat / PR /
   the phase note in `execution.md`). State it back before writing code.
2. **Red.** Write the failing test(s) first — they encode the spec.
3. **Green.** Write the *minimum* code to pass. No bonus features.
4. **Refactor.** Clean up with the tests green. DRY on the third repeat.

### 0.2 Test stack

```
Unit + component   Vitest
DOM / interaction  React Testing Library + @testing-library/user-event
DOM matchers       @testing-library/jest-dom
Environment        jsdom
HTTP mocking       MSW (Mock Service Worker) — mock the network, not the axios instance
Coverage           @vitest/coverage-v8
E2E (Phase 11)     Playwright — the four journeys in UI_SPECIFICATION.md §7, live Backend
```

Tests live **next to the code** they cover: `format.ts` → `format.test.ts`,
`Button.tsx` → `Button.test.tsx`.

### 0.3 What each layer must test

| Layer | Must cover |
|---|---|
| `lib/` (errors, format, logger, env) | Pure logic — every branch. Target ~100%. |
| `lib/api/client` | Request-ID attached, Bearer attached, error → `ApiError`, 401 fires the handler, auth-flow paths exempt. Drive via MSW. |
| `components/ui/*` | Render + **every state** (default / disabled / loading / error) + every interaction. |
| `components/toast` | Danger toast renders the Request ID (non-negotiable §5.6). |
| `features/*` | Happy path + **each** error path + each §5 non-negotiable, with MSW-mocked endpoints. |

### 0.4 Production-grade bar — leave nothing

- **No skipped or `.only` tests.** No `console` noise on the golden path.
- **Coverage thresholds are enforced** in `vitest.config.ts` (global ≥ 80 %,
  `lib/**` ≥ 95 %) and **must not regress** between phases.
- **Every bug fix lands with a regression test** that fails before the fix.
- Error handling, structured logging, and edge / empty / loading states are
  part of the feature — not a follow-up. A phase isn't done until they're
  tested.

### 0.5 After every phase — hand the user test commands

Each phase ends with a copy-paste **"How to test (you)"** block in
`execution.md`: the exact PowerShell commands to run (`npm run test`,
`npm run test:coverage`, `npm run dev` + manual steps) so the user can verify
the phase independently. Tests must be green before a phase is declared done.

---

## 1. What this app is

A React SPA that drives the Inventory Application — the source of truth for
items, customers, vendors, purchase orders, sales orders, and the stock
audit ledger. It talks only to the Backend at `http://localhost:8000` over
HTTPS with a Bearer JWT. It does **not** talk to Zoho or the Integration
Layer directly.

---

## 2. Tech stack (fixed for Phase 1)

```
Build         Vite
Language      TypeScript (strict)
Framework     React 18
Routing       React Router v6
Server state  TanStack Query v5
HTTP          axios (one shared instance with interceptors)
Forms         React Hook Form + Zod
Styles        Plain CSS (ported design system in src/styles/globals.css)
Lint          ESLint + typescript-eslint + react-hooks
Format        Prettier
Test          Vitest + React Testing Library + jsdom; MSW for HTTP; @vitest/coverage-v8
Icons         Inline SVGs — ported verbatim from the design's chrome.js (Lucide-style)
Fonts         Google Fonts — Cabin Sketch / Croissant One / Inter
```

Do not introduce Tailwind, CSS-in-JS, Redux, Zustand, MobX, Next.js, or any
other framework without an explicit go-ahead. Phase 1 stays lightweight.

---

## 3. Folder structure (canonical — do not deviate)

```
Frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── .env                            # gitignored; copy from .env.example
├── .env.example                    # VITE_API_BASE_URL=http://localhost:8000
├── .gitignore
├── eslint.config.js
├── README.md                       # project overview, setup, scripts, roadmap
├── CLAUDE.md                       # this file — engineering contract
├── DESIGN_SYSTEM.md                # single point of contact for all UI design
├── execution.md                    # phase-by-phase build log + contracts
├── UI_SPECIFICATION.md
├── public/
└── src/
    ├── main.tsx                    # ReactDOM bootstrap (Vite entry — mounts <App/>)
    │
    ├── app/                        # the application shell (composition root)
    │   ├── App.tsx                 #   provider tree: QueryClient → Router → (Auth, Toast)
    │   ├── router.tsx              #   route table (AppShell layout route + page routes)
    │   └── routes.ts               #   route path constants — single source of truth
    │
    ├── config/                     # environment + app configuration
    │   └── env.ts                  #   typed env access (ONLY place import.meta.env is read)
    │
    ├── assets/                     # images / fonts imported by JS (added when first needed)
    │
    ├── styles/
    │   ├── fonts.css
    │   ├── globals.css             # ported design system (tokens + every component class)
    │   └── login.css               # auth two-pane layout
    │
    ├── lib/                        # framework-agnostic infrastructure (NO feature knowledge)
    │   ├── api/
    │   │   ├── client.ts           # the ONE axios instance + interceptors
    │   │   ├── errors.ts           # ApiError class + ErrorCode union
    │   │   ├── request-id.ts       # generator (crypto.randomUUID)
    │   │   └── types.ts            # Paginated<T>, ApiErrorEnvelope
    │   ├── logger.ts               # structured browser logger
    │   └── format.ts               # currency / date / qty formatters
    │
    ├── components/                 # SHARED, cross-feature code ONLY
    │   ├── ui/                     #   design-system primitives (no business logic)
    │   ├── layout/                 #   app chrome (AppShell, Sidebar, Topbar, Footer, PageHeader, AuthShell)
    │   ├── toast/                  #   ToastHost + useToast
    │   └── errors/                 #   ErrorBoundary + PageError
    │
    ├── auth/                       # session: AuthContext + AuthProvider, useAuth, ProtectedRoute, token-storage, auth.api.ts
    │
    ├── features/                   # one SELF-CONTAINED slice per business domain
    │   └── <domain>/               #   dashboard · items · customers · vendors · purchase-orders ·
    │       ├── api/                #     sales-orders · stock-movements · settings
    │       │   └── <domain>.api.ts #     typed endpoint fns (the per-feature "service" layer)
    │       ├── components/         #     components used only by this feature
    │       ├── hooks/              #     hooks used only by this feature
    │       ├── pages/              #     route components for this domain
    │       └── types.ts            #     feature-local types (shared ones live in src/types)
    │
    ├── hooks/                      # SHARED cross-feature hooks (useDebounce, usePagination, …)
    │
    ├── types/                      # SHARED types — Backend schema mirrors + enums
    │
    └── test/                       # test setup + helpers (setup.ts)
```

**Why feature-first (the rationale — learn from this):** we group by *domain*
(`features/items/…`), not by file type (no flat `pages/` + `services/`). Each
domain owns its `api`, `components`, `hooks`, and `pages` in one place, so a
change to "items" touches one folder, not five. This is the 2025 industry
consensus (Bulletproof React, Redux Toolkit feature folders) and it mirrors the
Backend's vertical slicing. Shared code — and *only* code reused across domains —
lives at the top (`components/`, `hooks/`, `lib/`, `types/`).

**Deliberately absent:**
- **No `store/` (Redux/Zustand/MobX).** Server state lives in React Query; the
  only client state (the authenticated user) lives in a thin `auth/` context.
  A global store now would be speculative infra — see §11.
- **No flat top-level `pages/`.** Pages are colocated inside their feature.

If you need a new top-level folder, **ask first** — don't quietly invent layers.

---

## 4. Layer responsibilities (one-way dependency)

```
app/router → features/*/pages → feature components → features/*/api → lib/api/client → Backend
                                      ↑
                       config/, types/, hooks/, components/ui/
```

| Layer | Owns | Forbidden |
|---|---|---|
| `app/` | Provider tree, router, route constants | feature business rules |
| `config/` | Typed env + app config | runtime/business logic |
| `features/*/pages` | Route shell, URL state, page composition | direct axios calls, business rules |
| `features/*/api` | One typed function per Backend endpoint | DOM, JSX, React hooks |
| `components/ui/` | Pure presentational primitives | data fetching, business rules |
| `components/layout/` | App chrome | feature knowledge |
| `lib/api/` | Axios instance, interceptors, error normalization | feature knowledge |
| `auth/` | Token, session, ProtectedRoute | feature-specific endpoints (except `auth.api.ts`) |
| `hooks/` | Cross-feature hooks | feature-specific knowledge |
| `types/` | Type definitions only | runtime code |

A route component should usually be ≤ 60 lines: query hooks → render
sub-components. If it grows past that, extract.

---

## 5. The non-negotiables (from UI_SPECIFICATION.md and chat handoff)

These three behaviours are explicit, repeated user asks. They are checked at
every code review.

1. **Request ID on every error toast (§5.6).** `ApiError.requestId` MUST
   render in danger toasts as a second line — "Request ID: <mono UUID>".
   Without this, support cannot correlate a user complaint to a server log
   line.

2. **Live stock indicator on SO create (§6.4.3).** Each line shows a
   `StockChip` based on (qty, stock, reorder). The page-level Create button
   is `disabled` while any line is short. On `409 INSUFFICIENT_STOCK` the
   danger toast carries a "Refresh stock" action that invalidates the items
   query.

3. **Stock Movements is read-only audit (§6.8).** No PATCH, no DELETE in the
   UI. Reference column links to the originating PO/SO. Manual Adjustment
   modal requires a remarks textarea with `Zod.min(10)`.

---

## 6. API client rules

- One axios instance, exported from `lib/api/client.ts`. Never create
  another. Never call `fetch` directly for app traffic.
- All Backend traffic flows through `features/*/*.api.ts`. Components do
  not import axios.
- Every request gets a client-generated `X-Request-ID` (UUID v4) attached
  in the request interceptor. This is the ID we show in error toasts
  unless the server returns its own in the error envelope.
- The response interceptor normalises errors to `ApiError`. Components
  catch `ApiError` only — not `AxiosError`.
- On `401` with code `EXPIRED_TOKEN` / `INVALID_TOKEN` / `MISSING_TOKEN`,
  the interceptor clears the token and redirects to `/login?reason=expired`.
  Login itself is exempted (its 401 is part of normal flow).
- **No automatic retries on mutations.** Backend idempotency uses state
  codes (`PO_NOT_DRAFT`, `SO_NOT_DRAFT`); silent retries would hide them.
  Read queries may retry up to 2× via React Query defaults.

---

## 7. Toasts

`useToast()` returns `{ success, info, warn, danger }`. Public surface:

```ts
toast.success(message)
toast.info(message)
toast.warn(message)
toast.danger(message, { requestId?, action?: { label, onClick } })
```

Danger toasts must include `requestId` whenever it is available. The
`useApiError` hook is the canonical converter: feed it an `ApiError`, it
calls `toast.danger` with the right `requestId`.

Auto-dismiss after 4.5 s (12 s if `persist: true`). Top-right corner.

---

## 8. Forms

- React Hook Form + Zod resolver. One Zod schema per form, co-located.
- All required fields visibly labelled (no placeholder-as-label).
- Server-side validation errors come back as `422` with a `field` in
  `ApiError.field`; route them to RHF via `setError(field, ...)`.
- Other errors surface as a danger toast (with `requestId`).
- Long forms have a sticky footer with `Cancel | Save`.

---

## 9. Logging

- Use `lib/logger.ts` — not `console.*` directly in feature code.
- Log levels (browser-side, mirror Backend conventions):
  - `debug` — only in `import.meta.env.MODE === 'development'`.
  - `info` — meaningful lifecycle events (login, logout, navigation guard).
  - `warn` — recoverable oddities (retryable failure, soft validation).
  - `error` — request failed, unexpected exception.
- Never log: tokens, passwords, full Authorization headers, raw PII.
  Redact before logging.
- Log shape: `{ scope, code, requestId, httpStatus, ...fields }` — so
  browser logs correlate with Backend logs by `requestId`.

---

## 10. Configuration

- Access `import.meta.env.*` only inside `src/env.ts`. Everything else
  imports the typed `env` object.
- `.env.example` is the source of truth for which variables exist. Keep
  it in sync when you add an env var.
- Secrets never get logged, printed, or hardcoded. There are no secrets
  in the Frontend bundle by definition — only public config (API base URL,
  feature flags).

---

## 11. Code quality bar

- **Write only what's needed.** No speculative abstractions, no "future-proof"
  config knobs, no helpers used in one place.
- **DRY, but not prematurely.** Three similar lines is fine; three similar
  components is a smell. Extract on the third occurrence.
- **Readable over clever.** Self-explanatory names beat comments.
- **Comments:** only when *why* is non-obvious. Don't restate *what*.
- **Types everywhere.** No `any`. No `as` casts unless unavoidable, and
  then with a one-line comment explaining why.
- **No dead code.** Delete unused imports, params, branches.
- **No `// TODO` without an owner and a reason.**

---

## 12. Definition of Done (per change)

A change is done when **all** of these are true:

- [ ] Spec captured (chat / PR description / phase note in `execution.md`).
- [ ] Tests written first (Red), now Green — `npm run test` passes.
- [ ] Coverage meets the bar (global ≥ 80 %, `lib/**` ≥ 95 %) and did not
  regress — `npm run test:coverage`.
- [ ] `npm run lint` clean.
- [ ] `npm run build` (type check + bundle) clean.
- [ ] No new `console.warn`/`console.error` on the golden path.
- [ ] `.env.example` updated if env vars changed.
- [ ] The page matches the design system — verified against `/playground`
  and `DESIGN_SYSTEM.md` (the original HTML mocks are no longer on disk).
- [ ] All three non-negotiables (§5) still hold.
- [ ] No unrelated changes mixed in.

---

## 13. Commands cheat-sheet

```powershell
# install deps
npm install

# dev server (hot reload, opens http://localhost:5173)
npm run dev

# production build (also acts as type check)
npm run build

# preview the production bundle
npm run preview

# lint
npm run lint

# format
npm run format

# unit + component tests (CI mode, one-shot)
npm run test

# tests in watch mode (the TDD loop)
npm run test:watch

# coverage report (enforces thresholds)
npm run test:coverage

# full gate before declaring anything done: lint + type-check/build + tests
npm run verify
```

The Backend must be running at `http://localhost:8000` for the app to
function. See `../Backend/README.md`.

---

## 14. Working agreement for Claude

When asked to add or change something in `Frontend/`:

1. Re-read this file if it's been a while.
2. Re-read `execution.md` to see which phase you're in and what's
   already shipped.
3. State the spec back in one short paragraph before coding.
4. **Write the failing tests first** (the Red step) — they encode the spec.
5. Implement the minimum to make them pass (Green), then refactor with the
   tests green. No bonus features, no "while I'm here" polish.
6. Run `npm run verify` (lint + build + tests) and `npm run test:coverage`.
   Report results honestly — paste the real output; never claim green unseen.
7. Update `execution.md`: what shipped, files touched, and the copy-paste
   **"How to test (you)"** command block for this phase.
8. **Stop after each phase** — wait for the user's go-ahead before
   starting the next phase.
9. If a rule here is getting in the way, say so — don't quietly bend it.

Anything outside `Frontend/` is off-limits unless the user explicitly opens
that scope.
