"""add customer_targets (Phase 2A.4)

Revision ID: e3a5b7d9f2c4
Revises: d2f4a6c8e1b3
Create Date: 2026-06-16 01:30:00.000000

Phase 2A.4 — per-customer volume/revenue targets (the denominator of the
customer-health volume-achievement component). Purely additive. See
``INTELLIGENCE_SPECIFICATION.md`` §3.7.

Hand-written to match the existing migration conventions.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3a5b7d9f2c4"
down_revision: str | None = "d2f4a6c8e1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_targets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("target_quantity", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("target_revenue", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("period_end > period_start", name="ck_customer_targets_period_order"),
        sa.CheckConstraint("target_quantity > 0", name="ck_customer_targets_quantity_positive"),
        sa.CheckConstraint(
            "target_revenue IS NULL OR target_revenue >= 0",
            name="ck_customer_targets_revenue_non_negative",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_id", "period_start", "period_end",
            name="uq_customer_targets_customer_period",
        ),
    )
    op.create_index(op.f("ix_customer_targets_customer_id"), "customer_targets", ["customer_id"], unique=False)
    op.create_index(op.f("ix_customer_targets_created_by_user_id"), "customer_targets", ["created_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("customer_targets")
