# Design System — Adagen Inventory Manager

**This file is the single point of contact for everything visual in the
Frontend.** Before you add a colour, a spacing value, a font size, or a new
component, look here first. If what you need isn't in the system, extend the
system here (and in `globals.css`) — never hardcode a one-off value in a
component.

> **Golden rule:** No inline `style={{…}}` for colour, spacing, radius, or
> typography. Use a design token (CSS variable) or an existing class. This is
> enforced at code review (`CLAUDE.md §11`, `execution.md` "never do #7").

---

## 1. How the system is layered

```
┌─────────────────────────────────────────────────────────────┐
│  DESIGN_SYSTEM.md   ← you are here: the catalog + the rules   │
└─────────────────────────────────────────────────────────────┘
        │ documents
        ▼
┌───────────────┐   ┌────────────────────┐   ┌────────────────┐
│  Tokens       │ → │  Component classes │ → │ React          │
│  :root vars   │   │  .btn .card .badge │   │ components/ui/*│
│  globals.css  │   │  globals.css       │   │ <Button/> …    │
└───────────────┘   └────────────────────┘   └────────────────┘
                                                      │ rendered in
                                                      ▼
                                            ┌────────────────────┐
                                            │  /playground route  │
                                            │  living visual gallery
                                            └────────────────────┘
```

| Layer | Where | Source of truth for |
|---|---|---|
| **Tokens** | `src/styles/globals.css` → `:root` | Colour, sizing, radius — the *only* place raw hex/px live |
| **Component classes** | `src/styles/globals.css`, `src/styles/login.css` | How each component looks |
| **Fonts** | `src/styles/fonts.css` | The three brand typefaces |
| **React primitives** | `src/components/ui/*` (Phase 1) | The typed, reusable API over the classes |
| **Living gallery** | `/playground` route (Phase 1, removed Phase 11) | Visual QA of every primitive and state |
| **This catalog** | `DESIGN_SYSTEM.md` | What exists, what it's for, how to use it |

**Why plain CSS + tokens (not Tailwind / CSS-in-JS):** the design was handed
off as a locked CSS design system whose class names and CSS variables *are*
the contract. Porting it verbatim keeps pixel parity for free and avoids
re-encoding the same tokens in a second system. See the plan's "Rejected
alternatives".

---

## 2. Brand

The brand is locked to four named colours and three typefaces.

| Name | Token | Hex | Meaning |
|---|---|---|---|
| **Bone** | `--bg` | `#f1f2ed` | App background — calm, warm neutral |
| **Ink** | `--ink` | `#393949` | Primary text, sidebar, dark surfaces |
| **Ember** | `--danger` | `#bd4d35` | Destructive / error / "out of stock" |
| **Amber** | `--accent` | `#eeaa42` | Brand primary action, focus, highlights |

Tone: **professional, calm, data-dense** — Linear / Stripe / Notion, not B2C.
Light theme only (no dark mode in Phase 1).

---

## 3. Colour tokens (the full palette)

All defined in `globals.css :root`. **Never use a raw hex in a component** —
reference the token.

### 3.1 Surfaces & background

| Token | Hex | Use |
|---|---|---|
| `--bg` | `#f1f2ed` | Page background (Bone) |
| `--bg-2` | `#e9ead8` | Subtle fills, segmented-control track, ghost-button hover |
| `--bg-3` | `#e1e2d2` | Deeper fill (rare) |
| `--card` | `#ffffff` | Card / table / input surface |

### 3.2 Text & ink scale

| Token | Hex | Use |
|---|---|---|
| `--ink` | `#393949` | Primary text, headings |
| `--ink-2` | `#5a5a6e` | Secondary text, labels |
| `--ink-3` | `#8a8a9a` | Muted text, hints, placeholders |
| `--ink-4` | `#b6b6c0` | Faintest text, separators in crumbs |

### 3.3 Lines

| Token | Hex | Use |
|---|---|---|
| `--line` | `#e3e4dc` | Default borders, dividers, table rules |
| `--line-2` | `#d6d7cc` | Input / control borders (slightly stronger) |

### 3.4 Semantic colours

Each has a base, and most have `-soft` (fill) and `-tint` (faint fill) variants.

| Role | Base | Soft | Tint | Used for |
|---|---|---|---|---|
| **Accent / Amber** | `--accent` `#eeaa42` | `--accent-soft` `#fbe3ba` | `--accent-tint` `#fdf1d8` | Primary buttons, focus ring, active nav, "below min" |
| **Danger / Ember** | `--danger` `#bd4d35` | `--danger-soft` `#f6dcd3` | `--danger-tint` `#fbe9e2` | Errors, destructive, OUT/short stock |
| **Success** | `--success` `#4f8a5b` | `--success-soft` `#d8e8d9` | — | OK stock, RECEIVED, IN movement, synced |
| **Info** | `--info` `#4a6fa5` | `--info-soft` `#dde6f1` | — | RAW item type, informational toasts |
| `--accent-2` | `#d99230` | hover for amber, text-button colour |
| `--danger-2` | `#a23d28` | hover for danger |

> **Contrast:** every text-on-fill pairing in the badge/chip classes was chosen
> for WCAG AA (≥ 4.5:1). If you introduce a new fill, re-check contrast.

---

## 4. Typography

Loaded in `fonts.css` from Google Fonts with `display=swap`.

| Family | Token usage | Where | Weights |
|---|---|---|---|
| **Cabin Sketch** | `'Cabin Sketch', cursive` | **Logo only** (sidebar brand, auth brand) | 400, 700 |
| **Croissant One** | `'Croissant One', serif` | Titles, page `<h1>`, card `<h3>`, KPI values, modal `<h2>` | 400 |
| **Inter** | `'Inter', system-ui, sans-serif` | Everything else: body, UI, tables, numbers | 300–700 |

**Rules**

- **Cabin Sketch is the logo typeface. Never** use it for content.
- Titles use **Croissant One at weight 400** — it's a display serif; don't bold it.
- Numbers / SKUs / IDs use **Inter with tabular figures** — add the `mono`
  class (`font-feature-settings: 'tnum'`), right-align numeric columns.
- Body base is `14px`, `--ink`, on `--bg`.

### Type scale (observed, in px)

| Context | Size | Family |
|---|---|---|
| Page title `.page-head h1` | 30 | Croissant One |
| Modal title / drawer title | 18–19 | Croissant One |
| Card header `.card-head h3` | 16 | Croissant One |
| KPI value `.kpi .val` | 28 | Croissant One |
| Body / inputs / table cells | 13–14 | Inter |
| Labels / hints / metadata | 11–12.5 | Inter |
| Eyebrow / table headers | 10.5–11 uppercase, tracked | Inter 600 |

---

## 5. Sizing, radius, spacing

| Token | Value | Use |
|---|---|---|
| `--sidebar-w` | `240px` | Sidebar column width |
| `--topbar-h` | `64px` | Sticky topbar height |
| `--radius-sm` | `6px` | Pager buttons, small chips, kbd |
| `--radius-md` | `8px` | Buttons, inputs, nav items, segmented |
| `--radius-lg` | `12px` | Cards, KPI tiles, toolbars |

**Spacing:** use the helper classes (`.gap-8`, `.mt-16`, `.mb-24`, …) or the
component classes' built-in padding. The system's rhythm is **4 / 8 / 12 / 16 /
22 / 24 / 28 / 32 px**. Don't invent off-grid values.

**Border radius for pills/chips/badges** is `999px` (fully rounded).

---

## 6. Component catalog

Every class group below already exists in `globals.css`. Phase 1 wraps each in
a `components/ui/*` React primitive. **Render the listed class names exactly** —
that's what guarantees pixel parity.

### 6.1 Buttons — `.btn`

| Variant | Class | Use |
|---|---|---|
| Primary | `.btn .btn-pri` | The **one** main action per page (Amber fill) |
| Secondary | `.btn .btn-sec` | Cancel / Back (white, outlined) |
| Destructive | `.btn .btn-dng` | Delete / cancel order (Ember; always modal-confirmed) |
| Ghost | `.btn .btn-ghost` | Low-emphasis / toolbar |
| Text/link | `.btn .btn-txt` | Inline link-style action |

Modifiers: `.btn-sm` (in tables), `.btn-icon` (square icon-only), `[disabled]`
(opacity 0.55, `not-allowed`). React API: `<Button variant="pri|sec|dng|ghost|txt"
size="sm|md" loading disabled iconOnly>`.

### 6.2 Badges & status chips — `.badge`

| Class | Colour | Domain states it represents |
|---|---|---|
| `.bd-success` | green | Stock **OK**, PO **RECEIVED**, SO **SHIPPED**, **IN** movement, **Synced** |
| `.bd-warn` | amber | Stock **LOW**, sync **Pending** |
| `.bd-danger` | ember | Stock **OUT**, **OUT** movement, sync **Failed** |
| `.bd-ink` | grey | PO/SO **DRAFT** |
| `.bd-info` | blue | Item type **RAW** |
| `.bd-purple` | purple | Item type **FINISHED** |

Add a leading `.dot` for emphasis. **Every badge carries text, not colour
alone** (accessibility §10). Canonical domain→badge mapping lives in §9.

### 6.3 Cards — `.card`

`.card` (surface) · `.card-pad` (padding) · `.card-head` (title row, `<h3>` +
`.sub`) · `.card-foot`. Radius `--radius-lg`.

### 6.4 KPI tiles — `.kpi`

`.kpi-row` (5-up grid; `.kpi-4` for 4-up). Each `.kpi` has `.label`, `.val`
(Croissant One), `.delta` (`.up` green / `.down` ember), and an `.icon-pill`
(tinted by `.success` / `.danger` / `.accent` / `.info` on the `.kpi`).

### 6.5 Data table — `table.tbl`

The most-used component. `.tbl-wrap` (horizontal scroll) → `table.tbl`. Cell
modifiers: `.mono` (tabular numbers), `.muted`, `.right`, `.center`, `.strong`.
`.tbl-link` for the clickable name cell, `.tbl-actions` for the row action menu.
Footer `.tbl-foot` + `.pager` (`.pg`, `.arrow`, `.pg.active`, `.dots`).

Must support (per `UI_SPECIFICATION.md §5.4`): sortable headers, filter toolbar
above, server pagination, row hover, row→detail click, skeleton loading rows,
empty state, sticky header.

### 6.6 Filter toolbar — `.toolbar`

Sits above a table inside the same card. Holds `.search` (icon + input), `.seg`
(segmented control; `.opt.active`), `.filter-chip` (dropdown trigger), and
`.spacer`.

### 6.7 Forms — `.field`

`.field` (column: `label` + control + `.hint` / `.err`). Controls: `.input`,
`.select`, `.textarea`; error state `.error`; focus shows the Amber ring.
`.input-with-icon` for leading icons. `.check` / `.check-row` for checkboxes
(`.check.on` = checked). Required marker `.req-mark` (`*`). Layout grid
`.form-grid` (2-col, `.full` to span). Long forms get a `.sticky-foot`.

> **No placeholder-as-label.** Every field has a visible `<label>` (a11y §10).

### 6.8 Drawer — `.drawer`

Right-side 520px panel for create/edit forms. `.scrim` (backdrop) + `.drawer`
(`.open` slides in) with `.drawer-head` / `.drawer-body` / `.drawer-foot`.
ESC closes; `aria-modal`.

### 6.9 Modal — `.modal-host` / `.modal-card`

Centred, max 560px, for confirmations and quick "add" forms. `.head` (with
tinted `.ic`, `.ic.danger`, `.ic.success`), `.body`, `.foot`. Used by the PO
**Receive** and SO **Ship** confirmations and the Manual Adjustment form.

### 6.10 Toasts — `.toast`

Bottom-right stack `.toasts`. Variants `.success` / `.warn` / `.danger` /
`.info` (colour the `.ic`). The `.body` has a message line and an optional
`.req` line for the **Request ID** (mono). Optional `.toast-action` button.

> **Non-negotiable (§5.6):** danger toasts **always** render the Request ID via
> `.req .mono`. The DOM is built for it; don't ship a danger toast without it.

### 6.11 Empty & loading — `.empty`, `.skeleton`

`.empty` (`.ill` icon + `.ttl` headline + `.sub` subtext + CTA). `.skeleton`
(shimmer placeholder) for table rows and cards — **skeletons, not spinners,
not blank screens** (`UI_SPECIFICATION.md §5.8`).

### 6.12 Tabs — `.tabs`

`.tabs` row of `.tab` (`.tab.active` underlined in Amber). Used on detail pages
(Items, Customers, Vendors).

### 6.13 Domain-specific pieces

| Component | Class | Notes |
|---|---|---|
| **Stock chip** | `.stock-chip` (`.ok` / `.short` / `.warn`) | The SO live-stock indicator (§5 non-negotiable) |
| **Line-items editor** | `.line-items` (`.input-sm`, `.row-x`, `.total`) | PO/SO create line table |
| **Sticky footer** | `.sticky-foot` (`.totals`, `.actions`) | Long create forms |
| **Progress bar** | `.bar` (`.success` / `.danger`) `> .fill` | Low-stock bars on dashboard |
| **Timeline** | `.timeline` (`.dot.done/.now/.fail`) | Stock-impact / audit trails |
| **External link** | `.ext-link` | "Open in Zoho CRM" |
| **Env chip** | `.env-chip` | `dev`/`staging` badge in chrome |
| **Avatars** | `.avatar-sm`, `.avatar-stack` | User initials |

### 6.14 Layout chrome

`.app` (sidebar + main grid) · `.sidebar` (brand, nav, foot) · `.topbar`
(crumbs, search, actions, user-menu) · `.page-head` (title + actions) ·
`.app-footer` (version + env + copyright). Auth pages use the two-pane
`.auth-wrap` from `login.css`.

### 6.15 Helpers

Flex/grid/spacing utilities exist (`.flex`, `.col`, `.gap-*`, `.mt-*`,
`.mb-*`, `.grid-2`, `.grid-3`, `.items-center`, `.justify-between`,
`.text-muted`, `.w-full`, …). Use them for one-off layout instead of inline
styles. `.divider`, `.eyebrow`, `.sect-title`, `.label-pair` for structure.

### 6.16 Dropdown menu — `.menu-anchor` / `.menu-pop`

Anchored popup for a small set of actions behind one trigger. `.menu-anchor`
(positioning context) → trigger button → `.menu-backdrop` (click-catcher) +
`.menu-pop` (the panel; `.menu-pop-left` to left-align) of `.menu-item`
(`.danger` variant) / `.menu-sep`. React primitive: `components/ui/Menu.tsx`
(`<Menu>` + `<MenuItem>` / `<MenuLinkItem>`) — closes on outside click, ESC, and
item activation; `aria-haspopup="menu"` + `role="menu"`/`menuitem`. Used by the
dashboard **New Order** split (Sales / Purchase) and the topbar account menu.

---

## 7. Iconography

- **Inline SVGs from the Lucide set**, centralized in `components/ui/Icon.tsx`
  (Phase 1). One `<Icon name="…" />` API; the set covers home / box / bag /
  cart / user / truck / swap / cog / bell / search / plus / help / signout /
  chevron and grows as pages need them.
- `globals.css` styles `svg { color: currentColor }` at 14–16px — icons inherit
  text colour automatically. Don't set icon colour inline.
- Keep one consistent family (Lucide). Don't mix icon sets.

---

## 8. Motion & responsiveness

- Transitions are short (0.12–0.22s). A `prefers-reduced-motion` guard already
  exists — respect it; don't add motion that ignores it.
- Designed for **desktop ≥ 1280px**; tablet ≥ 768px usable; below 768px degrades
  gracefully (tables scroll, panes stack — see `login.css` @880px). No
  mobile-specific designs in Phase 1.

---

## 9. Domain → visual mapping (canonical)

So every page renders the same state the same way:

| Domain field | Value | Badge / chip |
|---|---|---|
| Item type | `RAW` / `FINISHED` | `.bd-info` / `.bd-purple` |
| Item status | `IN_STOCK` / `LOW_STOCK` / `NO_STOCK` | `.bd-success` / `.bd-warn` / `.bd-danger` |
| PO status | `DRAFT` / `RECEIVED` | `.bd-ink` / `.bd-success` |
| SO status | `DRAFT` / `SHIPPED` | `.bd-ink` / `.bd-success` |
| Movement direction | `IN` / `OUT` | `.bd-success` ↑ / `.bd-danger` ↓ |
| Zoho sync | Synced / Pending / Failed | `.bd-success` / `.bd-warn` / `.bd-danger` |
| SO line stock | enough / short / below reorder | `.stock-chip.ok` / `.short` / `.warn` |

> The Backend's real SO state machine is `DRAFT → SHIPPED` (verified in
> `Backend_Reference.md`). `UI_SPECIFICATION.md §5.2` still says
> "CONFIRMED / CANCELLED" — that doc is stale; **the Backend wins.**

---

## 10. Accessibility baseline (enforced)

- WCAG **AA** contrast (≥ 4.5:1) for text — already met by the token pairings.
- Every interactive element keeps a visible `:focus-visible` ring (the Amber
  box-shadow on inputs; don't strip outlines).
- Status conveyed by **text + colour**, never colour alone (badges carry labels).
- Form fields have visible `<label>`s; no placeholder-as-label.
- `aria-live="polite"` on the toast region; `aria-modal` + ESC on Modal/Drawer.

---

## 11. How to extend the system

1. **Need a colour?** Add a token to `:root` (with a `-soft`/`-tint` if it fills).
   Document it in §3. Never inline a hex.
2. **Need a component?** If it's reused (rule of three), add the class to
   `globals.css`, a `components/ui/*` wrapper, an entry in §6, and a tile in
   `/playground`. One-offs (used once) don't earn a primitive — compose helpers.
3. **Changing a token** ripples everywhere by design — that's the point. Verify
   against `/playground` before/after.
4. Keep this file in sync with `globals.css`. A token or component that exists
   in code but not here is a documentation bug.

---

## 12. Quick reference — where things live

| You want… | Go to |
|---|---|
| A colour / size value | `globals.css :root` → documented in §3, §5 |
| A button / input / table look | `globals.css` component classes → §6 |
| The typed React component | `src/components/ui/*` (Phase 1) |
| To see it rendered | `/playground` route (Phase 1) |
| The auth two-pane layout | `src/styles/login.css` |
| Fonts | `src/styles/fonts.css` |
| The engineering rules | `CLAUDE.md` |
| The phase log | `execution.md` |
