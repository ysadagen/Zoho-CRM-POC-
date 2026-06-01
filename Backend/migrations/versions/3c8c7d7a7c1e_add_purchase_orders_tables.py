"""add purchase_orders + purchase_order_items tables

Revision ID: 3c8c7d7a7c1e
Revises: 0fe7e33f61e6
Create Date: 2026-06-01 11:16:40

Creates the Phase 7 schema:

* ``purchase_order_status`` ENUM (DRAFT, RECEIVED)
* ``purchase_orders`` header table with DB-level invariants:
  - ``subtotal >= 0``, ``total >= 0``
  - ``status`` ↔ ``received_date`` consistency
* ``purchase_order_items`` line table with:
  - ``quantity > 0``, ``unit_price >= 0``, ``line_total >= 0``
  - UNIQUE (purchase_order_id, item_id) — no duplicate lines per PO
* ``purchase_order_number_seq`` SEQUENCE — backs the ``PO-YYYYMM-NNNNNN``
  human-readable identifier. Non-transactional by design so a rolled-back
  PO leaves a visible gap, which is the right trade-off here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3c8c7d7a7c1e"
down_revision: str | None = "0fe7e33f61e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS purchase_order_number_seq")

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("po_number", sa.String(length=50), nullable=False),
        sa.Column("vendor_id", sa.UUID(), nullable=False),
        sa.Column(
            "order_date",
            sa.Date(),
            server_default=sa.text("CURRENT_DATE"),
            nullable=False,
        ),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("received_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "RECEIVED", name="purchase_order_status"),
            server_default="DRAFT",
            nullable=False,
        ),
        sa.Column("subtotal", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "subtotal >= 0", name="ck_purchase_orders_subtotal_non_negative"
        ),
        sa.CheckConstraint(
            "total >= 0", name="ck_purchase_orders_total_non_negative"
        ),
        sa.CheckConstraint(
            "(status = 'RECEIVED' AND received_date IS NOT NULL) "
            "OR (status = 'DRAFT' AND received_date IS NULL)",
            name="ck_purchase_orders_status_received_date_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"], ["vendors.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_purchase_orders_po_number"),
        "purchase_orders",
        ["po_number"],
        unique=True,
    )
    op.create_index(
        op.f("ix_purchase_orders_vendor_id"),
        "purchase_orders",
        ["vendor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_purchase_orders_status"),
        "purchase_orders",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_purchase_orders_created_by_user_id"),
        "purchase_orders",
        ["created_by_user_id"],
        unique=False,
    )

    op.create_table(
        "purchase_order_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("purchase_order_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity > 0", name="ck_purchase_order_items_quantity_positive"
        ),
        sa.CheckConstraint(
            "unit_price >= 0",
            name="ck_purchase_order_items_unit_price_non_negative",
        ),
        sa.CheckConstraint(
            "line_total >= 0",
            name="ck_purchase_order_items_line_total_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"],
            ["purchase_orders.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"], ["items.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "purchase_order_id",
            "item_id",
            name="uq_purchase_order_items_purchase_order_id_item_id",
        ),
    )
    op.create_index(
        op.f("ix_purchase_order_items_purchase_order_id"),
        "purchase_order_items",
        ["purchase_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_purchase_order_items_item_id"),
        "purchase_order_items",
        ["item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_purchase_order_items_item_id"),
        table_name="purchase_order_items",
    )
    op.drop_index(
        op.f("ix_purchase_order_items_purchase_order_id"),
        table_name="purchase_order_items",
    )
    op.drop_table("purchase_order_items")

    op.drop_index(
        op.f("ix_purchase_orders_created_by_user_id"),
        table_name="purchase_orders",
    )
    op.drop_index(op.f("ix_purchase_orders_status"), table_name="purchase_orders")
    op.drop_index(
        op.f("ix_purchase_orders_vendor_id"), table_name="purchase_orders"
    )
    op.drop_index(
        op.f("ix_purchase_orders_po_number"), table_name="purchase_orders"
    )
    op.drop_table("purchase_orders")

    op.execute("DROP TYPE IF EXISTS purchase_order_status")
    op.execute("DROP SEQUENCE IF EXISTS purchase_order_number_seq")
