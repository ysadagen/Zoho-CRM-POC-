# Intelligence Layer — System Specification (Phase 2)

**Audience:** engineers building the Backend intelligence module and the
Frontend intelligence surfaces; reviewers validating scoring behaviour.
**Counterparts:** `ZOHO_CRM_SPECIFICATION.md` (Phase 1 CRM sync, unchanged),
`Backend/CLAUDE.md` (engineering contract), `Frontend/UI_SPECIFICATION.md`
(to be extended in Phase 2C).
**Source requirements:** JSPL CRM AI documentation — scoring diagrams
(lead scoring, effort & efficiency, customer health, beat planning),
`CRM AI - ADR-001.pdf`, `KPIs Used.docx`, `customer_profile_feasibility.docx`,
`JSPL_CRM_AI_Project_Brief.pdf`.

This document answers three questions:

1. **What new data does the system capture** so that intelligence is computable?
2. **How exactly is every score calculated** — formula, bands, defaults, worked example?
3. **How is it exposed** — tables, endpoints, recompute lifecycle, tests?

---

## 1. The mental model (one minute)

Phase 1 built an inventory system: items, customers, vendors, purchase/sales
orders, stock ledger. Phase 2 adds a **closed-loop sales execution system**
on top of it:

```
                ┌─────────────────────────────┐
                │   1. Lead scoring           │  who to target (Hot/Medium/Cold)
                └──────────┬──────────────────┘
           ┌───────────────┴───────────────┐
           ▼                               ▼
┌──────────────────────┐       ┌──────────────────────┐
│ 2. Effort &          │       │ 3. Customer health   │
│    efficiency        │       │    (who needs        │
│    (who is           │       │     attention)       │
│     performing)      │       │                      │
└──────────┬───────────┘       └──────────┬───────────┘
           └───────────────┬──────────────┘
                           ▼
                ┌─────────────────────────────┐
                │   4. Beat planning          │  where & how to act
                └──────────┬──────────────────┘
                           ▲
                ┌──────────┴──────────────────┐
                │   Data foundation (Phase 2A)│  leads, activities, targets,
                │   validated data → Postgres │  invoices/payments, locations
                └─────────────────────────────┘
```

Four deterministic scoring engines run on local Backend data. **No Zoho
dependency** — the Integration Layer remains last in the build order and is
untouched by this phase.

| Engine | Question it answers | Entity scored | Output |
|---|---|---|---|
| Lead scoring | Which leads deserve attention first? | Lead | 0–100 + HOT / MEDIUM / COLD |
| Effort & efficiency | Who is performing, and is effort converting? | Sales rep (user) | Effort 0–100, Efficiency 0–100, quadrant |
| Customer health | Which customers are healthy vs at churn risk? | Customer | 0–100 + HEALTHY / STABLE / AT_RISK / CRITICAL |
| Beat planning | Which customers should a rep visit next, where? | Customer (per rep) | Visit Priority Score 0–100 + suggested beat |

---

## 2. Design principles (non-negotiable)

These come straight from the source requirements and ADR-001. They are
enforceable in code review and tests.

1. **Deterministic first.** Every score in Phase 2B is pure arithmetic over
   stored data. Same inputs ⇒ same outputs, unit-testable to the decimal.
   LLM capabilities (AI business summary, qualitative lead assessment) are
   Phase 2D and never feed back into deterministic scores.
2. **Weights live in configuration, never in code** (ADR-001
   "Store BU-specific weights in configuration"). Every engine reads its
   active `scoring_configs` row. Changing a weight is a data change, not a
   deploy.
3. **Every score is versioned.** Every persisted score row carries the
   `config_id` (engine + version) it was computed with (ADR-001 "Log
   framework version with each score for A/B testing capability").
4. **Missing data never blocks scoring.** Every parameter has a documented
   conservative default. A lead with only a name still gets a score; the
   score row records which defaults were applied (`defaults_applied`).
5. **Score history is append-only.** Snapshots are inserted, never updated —
   same philosophy as `stock_movements`. Trends come for free.
6. **Single framework, BU-ready.** ADR-001 mandates BU-specific frameworks
   (Cement predictive vs TMT qualification) for JSPL production. The POC
   implements **one** framework, but the config/versioning schema makes a
   second framework a new config row + routing rule, not a redesign
   (see Decision D-11).
7. **The intelligence layer lives inside the Backend** as new modules in the
   existing layout (`models/`, `services/`, `repositories/`, `api/v1/`).
   No fourth service, no new infra (no Redis, no Celery) — per
   `Backend/CLAUDE.md` §2 (see Decision D-1).

---

## 3. Data foundation — schema extensions (Phase 2A)

All tables follow existing Backend conventions: UUID PKs, `created_at` /
`updated_at` server-managed timestamps, `created_by_user_id` /
`updated_by_user_id` audit FKs (`ON DELETE RESTRICT`), CHECK constraints for
invariants, soft delete via `is_active` only where noted, Alembic migration
per change.

### 3.1 New enums

```
LeadStage             NEW | QUALIFICATION | NEGOTIATION | WON | LOST
LeadSource            PHONE_IN | WALK_IN | REFERENCE | CAMPAIGN | FIELD_VISIT | OTHER
DealerPotential       HIGH | MEDIUM | LOW
CustomerType          DEALER | SUB_DEALER | RETAILER
ActivityType          VISIT | MEETING | FOLLOW_UP | CALL | COMPLAINT
CompetitiveRiskLevel  NONE | LOW | MEDIUM | HIGH
ScoringEngine         LEAD_SCORING | EFFORT_EFFICIENCY | CUSTOMER_HEALTH | BEAT_PLANNING
LeadClassification    HOT | MEDIUM | COLD
HealthClassification  HEALTHY | STABLE | AT_RISK | CRITICAL
VisitPriority         CRITICAL | HIGH | MEDIUM | LOW
EffortQuadrant        HIGH_EFFORT_HIGH_EFFICIENCY | HIGH_EFFORT_LOW_EFFICIENCY |
                      LOW_EFFORT_HIGH_EFFICIENCY | LOW_EFFORT_LOW_EFFICIENCY
```

### 3.2 `leads`

The new central entity. A lead may exist with or without a linked customer
(new prospect vs expansion of an existing account).

| Column | Type | Constraints / notes |
|---|---|---|
| `id` | UUID PK | |
| `lead_number` | str, unique | Format `LD-YYYYMM-NNNNNN`, generated like `so_number` |
| `customer_id` | UUID FK → customers, nullable | Set when the lead is for an existing customer, or on WON |
| `contact_name` | str, not null | |
| `phone` | str, nullable | |
| `email` | str, nullable | |
| `item_id` | UUID FK → items, nullable | Product of interest |
| `quantity` | Numeric, nullable | In the item's `unit_of_measure`. CHECK `quantity > 0` |
| `estimated_budget` | Numeric, nullable | CHECK `estimated_budget >= 0` |
| `dealer_potential` | DealerPotential, nullable | Rep's judgement of account potential |
| `required_by_date` | date, nullable | Drives the **urgency** parameter |
| `source` | LeadSource, not null | |
| `stage` | LeadStage, not null, default NEW | Mutated **only** via the transition endpoint |
| `assigned_to_user_id` | UUID FK → users, not null, indexed | The owning sales rep |
| `state` / `district` / `city` / `pincode` | str, all nullable | Structured location; drives **location** parameter and beat planning |
| `won_value` | Numeric, nullable | Actual order value; required on WON |
| `won_at` / `lost_at` | timestamptz, nullable | |
| `lost_reason` | str, nullable | Required on LOST |
| `notes` | str, nullable | |
| `is_active` | bool, default true | Soft delete |
| audit + timestamps | | per convention |

CHECK constraints:
- `ck_leads_won_consistency`: `(stage = 'WON') = (won_at IS NOT NULL AND won_value IS NOT NULL)`
- `ck_leads_lost_consistency`: `(stage = 'LOST') = (lost_at IS NOT NULL AND lost_reason IS NOT NULL)`

**Stage transition matrix** (anything else → 409 `INVALID_STAGE_TRANSITION`):

```
NEW           → QUALIFICATION | LOST
QUALIFICATION → NEGOTIATION   | LOST
NEGOTIATION   → WON           | LOST
WON, LOST     → (terminal)
```

### 3.3 `lead_stage_history` (append-only)

Same philosophy as `stock_movements`: every transition writes a row; rows
are never updated or deleted. This single table yields stage-change rate,
won dates, and time-to-close for the effort & efficiency engine.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `lead_id` | UUID FK → leads, ON DELETE CASCADE, indexed | |
| `from_stage` | LeadStage, nullable | NULL only for the creation row (`to_stage = NEW`) |
| `to_stage` | LeadStage, not null | |
| `changed_at` | timestamptz, not null, default now | |
| `changed_by_user_id` | UUID FK → users, RESTRICT | |
| `remark` | str, nullable | |

Composite index: `(lead_id, changed_at DESC)`.

### 3.4 `sales_activities` (append-only)

One table covers every activity input the four engines need (effort score,
engagement, visit gap, communication gap, service risk).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `type` | ActivityType, not null | VISIT, MEETING, FOLLOW_UP, CALL, COMPLAINT |
| `rep_user_id` | UUID FK → users, not null, indexed | Who performed / logged it |
| `customer_id` | UUID FK → customers, nullable, indexed | |
| `lead_id` | UUID FK → leads, nullable, indexed | |
| `occurred_at` | timestamptz, not null | |
| `duration_minutes` | int, nullable | CHECK `duration_minutes > 0`. Drives time-spent weight |
| `remarks` | str, nullable | VOC source for Phase 2D LLM summaries |
| audit + timestamps | | per convention |

CHECK: `ck_sales_activities_has_subject`:
`customer_id IS NOT NULL OR lead_id IS NOT NULL`.
No PATCH/DELETE endpoints — activities are facts (corrections = new row +
remark; same rule as stock adjustments).
Composite indexes: `(customer_id, occurred_at DESC)`, `(rep_user_id, occurred_at DESC)`.

### 3.5 `customers` — new columns

| Column | Type | Notes |
|---|---|---|
| `customer_type` | CustomerType, not null, default RETAILER | Beat-planning weight. Backfill existing rows to RETAILER |
| `state` / `district` / `city` / `pincode` | str, nullable | Structured location (the free-text `address` stays for display) |
| `competitive_risk_level` | CompetitiveRiskLevel, not null, default NONE | Manual flag for POC (Decision D-8) |

### 3.6 `items` — new column

| Column | Type | Notes |
|---|---|---|
| `standard_cost` | Numeric, nullable | CHECK `standard_cost >= 0`. Enables product/realized margin. NULL ⇒ margin parameter falls to its default |

### 3.7 `customer_targets`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `customer_id` | UUID FK → customers, indexed | |
| `period_start` / `period_end` | date, not null | CHECK `period_end > period_start` |
| `target_quantity` | Numeric, not null | CHECK `> 0`. In dispatch units |
| `target_revenue` | Numeric, nullable | CHECK `>= 0` |
| audit + timestamps | | |

UNIQUE `(customer_id, period_start, period_end)`.

### 3.8 `invoices` and `payments` (minimal AR for DSO / ageing)

`invoices`:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `invoice_number` | str, unique | `INV-YYYYMM-NNNNNN` |
| `customer_id` | UUID FK → customers, indexed | |
| `sales_order_id` | UUID FK → sales_orders, nullable | |
| `invoice_date` | date, not null | |
| `due_date` | date, not null | CHECK `due_date >= invoice_date` |
| `amount` | Numeric, not null | CHECK `> 0` |
| audit + timestamps | | |

`payments`:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `invoice_id` | UUID FK → invoices, ON DELETE RESTRICT, indexed | |
| `paid_date` | date, not null | |
| `amount` | Numeric, not null | CHECK `> 0` |
| audit + timestamps | | |

Derived (never stored): `outstanding = invoice.amount − Σ payments.amount`
(service-level CHECK: payments may not exceed the invoice amount → 409
`OVERPAYMENT`). An invoice is **paid** when outstanding = 0; **overdue**
when outstanding > 0 and `due_date < today`.

### 3.9 `scoring_configs`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `engine` | ScoringEngine, not null | |
| `version` | int, not null | UNIQUE `(engine, version)` |
| `params` | JSONB, not null | Weights, band tables, thresholds — full shape per engine in §4–§7 |
| `is_active` | bool, not null, default false | Partial unique index: at most **one** active config per engine |
| `description` | str, nullable | Why this version exists |
| `created_at`, `created_by_user_id` | | Configs are immutable once created — a change = new version row |

Migrations seed **version 1 active** for all four engines with the default
parameters defined in this document.

### 3.10 Score snapshot tables (append-only)

All four share the pattern: identity of the scored entity, `config_id` FK →
`scoring_configs`, `computed_at`, component scores, total, classification,
`defaults_applied` (JSONB array of parameter names that fell back to
defaults). Latest score = newest `computed_at` per entity (composite index
`(entity_id, computed_at DESC)`).

`lead_scores`: `lead_id`, `urgency_score`, `location_score`,
`contribution_margin_score`, `quantity_score`, `product_margin_score`
(each int 0–100), `total_score` numeric(5,2), `classification`
LeadClassification, `defaults_applied`.

`customer_health_scores`: `customer_id`, `cps` numeric(5,2), `crs`
numeric(5,2), `components` JSONB (all ten sub-scores), `weight_profile` str,
`health_score` numeric(5,2), `classification` HealthClassification,
`defaults_applied`.

`effort_efficiency_scores`: `rep_user_id`, `period_start`, `period_end`,
`effort_raw` numeric, `effort_score` numeric(5,2), `efficiency_components`
JSONB (five sub-scores), `efficiency_score` numeric(5,2), `quadrant`
EffortQuadrant.

`visit_priority_scores`: `customer_id`, `rep_user_id`, `revenue_score`,
`visit_gap_score`, `customer_type_score`, `location_density_score` (ints),
`vps` numeric(5,2), `priority` VisitPriority.

---

## 4. Engine 1 — Lead scoring

> Every lead scored 0–100. Five parameters, equally weighted at 20% each
> (weights configurable). Missing data never blocks scoring.

```
total = Σ (parameter_score × weight)        weights default to 0.20 each
HOT ≥ 80   |   MEDIUM 40–79   |   COLD < 40
```

**Cohort window:** all cohort-relative parameters use leads created in the
trailing **90 days** (configurable, Decision D-5).

### 4.1 Parameter: Urgency (weight 0.20)

From `required_by_date − today` (days):

| Days until required | Score |
|---|---|
| < 7 | 100 |
| 7–30 | 70 |
| 31–60 | 40 |
| > 60 | 20 |
| `required_by_date` NULL → **default 40** | |
| `required_by_date` in the past → 100 (still open = maximally urgent) | |

### 4.2 Parameter: Location (weight 0.20)

Completeness of structured location on the lead:

| Location data present | Score |
|---|---|
| state + district + (city or pincode) — "full" | 100 |
| state + district — "partial" | 50 |
| state only — "no data" tier | 30 |
| nothing | 0 |

### 4.3 Parameter: Contribution margin (weight 0.20)

Derived from `estimated_budget` + `dealer_potential` (per the source
diagram: "Margin derived from estimated_budget + dealer_potential").

Budget band (absolute thresholds, configurable in `params`; defaults):
**HIGH ≥ 1,000,000 · MEDIUM 250,000–999,999 · LOW < 250,000**.

| dealer_potential \ budget band | HIGH | MEDIUM | LOW |
|---|---|---|---|
| HIGH | 100 | 70 | 40 |
| MEDIUM | 70 | 70 | 40 |
| LOW | 40 | 40 | 10 |

Missing one input → band by the other alone (HIGH→100, MEDIUM→70, LOW→40
for potential; HIGH→100, MEDIUM→70, LOW→40 for budget). Both missing →
**default 40**.

### 4.4 Parameter: Quantity (weight 0.20)

Normalized within the cohort: "highest in period = base 100%".
`ratio = lead.quantity ÷ max(quantity over cohort leads with same item type, excluding NULLs)`

| ratio | Score |
|---|---|
| ≥ 0.75 | 100 |
| 0.40–0.74 | 70 |
| 0.15–0.39 | 40 |
| < 0.15 | 20 |
| `quantity` NULL, or cohort empty → **default 40** | |

### 4.5 Parameter: Product margin (weight 0.20)

From the linked item: `margin % = (unit_price − standard_cost) ÷ unit_price × 100`.

| Margin % | Score |
|---|---|
| ≥ 25 | 100 |
| 10–24 | 60 |
| < 10 | 30 |
| `item_id` NULL or `standard_cost` NULL → **default 60** | |

### 4.6 Worked example (canonical test vector LS-1)

Lead: required in 20 days (70) · state+district only (50) · budget 800,000 +
potential HIGH → MEDIUM×HIGH = 70 · quantity 50 vs cohort max 60 → ratio
0.83 → 100 · item margin 16% → 60.

```
total = 0.20×70 + 0.20×50 + 0.20×70 + 0.20×100 + 0.20×60 = 70.00 → MEDIUM
```

### 4.7 Recompute triggers

On lead create, on PATCH of any scoring input (`required_by_date`, location
fields, `estimated_budget`, `dealer_potential`, `quantity`, `item_id`), and
on stage transition. Cohort drift (a new larger lead changes everyone's
quantity ratio) is reconciled by the recompute endpoint (§9.5, Decision D-9).

---

## 5. Engine 2 — Effort & efficiency

> Effort = input invested. Efficiency = output per input. Scored per sales
> rep over a period (default: trailing 90 days; endpoint accepts explicit
> `period_start`/`period_end`).

### 5.1 Effort score

Raw effort from `sales_activities` (by `rep_user_id`, within period) —
activity weights configurable, defaults:

```
effort_raw = (visits × 3) + (meetings × 4) + (follow_ups × 2) + (calls × 1)
           + time_spent_weight
time_spent_weight = Σ duration_minutes ÷ 60        (1 point per hour logged)
```

COMPLAINT activities do **not** count toward effort.
Normalized within the cohort of all active reps in the period:

```
effort_score = effort_raw ÷ max(effort_raw over cohort) × 100
```

Top performer = 100 by construction. A rep with zero activity scores 0.
Cohort of one rep → effort_score = 100 (only member is the benchmark).

### 5.2 Composite efficiency score — five components × 20% each

All components are computed per rep over the period, normalized 0–100, then:

```
efficiency = 0.20×(stage_change_rate) + 0.20×(won_rate) + 0.20×(revenue_efficiency)
           + 0.20×(time_to_close) + 0.20×(lead_score_utilization)
```

| # | Component | Formula | Normalization |
|---|---|---|---|
| 1 | Lead stage change rate % | (assigned leads with ≥1 transition beyond NEW ÷ total assigned leads) × 100 | Already 0–100 |
| 2 | Lead won rate % | (leads WON ÷ total assigned leads) × 100 | Already 0–100 |
| 3 | Revenue efficiency | Σ `won_value` of WON leads ÷ effort_raw | ÷ cohort max × 100 |
| 4 | Avg time to close | Σ(won_at − lead created_at, days) ÷ leads won | Inverted min–max over cohort: `(max − rep) ÷ (max − min) × 100`; cohort min = 100, max = 0; all equal or single rep → 100 |
| 5 | Lead score utilization % | (effort_raw points spent on leads whose latest score is HOT ÷ effort_raw points spent on all leads) × 100 | Already 0–100 |

Edge rules (all must be unit-tested): zero assigned leads → components 1, 2,
5 = 0; zero won leads → components 3 = 0 and 4 = 0; activity rows without a
`lead_id` count toward effort but not toward utilization's numerator or
denominator.

### 5.3 Classification and quadrant

Efficiency bands: **80–100 highly efficient · 60–79 efficient ·
40–59 needs improvement · < 40 inefficient**.

Quadrant (threshold 60 on both axes, configurable):

| | efficiency ≥ 60 | efficiency < 60 |
|---|---|---|
| **effort ≥ 60** | HIGH_EFFORT_HIGH_EFFICIENCY — best performers | HIGH_EFFORT_LOW_EFFICIENCY — process/targeting issue |
| **effort < 60** | LOW_EFFORT_HIGH_EFFICIENCY — low engagement, needs a push | LOW_EFFORT_LOW_EFFICIENCY — underperformance, intervene |

### 5.4 Worked example (canonical test vector EE-1)

Rep R1, 90-day period: 10 visits, 4 meetings, 6 follow-ups, 8 calls, 20h
logged → `effort_raw = 30 + 16 + 12 + 8 + 20 = 86`. Cohort max raw = 120 →
`effort_score = 71.67`.

Efficiency: stage-change 60, won rate 25, revenue 1,200,000 ÷ 86 = 13,953 vs
cohort max 20,000 → 69.77, avg close 28d vs cohort min 20 / max 45 →
(45−28)÷25×100 = 68.00, utilization 55.

```
efficiency = 0.20×(60 + 25 + 69.77 + 68 + 55) = 55.55 → "needs improvement"
quadrant   = effort 71.67 (high) × efficiency 55.55 (low)
           → HIGH_EFFORT_LOW_EFFICIENCY
```

---

## 6. Engine 3 — Customer health

> Health = performance minus churn risk, normalized 0–100.

```
raw    = (CPS × W_P) − (CRS × W_R)          with W_P + W_R = 1
health = raw + 100 × W_R                     (min–max normalization to 0–100)
HEALTHY 80–100 | STABLE 60–79 | AT_RISK 40–59 | CRITICAL < 40
```

(The normalization is exact: raw ranges over [−100·W_R, +100·W_P]; shifting
by 100·W_R maps it onto [0, 100] because the weights sum to 1.)

**Weight profiles** (configurable in `params`; the snapshot records which
profile was used):

| Profile | W_P | W_R | When |
|---|---|---|---|
| `standard` (default) | 0.60 | 0.40 | Default for all customers (Decision D-4) |
| `high_competition` | 0.60 | 0.40 | Reserved — same as standard until market tagging exists |
| `credit_stress` | 0.55 | 0.45 | Manual assignment per customer (future) |
| `growth_expansion` | 0.70 | 0.30 | Manual assignment per customer (future) |

**Dispatch** = shipped quantity: Σ `sales_order_items.quantity` of SHIPPED
sales orders (by `shipped_date`). All windows are relative to the
computation date.

### 6.1 Customer Performance Score (CPS) — five components

| Component | Weight | Formula | Band → score |
|---|---|---|---|
| Volume achievement | 0.30 | dispatch in current target period ÷ `target_quantity` × 100, capped at 100 | Direct value. No target row → **default 50** |
| Payment discipline (DSO) | 0.20 | Amount-weighted avg of `paid_date − invoice_date` over invoices fully paid in trailing 180d | ≤30d→100 · 31–45→75 · 46–60→50 · 61–90→25 · >90→0. No paid invoices → **default 50** |
| Engagement (visits) | 0.20 | Count of VISIT + MEETING activities in trailing 90d | ≥6→100 · 4–5→75 · 2–3→50 · 1→25 · 0→0 |
| Growth trend | 0.15 | (revenue last 90d − revenue prior 90d) ÷ revenue prior 90d × 100 | ≥+20%→100 · +5..+19→75 · −5..+4→50 · −20..−6→25 · <−20→0. No prior-period revenue → **default 50** |
| Margin quality | 0.15 | Realized margin % across shipped SO lines in trailing 90d: Σ(line_total − qty×standard_cost) ÷ Σ line_total × 100 | ≥25%→100 · 10–24→60 · <10→30. Costs missing → **default 60** |

### 6.2 Churn Risk Score (CRS) — five components (higher = riskier)

| Component | Weight | Formula | Band → score |
|---|---|---|---|
| Volume decline (30/60/90d) | 0.30 | decline % = max(0, (avg monthly dispatch over prior 90d − dispatch last 30d) ÷ avg monthly dispatch over prior 90d × 100) | ≥50%→100 · 25–49→70 · 10–24→40 · <10→0. No baseline → **default 0** |
| Payment risk / overdue | 0.25 | overdue outstanding ÷ total outstanding × 100 (today) | ≥75%→100 · 50–74→75 · 25–49→50 · 1–24→25 · 0→0. No outstanding → 0 |
| Competitive risk | 0.20 | `customers.competitive_risk_level` (manual flag, Decision D-8) | NONE→0 · LOW→33 · MEDIUM→66 · HIGH→100 |
| Engagement gap | 0.15 | `(comm_gap × 0.4) + (activity_gap × 0.6)` — tables below | Composite 0–100 |
| Service risk (complaints) | 0.10 | COMPLAINT activities in trailing 90d | 0→0 · 1→40 · 2→70 · ≥3→100 |

**Communication gap** (days since last VISIT/MEETING/CALL/FOLLOW_UP
activity): 0–7→0 · 8–15→20 · 16–30→40 · 31–60→70 · >60→100 · never→100.

**Activity gap** (days since last SHIPPED sales order): 0–15→0 · 16–30→25 ·
31–60→50 · 61–90→75 · >90→100 · never→100.

### 6.3 Worked example (canonical test vector CH-1)

CPS: volume 80 (0.30→24.0) · DSO 70 (0.20→14.0) · engagement 60 (0.20→12.0) ·
growth 50 (0.15→7.5) · margin 70 (0.15→10.5) → **CPS = 68.00**.

CRS: decline 40 (0.30→12.0) · payment 30 (0.25→7.5) · competitive LOW=33
(0.20→6.6) · gap: comm 40, activity 25 → 0.4×40+0.6×25 = 31 (0.15→4.65) ·
service 0 (0.10→0) → **CRS = 30.75**.

```
raw    = 68.00×0.60 − 30.75×0.40 = 40.80 − 12.30 = 28.50
health = 28.50 + 100×0.40 = 68.50 → STABLE
```

---

## 7. Engine 4 — Beat planning & visit prioritization

> For a given rep: rank their customers by Visit Priority Score, cluster by
> location, suggest a day's beat within visit capacity.

### 7.1 Visit Priority Score (VPS)

Adopted formula (Decision D-2 — see §13 for the rejected alternative):

```
VPS = (0.35 × revenue_score) + (0.25 × visit_gap_score)
    + (0.20 × customer_type_score) + (0.20 × location_density_score)
```

| Input | Definition |
|---|---|
| `revenue_score` | Customer revenue (Σ shipped SO totals, trailing 90d) ÷ max over the rep's customers × 100. Zero everywhere → all 0 |
| `visit_gap_score` | Days since last VISIT activity: <15→25 · 15–29→50 · 30–44→75 · ≥45 or never→100 |
| `customer_type_score` | DEALER→100 · SUB_DEALER→80 · RETAILER→70 (per the 1.0/0.8/0.7 weights) |
| `location_density_score` | LDS × 100, where LDS = customers in the same district ÷ total customers handled by the rep. District NULL → 0 |

Priority bands: **CRITICAL ≥ 80 · HIGH 60–79 · MEDIUM 40–59 · LOW < 40**.

"Customers handled by a rep" (POC definition): customers with at least one
activity by that rep, or linked to a lead assigned to that rep, in the
trailing 180 days.

### 7.2 Suggested beat (the planning output)

`GET /api/v1/intelligence/beat-plan?rep_user_id=&max_visits=` returns:

1. All handled customers scored per §7.1, ranked by VPS descending.
2. Grouped into **clusters by district**; cluster opportunity flagged when
   LDS > 0.50 (per source: "LDS > 0.50 = high cluster opportunity").
3. A suggested beat: top `max_visits` customers (default **12**, from the
   time-utilization model: 360 effective minutes ÷ ~22 min per visit ≈ 16
   max; 12 is the conservative default), preferring same-cluster customers
   on VPS ties.
4. Per-customer: VPS breakdown, priority band, days since last visit, last
   90d revenue.

### 7.3 Productivity metrics (reported, not scored)

Returned by the beat-plan and effort endpoints for dashboard display:

```
daily_visit_efficiency = completed visits ÷ planned visits × 100      (Phase 2C+, needs planned-visit capture — reported as NULL until then)
revenue_per_visit      = Σ shipped SO totals ÷ count of VISIT activities (period)
beat_efficiency        = 0.30×cluster + 0.30×revenue + 0.20×completion + 0.20×time_util   (Phase 2C+, same dependency)
```

Only `revenue_per_visit` is computable in Phase 2B; the other two require
planned-beat capture, which lands with the Frontend beat screen (2C).

### 7.4 Worked example (canonical test vector BP-1)

Customer C (DEALER) in Jajpur, rep handles 40 customers of which 12 in
Jajpur: revenue 340,000 vs max 400,000 → 85 · last visit 25 days → 50 ·
type → 100 · LDS 12/40 = 0.30 → 30.

```
VPS = 0.35×85 + 0.25×50 + 0.20×100 + 0.20×30 = 29.75 + 12.5 + 20 + 6 = 68.25 → HIGH
```

---

## 8. Score computation lifecycle

| Engine | When computed | When persisted |
|---|---|---|
| Lead scoring | On lead create / scoring-input PATCH / transition; and on recompute | Snapshot on every computation |
| Effort & efficiency | Live on GET (always-fresh cohort math); on recompute | Snapshot only on recompute |
| Customer health | Live on GET; on recompute | Snapshot only on recompute |
| Beat planning | Live on GET; on recompute | Snapshot only on recompute |

Rationale (Decision D-9): lead scores are per-entity and cheap → persist on
write. The other three are cohort computations whose inputs change with
every activity/order — computing live on read guarantees freshness without
invalidation machinery; snapshots exist for **trend history** and are
produced by the recompute endpoint, which a scheduled job (Windows Task
Scheduler / cron hitting the endpoint — no new infra) calls nightly.

`POST /api/v1/intelligence/recompute` (admin): body
`{"engine": "<ScoringEngine>" | null}` — null = all engines. Synchronous;
returns counts per engine. Recomputes and snapshots every active entity
using the active config.

---

## 9. API endpoints (Phase 2A + 2B)

All under `/api/v1`, JWT-protected, standard pagination
(`{"items": [...], "total": N, "limit": L, "offset": O}`), errors via the
`AppError` envelope. The endpoint tables are the contract; §9.6 defines the
canonical request/response shapes.

### 9.1 Leads (Phase 2A)

| Method & path | Purpose | Errors |
|---|---|---|
| `GET /leads` | List; filters: `stage`, `source`, `assigned_to_user_id`, `state`, `district`, `classification`, `created_from/to` | |
| `POST /leads` | Create (stage forced to NEW; writes creation row to stage history; computes initial score) | 422 |
| `GET /leads/{id}` | Detail incl. latest score + stage history | 404 |
| `PATCH /leads/{id}` | Update mutable fields (not `stage`); recomputes score if scoring inputs changed | 404, 422 |
| `POST /leads/{id}/transition` | Body `{to_stage, remark?, won_value?, lost_reason?}`; validates matrix, writes history, sets won/lost fields, recomputes score | 404, 409 `INVALID_STAGE_TRANSITION`, 422 |
| `DELETE /leads/{id}` | Soft delete | 404 |

### 9.2 Activities (Phase 2A)

| Method & path | Purpose | Errors |
|---|---|---|
| `GET /activities` | List; filters: `type`, `rep_user_id`, `customer_id`, `lead_id`, `occurred_from/to` | |
| `POST /activities` | Create (append-only; no update/delete endpoints) | 404 (bad FK), 422 |

### 9.3 Targets, invoices, payments (Phase 2A)

| Method & path | Purpose | Errors |
|---|---|---|
| `GET /customers/{id}/targets` · `POST /customers/{id}/targets` · `PATCH /customers/{id}/targets/{target_id}` | Target CRUD | 404, 409 (overlapping duplicate period), 422 |
| `GET /invoices` · `POST /invoices` · `GET /invoices/{id}` | Invoice CRUD (no delete) | 404, 422 |
| `POST /invoices/{id}/payments` | Record payment | 404, 409 `OVERPAYMENT`, 422 |

### 9.4 Intelligence reads (Phase 2B)

| Method & path | Returns |
|---|---|
| `GET /intelligence/lead-scores` | Latest score per active lead; filters: `classification`, `assigned_to_user_id` |
| `GET /intelligence/lead-scores/{lead_id}` | Latest + full history + component breakdown + `defaults_applied` |
| `GET /intelligence/customer-health` | Live-computed health for all active customers; filter: `classification`; sort by score |
| `GET /intelligence/customer-health/{customer_id}` | Live detail: CPS/CRS component breakdown + snapshot history (trend) |
| `GET /intelligence/effort-efficiency?period_start=&period_end=` | Live cohort table: per rep effort, efficiency, components, quadrant |
| `GET /intelligence/effort-efficiency/{user_id}` | Live detail + snapshot history |
| `GET /intelligence/beat-plan?rep_user_id=&max_visits=` | §7.2 payload |

### 9.5 Administration (Phase 2B, admin-only)

| Method & path | Purpose |
|---|---|
| `GET /intelligence/configs?engine=` | List config versions (active flagged) |
| `POST /intelligence/configs` | Create new version for an engine and activate it (deactivates prior). Params validated against the engine's schema (weights sum to 1, bands contiguous) → 422 on violation |
| `POST /intelligence/recompute` | §8 |

### 9.6 Canonical request/response shapes

Pydantic schemas live in `schemas/{lead,sales_activity,customer_target,invoice,intelligence}.py`.
Every `*Create`/`*Update` schema sets `str_strip_whitespace=True`
(CLAUDE.md §10.4). Notation: `?` = optional/nullable; constraints in
parentheses become Pydantic validators **and**, where marked in §3, DB CHECKs.

```
LeadCreate
  contact_name: str                      (required, min_length=1)
  source: LeadSource                     (required)
  assigned_to_user_id: UUID              (required, must exist → 404)
  customer_id?: UUID                     (must exist → 404)
  phone?: str
  email?: EmailStr
  item_id?: UUID                         (must exist → 404)
  quantity?: Decimal                     (> 0)
  estimated_budget?: Decimal             (>= 0)
  dealer_potential?: DealerPotential
  required_by_date?: date
  state?: str   district?: str   city?: str   pincode?: str
  notes?: str

LeadUpdate
  every LeadCreate field, all optional. `stage` is NOT a field on this
  schema — stage changes go through /transition only.

LeadOut
  id, lead_number, stage, every LeadCreate field,
  won_value?, won_at?, lost_at?, lost_reason?,
  is_active, created_at, updated_at,
  latest_score?: { total_score, classification, computed_at }

LeadDetailOut = LeadOut
  + stage_history: [ { from_stage?, to_stage, changed_at,
                       changed_by_user_id, remark? } ]   (changed_at desc)
  + score?: LeadScoreOut                                 (latest, full breakdown)

StageTransitionRequest
  to_stage: LeadStage                    (required)
  remark?: str
  won_value?: Decimal (> 0)              (required iff to_stage == WON → 422)
  lost_reason?: str                      (required iff to_stage == LOST → 422)

ActivityCreate
  type: ActivityType                     (required)
  occurred_at: datetime                  (required, not in the future → 422)
  rep_user_id?: UUID                     (defaults to the authenticated user)
  customer_id?: UUID ┐
  lead_id?: UUID     ┘ at least one      (else 422 SUBJECT_REQUIRED)
  duration_minutes?: int                 (> 0)
  remarks?: str

TargetCreate
  period_start: date,  period_end: date  (end > start → 422)
  target_quantity: Decimal               (> 0)
  target_revenue?: Decimal               (>= 0)

InvoiceCreate
  customer_id: UUID, invoice_date: date, due_date: date (>= invoice_date),
  amount: Decimal (> 0), sales_order_id?: UUID
  — invoice_number is generated, never supplied

PaymentCreate
  paid_date: date, amount: Decimal (> 0)
  — service rejects Σ payments > invoice.amount → 409 OVERPAYMENT

LeadScoreOut
  lead_id, config_version: int, computed_at,
  components: { urgency, location, contribution_margin,
                quantity, product_margin },               (each int 0–100)
  total_score: float, classification: LeadClassification,
  defaults_applied: [str]            (e.g. ["urgency", "product_margin"])

CustomerHealthOut
  customer_id, company_name, computed_at, weight_profile: str,
  cps: float, crs: float,
  cps_components: { volume_achievement, payment_discipline,
                    engagement, growth_trend, margin_quality },
  crs_components: { volume_decline, payment_risk, competitive_risk,
                    engagement_gap, service_risk },
  health_score: float, classification: HealthClassification,
  defaults_applied: [str]

EffortEfficiencyOut                      (one per rep)
  rep_user_id, rep_email,
  period_start, period_end,
  activity_counts: { visits, meetings, follow_ups, calls, hours_logged },
  effort_raw: float, effort_score: float,
  efficiency_components: { stage_change_rate, won_rate, revenue_efficiency,
                           time_to_close, lead_score_utilization },
  efficiency_score: float, efficiency_band: str, quadrant: EffortQuadrant

BeatCustomerOut
  customer_id, company_name, district?, customer_type,
  vps: float, priority: VisitPriority,
  breakdown: { revenue_score, visit_gap_score,
               customer_type_score, location_density_score },
  days_since_last_visit?: int, revenue_90d: Decimal

BeatPlanOut
  rep_user_id, generated_at, max_visits,
  clusters: [ { district, customer_count, lds: float,
                cluster_opportunity: bool } ],            (lds desc)
  suggested_beat: [BeatCustomerOut],                      (≤ max_visits, vps desc)
  all_customers: [BeatCustomerOut]                        (full ranked list)

ScoringConfigOut    id, engine, version, is_active, description?, params, created_at
ScoringConfigCreate engine, params, description?
                    (version assigned = max(engine versions)+1; activates
                     immediately and deactivates the previous active row)
RecomputeRequest    engine?: ScoringEngine                (null = all engines)
RecomputeOut        results: { engine → entities_scored }, duration_ms
```

---

## 10. Frontend surfaces (Phase 2C — summary)

Detailed in a Phase 2C extension of `Frontend/UI_SPECIFICATION.md`; the
contract-level list:

1. **Leads** feature: list with stage + HOT/MEDIUM/COLD badges, filters,
   create/edit, detail with score breakdown panel (five bars + defaults
   notice), stage transition with guarded modal (won_value / lost_reason).
2. **Activities**: log-activity modal (from lead and customer detail) +
   activity timeline on both.
3. **Customer health** page: classification chips, sortable health table,
   detail drawer with CPS vs CRS breakdown and trend sparkline from
   snapshots.
4. **Team performance** page: effort vs efficiency scatter (quadrant view),
   per-rep drill-down.
5. **Beat plan** page: rep selector, ranked visit list with VPS breakdown,
   cluster grouping by district.
6. **Dashboard** additions: hot-lead count, at-risk customer count,
   funnel widget (NEW → … → WON/LOST).

Non-negotiables carry over (request-ID on danger toasts, etc.).

---

## 11. Phase 2D — LLM layer (deferred, contract only)

Implemented only after 2A–2C ship and are user-tested. Scope:

1. **AI business summary per customer** — narrative over the deterministic
   outputs: scores, trends, activity remarks, invoice posture. Endpoint:
   `GET /intelligence/customer-summary/{customer_id}`.
2. **Qualitative lead assessment** — optional sixth lead parameter
   analysing lead/activity remarks (ADR-001 allocates it 15–20 points).
   Off by default; enabled via a new scoring config version.

Hard rules (from ADR-001 "LLM Consistency"): temperature 0; structured
prompt templates checked into the repo; grounded **only** in retrieved
records (no external knowledge); output JSON-schema-validated; LLM output
**never** mutates deterministic scores; model + prompt version logged per
generation. API key via `core/config.py` settings, never logged.

---

## 12. Testing requirements (Phase 2 definition of done)

Per `Backend/CLAUDE.md` §5 — spec first, failing tests first. Mandatory
coverage:

1. **Canonical vectors LS-1, EE-1, CH-1, BP-1** (§4.6, §5.4, §6.3, §7.4)
   asserted to two decimals against the engine functions.
2. **Band edges** — one test per boundary in every band table (e.g. urgency
   at exactly 7 and 30 days; health at exactly 40/60/80).
3. **Defaults** — for each parameter: input missing ⇒ documented default
   used **and** parameter listed in `defaults_applied`. A lead with only
   `contact_name`, `source`, `assigned_to_user_id` must still score.
4. **Cohort edges** — single-rep cohort, zero-activity rep, zero leads,
   zero revenue, empty quantity cohort, customer with no invoices/targets.
5. **Stage matrix** — every legal transition passes and writes history;
   every illegal one returns 409; WON without `won_value` and LOST without
   `lost_reason` return 422.
6. **DB invariants** — direct `db_session.add(...)` bypassing the API
   asserts `IntegrityError` for every new CHECK constraint (per CLAUDE.md
   §10.3).
7. **Config versioning** — recompute after activating a new config version
   produces snapshots carrying the new `config_id`; weight sets that don't
   sum to 1 are rejected with 422.
8. **Append-only** — no update/delete route exists for `sales_activities`,
   `lead_stage_history`, or any score snapshot table.

---

## 13. Decisions log

| # | Decision | Rationale / rejected alternative |
|---|---|---|
| D-1 | Intelligence lives **inside the Backend** as new modules | A fourth service adds deploy/auth/infra surface with zero isolation benefit at POC scale. Rejected: separate `Intelligence/` FastAPI service |
| D-2 | VPS uses the 4-factor formula (0.35 revenue / 0.25 visit gap / 0.20 customer type / 0.20 location density) | The KPIs doc's 5-factor LVPS (0.30 lead score / 0.25 ROS / 0.20 VGS / 0.15 LDS / 0.10 visit type) mixes lead-ranking into customer-visit ranking and needs a visit-type taxonomy we don't capture. The diagram version is newer and self-consistent. Weights are config — switching later is a config version, not code |
| D-3 | Calls **are** included in effort at weight ×1 | Source says "not yet in CRM" — but this system owns its CRM, and `CALL` is an `ActivityType` from day one |
| D-4 | Default health weight profile = 0.60/0.40 | Matches the "high competition" profile in the source; market-segment tagging that would drive dynamic profiles doesn't exist yet. Profiles are config |
| D-5 | Default cohort/trend window = trailing 90 days everywhere | One window keeps every engine's "period" mentally consistent; configurable per engine |
| D-6 | No bags↔ton conversion | Cement-specific ("20 bags = 1 ton"). Quantities stay in `items.unit_of_measure`; conversion is a presentation concern if ever needed |
| D-7 | `items.standard_cost` added (nullable) | Cheapest possible enabler for product-margin and margin-quality parameters; NULL falls to defaults |
| D-8 | Competitive risk = manual enum on customer | Real signals (price undercutting, migration) need data we don't capture; a rep-maintained flag is honest. Revisit in 2D (LLM extraction from remarks) |
| D-9 | Lead scores persisted on write; cohort scores live-on-read + snapshot via recompute | Freshness without cache invalidation; trends via nightly recompute. Rejected: persisting every cohort score on every read (table bloat) |
| D-10 | LLM strictly Phase 2D | Deterministic engines are demo-able and testable without API keys, cost, or nondeterminism risk |
| D-11 | Single scoring framework; BU-specific frameworks (ADR-001) out of POC scope | `scoring_configs` (engine, version, params) + `config_id` on every snapshot means a Cement/TMT split later = new config rows + a routing rule |
| D-12 | Leads module is **local-only**; no Zoho Leads sync in this phase | Preserves the build order (Integration Layer last). `ZOHO_CRM_SPECIFICATION.md` §2 explicitly excluded Zoho Leads for Phase 1; extending sync is a future Integration Layer decision |

---

## 14. Out of scope (this phase)

- Zoho sync of any new entity (leads, activities, invoices) — D-12.
- Role hierarchy / role-based dashboards (CEO/NSM/RM views) — the POC has
  admin + user only; per-rep views are filtered by `rep_user_id`.
- ML/predictive models — everything here is deterministic by design.
- Planned-beat capture and `daily_visit_efficiency` / `beat_efficiency`
  (needs the 2C beat screen; noted in §7.3).
- Accounting beyond minimal invoices/payments (no credit limits, no ledger).
- Geocoding / lat-lon route optimization — clustering is district-based.

---

## 15. Delivery plan & gates

Per the project's phased-delivery rule: ship a phase, stop for user
testing, then proceed.

| Phase | Delivers | Gate |
|---|---|---|
| **2A — Data foundation** | Migrations + models + CRUD endpoints for leads, stage history, activities, targets, invoices/payments, customer/item extensions; seed script generating a realistic demo dataset (≈8 reps, ≈60 customers across ≈6 districts, ≈200 leads in all stages over 6 months, activities, targets, invoices with varied ageing) | All tests green; user exercises CRUD via `/docs`; seed data reviewed |
| **2B — Scoring engines** | `scoring_configs` + seeded v1 configs; four engines as pure, fully-tested service functions; snapshot tables; intelligence read endpoints; recompute endpoint | Canonical vectors verified by hand against this spec; user reviews scores over seed data |
| **2C — Frontend intelligence** | §10 surfaces | User testing on seeded data |
| **2D — LLM layer** | §11 | Grounding + determinism rules verified |

Each phase updates `execution.md` and, where conventions change,
`Backend/CLAUDE.md` / `Frontend/CLAUDE.md` in the same commit.
The slice-level work breakdown for phases 2A and 2B is §19; the live status
tracker is §20.

---

## 16. Backend module layout — additions

New files only; everything else in `Backend/CLAUDE.md` §3 is unchanged.
Two new concepts are sanctioned by this spec (which serves as the "ask
first" approval required by CLAUDE.md §3): the `services/scoring/`
subpackage and a `scripts/` folder at the Backend root. Record both in
`Backend/CLAUDE.md` when first created.

```
Backend/
├── scripts/
│   └── seed_demo.py                       # §18
├── src/app/
│   ├── api/v1/
│   │   ├── leads.py                       # §9.1
│   │   ├── activities.py                  # §9.2
│   │   ├── customer_targets.py            # §9.3 (router nested under /customers)
│   │   ├── invoices.py                    # §9.3
│   │   └── intelligence.py                # §9.4 + §9.5 (all /intelligence/*)
│   ├── models/
│   │   ├── lead.py                        # Lead + LeadStageHistory + enums
│   │   ├── sales_activity.py
│   │   ├── customer_target.py
│   │   ├── invoice.py                     # Invoice + Payment
│   │   ├── scoring_config.py
│   │   └── score_snapshot.py              # the 4 snapshot models
│   ├── schemas/
│   │   ├── lead.py
│   │   ├── sales_activity.py
│   │   ├── customer_target.py
│   │   ├── invoice.py
│   │   └── intelligence.py                # all §9.6 score/config/beat shapes
│   ├── services/
│   │   ├── lead_service.py
│   │   ├── sales_activity_service.py
│   │   ├── customer_target_service.py
│   │   ├── invoice_service.py
│   │   └── scoring/
│   │       ├── __init__.py
│   │       ├── config_service.py          # load/validate/activate configs
│   │       ├── lead_scoring.py            # §4
│   │       ├── customer_health.py         # §6
│   │       ├── effort_efficiency.py       # §5
│   │       ├── beat_planning.py           # §7
│   │       └── recompute_service.py       # §8
│   └── repositories/
│       ├── lead_repo.py                   # includes stage-history writes
│       ├── sales_activity_repo.py
│       ├── customer_target_repo.py
│       ├── invoice_repo.py                # invoices + payments
│       ├── scoring_config_repo.py
│       └── score_snapshot_repo.py         # insert + latest-per-entity reads
└── tests/
    ├── test_leads.py
    ├── test_lead_transitions.py
    ├── test_activities.py
    ├── test_customer_targets.py
    ├── test_invoices.py
    └── scoring/
        ├── test_scoring_configs.py
        ├── test_lead_scoring.py           # LS-1 + §4 band edges/defaults
        ├── test_customer_health.py        # CH-1 + §6
        ├── test_effort_efficiency.py      # EE-1 + §5 incl. cohort edges
        ├── test_beat_planning.py          # BP-1 + §7
        └── test_recompute.py
```

**Pure-function rule for engines** (what makes the canonical vectors
testable without a database): each engine module exposes

```python
def compute_lead_score(inputs: LeadScoringInputs, params: dict) -> LeadScoreResult: ...
```

— a pure function over plain dataclasses, no session, no I/O. A thin
orchestrator in the same module gathers `inputs` via repositories and
persists the snapshot. Unit tests hit the pure function with the §4–§7
vectors; integration tests hit the endpoint.

---

## 17. `scoring_configs.params` — exact JSON shapes (v1 defaults)

These are the rows the Alembic data-migration seeds (one active v1 per
engine). `POST /intelligence/configs` validates an incoming `params` against
the same shape (unknown keys → 422; weights must sum to 1.0 ± 0.001; band
lists must be ordered and gap-free).

### 17.1 LEAD_SCORING v1

```json
{
  "cohort_window_days": 90,
  "weights": { "urgency": 0.20, "location": 0.20, "contribution_margin": 0.20,
               "quantity": 0.20, "product_margin": 0.20 },
  "classification": { "hot_min": 80, "medium_min": 40 },
  "urgency_bands": [ { "max_days": 6, "score": 100 }, { "max_days": 30, "score": 70 },
                     { "max_days": 60, "score": 40 }, { "max_days": null, "score": 20 } ],
  "urgency_default": 40,
  "location_scores": { "full": 100, "partial": 50, "state_only": 30, "none": 0 },
  "budget_thresholds": { "high_min": 1000000, "medium_min": 250000 },
  "contribution_matrix": {
    "HIGH":   { "HIGH": 100, "MEDIUM": 70, "LOW": 40 },
    "MEDIUM": { "HIGH": 70,  "MEDIUM": 70, "LOW": 40 },
    "LOW":    { "HIGH": 40,  "MEDIUM": 40, "LOW": 10 } },
  "contribution_single_input": { "HIGH": 100, "MEDIUM": 70, "LOW": 40 },
  "contribution_default": 40,
  "quantity_ratio_bands": [ { "min_ratio": 0.75, "score": 100 }, { "min_ratio": 0.40, "score": 70 },
                            { "min_ratio": 0.15, "score": 40 }, { "min_ratio": 0.0, "score": 20 } ],
  "quantity_default": 40,
  "product_margin_bands": [ { "min_pct": 25, "score": 100 }, { "min_pct": 10, "score": 60 },
                            { "min_pct": 0, "score": 30 } ],
  "product_margin_default": 60
}
```

### 17.2 EFFORT_EFFICIENCY v1

```json
{
  "period_days_default": 90,
  "activity_weights": { "VISIT": 3, "MEETING": 4, "FOLLOW_UP": 2, "CALL": 1 },
  "time_points_per_hour": 1,
  "efficiency_weights": { "stage_change_rate": 0.20, "won_rate": 0.20,
                          "revenue_efficiency": 0.20, "time_to_close": 0.20,
                          "lead_score_utilization": 0.20 },
  "efficiency_bands": { "highly_efficient_min": 80, "efficient_min": 60,
                        "needs_improvement_min": 40 },
  "quadrant_thresholds": { "effort": 60, "efficiency": 60 }
}
```

### 17.3 CUSTOMER_HEALTH v1

```json
{
  "weight_profiles": { "standard": { "w_p": 0.60, "w_r": 0.40 },
                       "credit_stress": { "w_p": 0.55, "w_r": 0.45 },
                       "growth_expansion": { "w_p": 0.70, "w_r": 0.30 } },
  "default_profile": "standard",
  "classification": { "healthy_min": 80, "stable_min": 60, "at_risk_min": 40 },
  "cps_weights": { "volume_achievement": 0.30, "payment_discipline": 0.20,
                   "engagement": 0.20, "growth_trend": 0.15, "margin_quality": 0.15 },
  "crs_weights": { "volume_decline": 0.30, "payment_risk": 0.25,
                   "competitive_risk": 0.20, "engagement_gap": 0.15, "service_risk": 0.10 },
  "volume_achievement_default": 50,
  "dso_window_days": 180,
  "dso_bands": [ { "max_days": 30, "score": 100 }, { "max_days": 45, "score": 75 },
                 { "max_days": 60, "score": 50 }, { "max_days": 90, "score": 25 },
                 { "max_days": null, "score": 0 } ],
  "dso_default": 50,
  "engagement_window_days": 90,
  "engagement_bands": [ { "min_visits": 6, "score": 100 }, { "min_visits": 4, "score": 75 },
                        { "min_visits": 2, "score": 50 }, { "min_visits": 1, "score": 25 },
                        { "min_visits": 0, "score": 0 } ],
  "growth_bands": [ { "min_pct": 20, "score": 100 }, { "min_pct": 5, "score": 75 },
                    { "min_pct": -5, "score": 50 }, { "min_pct": -20, "score": 25 },
                    { "min_pct": null, "score": 0 } ],
  "growth_default": 50,
  "margin_bands": [ { "min_pct": 25, "score": 100 }, { "min_pct": 10, "score": 60 },
                    { "min_pct": 0, "score": 30 } ],
  "margin_default": 60,
  "decline_bands": [ { "min_pct": 50, "score": 100 }, { "min_pct": 25, "score": 70 },
                     { "min_pct": 10, "score": 40 }, { "min_pct": 0, "score": 0 } ],
  "payment_risk_bands": [ { "min_pct": 75, "score": 100 }, { "min_pct": 50, "score": 75 },
                          { "min_pct": 25, "score": 50 }, { "min_pct": 1, "score": 25 },
                          { "min_pct": 0, "score": 0 } ],
  "competitive_scores": { "NONE": 0, "LOW": 33, "MEDIUM": 66, "HIGH": 100 },
  "engagement_gap_weights": { "communication": 0.40, "activity": 0.60 },
  "comm_gap_bands": [ { "max_days": 7, "score": 0 }, { "max_days": 15, "score": 20 },
                      { "max_days": 30, "score": 40 }, { "max_days": 60, "score": 70 },
                      { "max_days": null, "score": 100 } ],
  "activity_gap_bands": [ { "max_days": 15, "score": 0 }, { "max_days": 30, "score": 25 },
                          { "max_days": 60, "score": 50 }, { "max_days": 90, "score": 75 },
                          { "max_days": null, "score": 100 } ],
  "service_risk_bands": [ { "min_complaints": 3, "score": 100 }, { "min_complaints": 2, "score": 70 },
                          { "min_complaints": 1, "score": 40 }, { "min_complaints": 0, "score": 0 } ]
}
```

### 17.4 BEAT_PLANNING v1

```json
{
  "weights": { "revenue": 0.35, "visit_gap": 0.25,
               "customer_type": 0.20, "location_density": 0.20 },
  "visit_gap_bands": [ { "max_days": 14, "score": 25 }, { "max_days": 29, "score": 50 },
                       { "max_days": 44, "score": 75 }, { "max_days": null, "score": 100 } ],
  "customer_type_scores": { "DEALER": 100, "SUB_DEALER": 80, "RETAILER": 70 },
  "priority_bands": { "critical_min": 80, "high_min": 60, "medium_min": 40 },
  "revenue_window_days": 90,
  "handled_window_days": 180,
  "cluster_lds_threshold": 0.50,
  "default_max_visits": 12
}
```

---

## 18. Seed dataset specification (`scripts/seed_demo.py`)

Without realistic data, none of the four engines can be validated or
demoed. The seed script is a Phase 2A deliverable with these rules:

- **Deterministic**: fixed RNG seed (42). Two runs on a fresh DB produce
  identical data. No wall-clock randomness; "today" is taken once at start.
- **Guarded**: refuses to run if any `leads` row exists, unless `--force`
  (which only proceeds, never deletes). Never run against a non-dev DB —
  reads the same `.env` as the app, so the guard is the safety net.
- **Run**: `uv run python scripts/seed_demo.py` from `Backend/`.

Volumes and distributions (tuned so every band of every engine is populated):

| Entity | Volume | Distribution |
|---|---|---|
| Users (reps) | 8 reps + 1 admin | 1 rep deliberately near-zero activity (cohort-edge case), 1 deliberately top performer |
| Customers | 60 | Types 30% DEALER / 30% SUB_DEALER / 40% RETAILER; 6 districts across 2 states with one dense district (≥12 customers for one rep → LDS > 0.50); `competitive_risk_level`: 70% NONE, 15% LOW, 10% MEDIUM, 5% HIGH |
| Items | 25 | `standard_cost` set on 80% (margins spread across <10 / 10–24 / ≥25%); 20% NULL (default-path coverage) |
| Leads | 200 over trailing 180 days | Stages: 25% NEW, 20% QUALIFICATION, 15% NEGOTIATION, 25% WON, 15% LOST; full stage-history chains; ~15% sparse leads (most scoring inputs NULL) to exercise defaults; quantities spread to hit every ratio band |
| Activities | ~2,000 over 180 days | Mix of all five types; per-customer visit recency spread across every visit-gap band; durations 15–120 min; ~5% COMPLAINT |
| Targets | 1 per customer per quarter (2 quarters) | Achievement outcomes spread across <50%, 50–99%, ≥100% |
| Sales orders | reuse Phase 1 mechanism | Enough SHIPPED orders per customer to produce growth/decline trends in both directions |
| Invoices / payments | for ~70% of shipped SOs | Paid with DSO spread across every band; ~20% of open invoices overdue |

Acceptance: after seeding + `POST /intelligence/recompute`, every
classification bucket of every engine is non-empty (HOT/MEDIUM/COLD;
all four health classes; all four quadrants; all four visit priorities).
The seed script asserts this and exits non-zero otherwise.

---

## 19. Work breakdown — implementation slices

Each slice follows `Backend/CLAUDE.md` §5: restate spec → failing tests →
minimal implementation → green → ruff/mypy. One Alembic migration per
slice. A slice is the unit of commit/PR; don't batch slices.

### Phase 2A — data foundation

| Slice | Scope | Files (new unless noted) | Key tests |
|---|---|---|---|
| **2A.1** Customer + item extensions | §3.5, §3.6 columns; expose in existing CRUD schemas/endpoints | edit `models/customer.py`, `models/item.py`, their schemas + routers; migration with RETAILER/NONE backfill | PATCH accepts new fields; defaults backfilled; CHECK `standard_cost >= 0` |
| **2A.2** Leads + stage history | §3.2, §3.3, §9.1; `lead_number` generator (reuse the `so_number` pattern); transition service writes history atomically | `models/lead.py`, `schemas/lead.py`, `repositories/lead_repo.py`, `services/lead_service.py`, `api/v1/leads.py`; migration | full §12.5 matrix; creation writes NEW history row; WON/LOST consistency CHECKs via direct insert; filters |
| **2A.3** Activities | §3.4, §9.2 | `models/sales_activity.py`, schemas, repo, service, `api/v1/activities.py`; migration | subject CHECK; rep defaulting; append-only (no PATCH/DELETE routes); filters |
| **2A.4** Targets | §3.7, §9.3 | `models/customer_target.py`, schemas, repo, service, `api/v1/customer_targets.py`; migration | unique period 409; period-order 422 |
| **2A.5** Invoices + payments | §3.8, §9.3; number generator | `models/invoice.py`, schemas, repo, service, `api/v1/invoices.py`; migration | OVERPAYMENT 409; due-date CHECK; outstanding/overdue derivation |
| **2A.6** Seed script | §18 | `scripts/seed_demo.py` | determinism (two runs, fresh DBs, identical counts); guard refuses second run; acceptance assertion |

**Gate 2A:** all green; user exercises CRUD via `/docs` on seeded data.

### Phase 2B — scoring engines

| Slice | Scope | Files | Key tests |
|---|---|---|---|
| **2B.0** Config infrastructure | §3.9, §17; data-migration seeding v1×4; validation rules; admin endpoints | `models/scoring_config.py`, `repositories/scoring_config_repo.py`, `services/scoring/config_service.py`, `api/v1/intelligence.py` (configs routes); migration | one-active partial index; weight-sum 422; version auto-increment; activation swap |
| **2B.1** Lead scoring engine | §4 pure functions + orchestration; `lead_scores` snapshot; write-triggers in `lead_service`; §9.4 lead-score endpoints | `services/scoring/lead_scoring.py`, `models/score_snapshot.py` (LeadScore), `repositories/score_snapshot_repo.py`, intelligence routes; migration | **LS-1**; every §4 band edge; every default + `defaults_applied`; recompute-on-PATCH trigger |
| **2B.2** Customer health engine | §6 pure functions; live GET; snapshot model | `services/scoring/customer_health.py`, snapshot model ext., routes | **CH-1**; §6.1/§6.2 band edges; normalization identity (`health = raw + 100·W_R`); no-data customer scores with defaults |
| **2B.3** Effort & efficiency engine | §5; live GET; snapshot model | `services/scoring/effort_efficiency.py`, routes | **EE-1**; cohort edges (single rep, zero activity, zero won); inverted time-to-close; utilization excludes non-lead effort |
| **2B.4** Beat planning engine | §7; live GET | `services/scoring/beat_planning.py`, routes | **BP-1**; LDS with NULL district; cluster threshold; max_visits truncation; tie-break by cluster |
| **2B.5** Recompute + snapshots | §8 endpoint; snapshots for 2B.2–2B.4; nightly invocation documented in Backend README | `services/scoring/recompute_service.py`, route | snapshot rows carry active `config_id`; new config version → recompute → new version on rows; counts in response |

**Gate 2B:** canonical vectors hand-verified against §4–§7; user reviews
scores over seed data via `/docs`.

### Phase 2C — frontend (slice plan written when 2C starts)

Scope is §10; the slice breakdown follows the Frontend's established
phase pattern (feature folder per surface: leads → activities → health →
performance → beat plan → dashboard widgets) and extends
`Frontend/UI_SPECIFICATION.md` first. Backend is frozen during 2C except
bug fixes.

### Phase 2D — LLM layer (contract in §11; slice plan written when 2D starts)

---

## 20. Status tracker

Update this table in the same commit as the work it describes. "Done" means
the slice's Definition of Done (CLAUDE.md §13) is fully met.

| Slice | Status | Date | Notes |
|---|---|---|---|
| Spec (this document) | ✅ Done | 2026-06-10 | |
| 2A.1 Customer + item extensions | ✅ Done | 2026-06-16 | migration `b8d4f2a17c93`; `customer_type`/location/`competitive_risk_level` on customers, `standard_cost` on items; 9 tests (292 total); ruff+mypy clean |
| 2A.2 Leads + stage history | ✅ Done | 2026-06-16 | migration `c5e1a9b3f7d2`; `leads` + append-only `lead_stage_history`; `LD-YYYYMM-NNNNNN` generator; transition state machine + WON/LOST consistency CHECKs; 24 tests; ruff+mypy clean |
| 2A.3 Activities | ✅ Done | 2026-06-16 | migration `d2f4a6c8e1b3`; append-only `sales_activities`; subject-required + duration CHECKs; rep defaulting; no PATCH/DELETE; 8 tests; ruff+mypy clean |
| 2A.4 Targets | ✅ Done | 2026-06-16 | migration `e3a5b7d9f2c4`; `customer_targets` nested under `/customers`; period-order 422; non-overlap 409; 8 tests; ruff+mypy clean |
| 2A.5 Invoices + payments | ✅ Done | 2026-06-16 | migration `f4b6c8e0a3d5`; `invoices`+`payments`; `INV-YYYYMM-NNNNNN` generator; derived outstanding/overdue; OVERPAYMENT 409; 9 tests; ruff+mypy clean |
| 2A.6 Seed script | ✅ Done | 2026-06-16 | `scripts/seed_demo.py` — deterministic (seed 42 + seeded UUIDs), guarded (refuses 2nd run w/o `--force`), acceptance-asserting; seeds 9 users / 25 items / 60 customers / 120 targets / 200 leads / 480 history / 1224 activities / 87 invoices / 65 payments. (SHIPPED-SO/dispatch enrichment deferred to 2B where the health engine consumes it.) |
| **Gate 2A — user testing** | 🟢 Ready | 2026-06-16 | All 2A slices green; dev DB migrated + seeded. Awaiting user testing via `/docs` before Phase 2B. |
| 2B.0 Config infrastructure | ✅ Done | 2026-06-18 | migration `a7c3e5f1b9d2`; `scoring_configs` (engine,version) + partial unique one-active-per-engine index; seeds v1 active ×4 from frozen `default_configs.py` (§17); `config_service` validation (weight-sum, unknown-key, band monotonicity → 422); admin `GET/POST /intelligence/configs` with version auto-increment + activation swap; 10 tests; ruff+mypy clean |
| 2B.1 Lead scoring engine | ✅ Done | 2026-06-18 | migration `b1d3f5a7c9e2`; pure `compute_lead_score` (§4) + `lead_scores` snapshot + `score_snapshot_repo`; write-triggers in `lead_service` (create / scoring-input PATCH / transition); `GET /intelligence/lead-scores[/{id}]`; leads now carry `latest_score` (+ full breakdown on detail). 55 tests (LS-1 + every band edge + every default + classification edges + write-trigger integration); ruff+mypy clean |
| 2B.2 Customer health engine | ✅ Done | 2026-06-18 | migration `c2e4f6a8b1d3`; pure `compute_customer_health` + `aggregate_health` (§6) — CH-1 + normalization identity (`health = raw + 100·W_R`) + every component band edge + no-data defaults; `customer_metrics_repo` (dispatch/revenue/margin/DSO/AR/activity aggregates); live `GET /intelligence/customer-health[/{id}]` (+ snapshot trend); `customer_health_scores` snapshot model. 13 new tests (68 scoring total); ruff+mypy clean |
| 2B.3 Effort & efficiency engine | ✅ Done | 2026-06-18 | migration `d3f5a7c9e1b4`; pure `compute_effort_efficiency` (cohort-relative; §5) — EE-1 + cohort edges (single rep, zero activity, zero won, zero assigned) + inverted time-to-close + utilization + band/quadrant edges; `rep_metrics_repo` (per-rep effort counts, lead outcomes, HOT-lead effort points); live `GET /intelligence/effort-efficiency[/{user_id}]` (period override); `effort_efficiency_scores` snapshot model + `effort_quadrant` enum. 11 new tests (79 scoring total); ruff+mypy clean |
| 2B.4 Beat planning engine | ⬜ Not started | | |
| 2B.5 Recompute + snapshots | ⬜ Not started | | |
| **Gate 2B — user testing** | ⬜ | | |
| 2C Frontend surfaces | ⬜ Not started | | slice plan TBD at start |
| 2D LLM layer | ⬜ Not started | | slice plan TBD at start |

**How to resume work in a fresh session:** read this file top to bottom,
check §20 for the first incomplete slice, read §19 for that slice's scope,
then follow `Backend/CLAUDE.md` §5 (spec restatement → failing tests →
implement). All formulas, bands, defaults, schemas, and config shapes
needed for any slice are in §3–§9 and §16–§18 of this document — no other
source document is required.
