"""add composite index (customer_id, status, shipped_date) on sales_orders

Revision ID: a1c3e5b7d9f2
Revises: f4b6c8e0a3d5
Create Date: 2026-07-02 00:00:00.000000

The Intelligence service's customer-health and beat-planning engines issue
six aggregate queries per customer that all filter on
``(customer_id, status = SHIPPED, shipped_date IN window)``.  The existing
single-column index on ``customer_id`` alone leaves Postgres scanning all
orders for that customer and then re-filtering on status + shipped_date.

A single composite index covering all three columns turns those scans into
index-range lookups regardless of how many orders a customer has, and is also
used by the nightly recompute run (``POST /intelligence/recompute``).

The index is non-unique and non-partial so it is safe to add online without
locking the table.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "a1c3e5b7d9f2"
down_revision: str | None = "f4b6c8e0a3d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_sales_orders_customer_id_status_shipped_date",
        "sales_orders",
        ["customer_id", "status", "shipped_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sales_orders_customer_id_status_shipped_date",
        table_name="sales_orders",
    )
