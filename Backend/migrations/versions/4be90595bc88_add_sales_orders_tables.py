"""add sales_orders + sales_order_items tables

Revision ID: 4be90595bc88
Revises: 3c8c7d7a7c1e
Create Date: 2026-06-01 12:00:00

Creates the Phase 8 schema, mirroring the Phase 7 PO setup:

* ``sales_order_status`` ENUM (DRAFT, SHIPPED)
* ``sales_orders`` header table with DB-level invariants:
  - ``subtotal >= 0``, ``total >= 0``
  - ``status`` ↔ ``shipped_date`` consistency
* ``sales_order_items`` line table with:
  - ``quantity > 0``, ``unit_price >= 0``, ``line_total >= 0``
  - UNIQUE (sales_order_id, item_id)
* ``sales_order_number_seq`` SEQUENCE — backs the ``SO-YYYYMM-NNNNNN``
  identifier (non-transactional, may leave gaps on rollback — same
  trade-off documented in the PO migration).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4be90595bc88"
down_revision: str | None = "3c8c7d7a7c1e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS sales_order_number_seq")

    op.create_table(
        "sales_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("so_number", sa.String(length=50), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column(
            "order_date",
            sa.Date(),
            server_default=sa.text("CURRENT_DATE"),
            nullable=False,
        ),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("shipped_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "SHIPPED", name="sales_order_status"),
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
            "subtotal >= 0", name="ck_sales_orders_subtotal_non_negative"
        ),
        sa.CheckConstraint("total >= 0", name="ck_sales_orders_total_non_negative"),
        sa.CheckConstraint(
            "(status = 'SHIPPED' AND shipped_date IS NOT NULL) "
            "OR (status = 'DRAFT' AND shipped_date IS NULL)",
            name="ck_sales_orders_status_shipped_date_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], ondelete="RESTRICT"
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
        op.f("ix_sales_orders_so_number"),
        "sales_orders",
        ["so_number"],
        unique=True,
    )
    op.create_index(
        op.f("ix_sales_orders_customer_id"),
        "sales_orders",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sales_orders_status"),
        "sales_orders",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sales_orders_created_by_user_id"),
        "sales_orders",
        ["created_by_user_id"],
        unique=False,
    )

    op.create_table(
        "sales_order_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("sales_order_id", sa.UUID(), nullable=False),
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
            "quantity > 0", name="ck_sales_order_items_quantity_positive"
        ),
        sa.CheckConstraint(
            "unit_price >= 0",
            name="ck_sales_order_items_unit_price_non_negative",
        ),
        sa.CheckConstraint(
            "line_total >= 0",
            name="ck_sales_order_items_line_total_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["sales_order_id"],
            ["sales_orders.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sales_order_id",
            "item_id",
            name="uq_sales_order_items_sales_order_id_item_id",
        ),
    )
    op.create_index(
        op.f("ix_sales_order_items_sales_order_id"),
        "sales_order_items",
        ["sales_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sales_order_items_item_id"),
        "sales_order_items",
        ["item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_sales_order_items_item_id"),
        table_name="sales_order_items",
    )
    op.drop_index(
        op.f("ix_sales_order_items_sales_order_id"),
        table_name="sales_order_items",
    )
    op.drop_table("sales_order_items")

    op.drop_index(
        op.f("ix_sales_orders_created_by_user_id"),
        table_name="sales_orders",
    )
    op.drop_index(op.f("ix_sales_orders_status"), table_name="sales_orders")
    op.drop_index(op.f("ix_sales_orders_customer_id"), table_name="sales_orders")
    op.drop_index(op.f("ix_sales_orders_so_number"), table_name="sales_orders")
    op.drop_table("sales_orders")

    op.execute("DROP TYPE IF EXISTS sales_order_status")
    op.execute("DROP SEQUENCE IF EXISTS sales_order_number_seq")
