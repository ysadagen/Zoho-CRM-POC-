# Inventory Management + Zoho CRM Integration

## Overview

This project is a Phase 1 proof of concept for a manufacturing business that manages raw materials, finished products, vendors, customers, purchase orders, and sales orders.

The system is intentionally kept simple. The Inventory Application is responsible for stock and operational records, while Zoho CRM is used for customer/vendor relationship history, transaction visibility, reminders, tasks, and dashboard-level tracking.

The architecture is designed so the current POC can remain lightweight, while still leaving enough separation to scale the system later.

## System Architecture

The application has three main parts:

```text
React Frontend
    ↓
Inventory Backend - FastAPI
    ↓
Inventory DB - PostgreSQL
```

The backend communicates with Zoho through a separate integration service:

```text
Inventory Backend - FastAPI
    ↓ Internal API
Integration Layer - FastAPI
    ↓
Integration DB - PostgreSQL
    ↓
Zoho CRM Core APIs
    ↓
Zoho CRM
```

For Phase 1, both databases can run on the same PostgreSQL server as separate logical databases:

```text
PostgreSQL Server
  ├── inventory_db
  └── integration_db
```

This keeps the infrastructure simple while keeping business data and integration data separate.

## Responsibilities

The Inventory Application manages the operational side of the business. It stores items, customers, vendors, purchase orders, sales orders, and stock movements. It is the source of truth for stock.

Zoho CRM manages the relationship side of the business. It stores customer/vendor history, transaction visibility, tasks, reminders, notes, and CRM dashboards.

The Integration Layer sits between both systems. It handles Zoho API communication, OAuth tokens, CRM record mappings, sync logs, retries, and webhook events. The Inventory Backend does not call Zoho directly.

## Business Scope

The company maintains raw material stock for Raw Plastic and Raw Steel. It sells finished water bottles in three sizes: Small, Medium, and Large.

Purchase orders increase raw material stock. Sales orders reduce finished product stock. Every stock change is recorded in the stock movement table so the system has a clear audit trail.

Zoho CRM receives synchronized customer, vendor, sales order, and purchase order information so the team can view history, assign tasks, set reminders, and track customer/vendor activity.

## Database Design

The project uses two databases.

The Inventory DB stores business and stock-related data:

```text
users
customers
vendors
items
vendor_item_terms
purchase_orders
purchase_order_items
sales_orders
sales_order_items
stock_movements
```

The Integration DB stores CRM synchronization data:

```text
crm_mappings
sync_logs
idempotency_keys
zoho_tokens
webhook_events
```

The `items` table stores both raw materials and finished products. The `stock_movements` table is used as the audit trail for all stock changes.

## Core Workflow

A typical sales flow starts when a customer order is created in the Inventory Application. The system validates available stock, saves the sales order, reduces finished product stock, and records a stock movement. After the local transaction is saved, the backend sends a sync request to the Integration Layer, which updates Zoho CRM with the relevant customer and transaction history.

A purchase flow works similarly. When a purchase order is received, raw material stock is increased, a stock movement is recorded, and the Integration Layer syncs the transaction to Zoho CRM under the relevant vendor history.

Local inventory operations should not fail just because Zoho CRM is unavailable. If a Zoho sync fails, the failure is stored in `sync_logs` and can be retried.

## Technology Stack

```text
Frontend: React
Backend: FastAPI
Integration Layer: FastAPI
Database: PostgreSQL
ORM: SQLAlchemy
Migrations: Alembic
Validation: Pydantic
CRM: Zoho CRM
CRM Integration: Zoho CRM Core APIs
Authentication: JWT + Zoho OAuth 2.0
```

Redis and Celery may be added later if background sync becomes necessary.

## Development Approach

The first milestone is to complete the Inventory Application independently. Items, vendors, customers, purchase orders, sales orders, and stock movements should work before Zoho integration is added.

After that, the Integration Layer should be connected step by step: first customer sync, then vendor sync, then sales order sync, and finally purchase order sync.

The system should maintain sync logs, CRM mappings, and idempotency keys so repeated sync attempts do not create duplicate Zoho records.

## Phase 1 Completion Criteria

Phase 1 is complete when the Inventory Application works independently, stock movements are correctly recorded, customer/vendor/order data syncs to Zoho CRM, failed syncs are logged, and the team can view useful customer and vendor history inside Zoho CRM.

The POC should remain simple. Advanced features such as production planning, accounting integration, barcode scanning, multi-warehouse inventory, Kafka, and full two-way sync are intentionally out of scope for this phase.

## Repository Layout

This is a **monorepo with multiple deployable services**. One Git repo, three
services, one shared local Postgres for dev.

```
Code/
├── docker-compose.yml          # one Postgres server for both services
├── db/                         # shared infra (Dockerfile + init SQL)
│   ├── Dockerfile              # builds inventory-crm-postgres:local
│   └── init/
│       └── 01-create-databases.sql   # creates inventory_db + integration_db
│
├── Backend/                    # FastAPI — source of truth for inventory
│   ├── CLAUDE.md               # engineering contract — read before changing code
│   ├── README.md               # service-specific quickstart
│   ├── .env.example            # required env vars (copy to .env)
│   ├── pyproject.toml          # Python deps (managed by uv)
│   └── src/app/                # source (created during Phase 1)
│
├── Integration Layer/          # FastAPI — talks to Zoho on behalf of Backend
│   ├── CLAUDE.md
│   ├── README.md
│   ├── .env.example
│   └── pyproject.toml
│
├── Frontend/                   # React (later phase)
│
└── README.md                   # you are here
```

Each service owns its own database (`inventory_db`, `integration_db`), its
own dependencies, its own lifecycle. They communicate over HTTP. The
Frontend talks only to the Backend. The Backend talks only to the
Integration Layer for CRM concerns. The Integration Layer is the **only**
service that talks to Zoho.

---

## Local Development Setup

For a brand-new contributor on a Windows machine. The whole flow assumes
**PowerShell** — don't mix Git Bash, it has path-translation quirks with
Docker on Windows.

### One-time per machine

Install:

1. **Python 3.14** — <https://www.python.org/downloads/>
2. **uv** (Python package manager) — `irm https://astral.sh/uv/install.ps1 | iex`
3. **Docker Desktop** — <https://www.docker.com/products/docker-desktop/>. Make sure WSL2 backend is enabled.
4. **Git** — <https://git-scm.com/>
5. *(Optional)* **pgAdmin 4** — <https://www.pgadmin.org/download/> for a database GUI.

Verify:

```powershell
python --version        # 3.14.x
uv --version
docker --version
docker info             # must succeed; if it fails, start Docker Desktop
```

### First-time setup of this repo

Clone, then from the `Code/` directory:

```powershell
# 1. Start the shared Postgres server (creates inventory_db + integration_db)
docker compose up -d --build
docker compose ps                                       # wait for (healthy)
docker compose exec db psql -U postgres -P pager=off -c "\l"
# Expect: inventory_db, integration_db, postgres, template0, template1

# 2. Configure each service. Copy each .env.example -> .env, then fill in
#    secrets. Generate a JWT secret with:
python -c "import secrets; print(secrets.token_urlsafe(64))"

cd Backend
copy .env.example .env
# edit .env: paste a strong value into JWT_SECRET_KEY,
# and another strong value into INTEGRATION_LAYER_API_KEY
uv sync

cd "..\Integration Layer"
copy .env.example .env
# edit .env: paste the SAME value used for the Backend's
# INTEGRATION_LAYER_API_KEY into INTERNAL_API_KEY here.
# Also fill in ZOHO_* values from the Zoho API Console when you have them.
uv sync
```

> ⚠ **Critical pairing:** `Backend/.env.INTEGRATION_LAYER_API_KEY` must equal
> `Integration Layer/.env.INTERNAL_API_KEY`. They are the shared secret for
> internal service-to-service auth. If they don't match, every Backend → IL
> call returns 401.

### Daily development

```powershell
# bring DB up (if not already running)
docker compose up -d

# Backend
cd Backend
uv run uvicorn app.main:app --reload --app-dir src --port 8000

# Integration Layer (in another PowerShell window)
cd "Integration Layer"
uv run uvicorn app.main:app --reload --app-dir src --port 8001
```

OpenAPI docs:
- Backend: <http://localhost:8000/docs>
- Integration Layer: <http://localhost:8001/docs>

> Until the app code is written (Phase 1 of each service), the `uvicorn`
> commands will fail because `app.main` doesn't exist yet. The DB and env
> setup above are still valid prerequisites.

### Stopping / resetting

```powershell
docker compose down            # stop, keep data
docker compose down -v         # stop AND wipe DB volume (also re-runs init scripts)
docker compose logs -f db      # tail Postgres logs
```

### Per-service commands

Each service has its own deeper command list in its README:

- [Backend/README.md](./Backend/README.md) — tests, lint, migrations, etc.
- [Integration Layer/README.md](./Integration%20Layer/README.md) — same plus webhook + idempotency notes.

---

## Where to read what

| If you want to … | Read |
|---|---|
| Understand the system at a glance | This file (sections above) |
| Run the project locally for the first time | This file → *Local Development Setup* |
| Change code in the Backend | [`Backend/CLAUDE.md`](./Backend/CLAUDE.md) |
| Change code in the Integration Layer | [`Integration Layer/CLAUDE.md`](./Integration%20Layer/CLAUDE.md) |
| Add a new env var | The service's `.env.example` + `app/core/config.py` |
| Add a new database | `db/init/01-create-databases.sql` + `docker compose down -v && docker compose up -d --build` |

---

## References

* FastAPI: https://fastapi.tiangolo.com/
* PostgreSQL: https://www.postgresql.org/docs/
* SQLAlchemy: https://docs.sqlalchemy.org/
* Alembic: https://alembic.sqlalchemy.org/
* Zoho CRM API v8: https://www.zoho.com/crm/developer/docs/api/v8/
* Zoho OAuth: https://www.zoho.com/crm/developer/docs/api/v8/oauth-overview.html
