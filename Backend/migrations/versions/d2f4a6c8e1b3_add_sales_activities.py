"""add sales_activities (Phase 2A.3)

Revision ID: d2f4a6c8e1b3
Revises: c5e1a9b3f7d2
Create Date: 2026-06-16 01:00:00.000000

Phase 2A.3 — the append-only sales-activity ledger. Purely additive.
See ``INTELLIGENCE_SPECIFICATION.md`` §3.4.

Hand-written to match the existing migration conventions.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d2f4a6c8e1b3"
down_revision: str | None = "c5e1a9b3f7d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


activity_type = postgresql.ENUM(
    "VISIT", "MEETING", "FOLLOW_UP", "CALL", "COMPLAINT",
    name="activity_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    activity_type.create(bind, checkfirst=True)

    op.create_table(
        "sales_activities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("type", activity_type, nullable=False),
        sa.Column("rep_user_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=True),
        sa.Column("lead_id", sa.UUID(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name="ck_sales_activities_duration_positive",
        ),
        sa.CheckConstraint(
            "customer_id IS NOT NULL OR lead_id IS NOT NULL",
            name="ck_sales_activities_has_subject",
        ),
        sa.ForeignKeyConstraint(["rep_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sales_activities_type"), "sales_activities", ["type"], unique=False)
    op.create_index(op.f("ix_sales_activities_rep_user_id"), "sales_activities", ["rep_user_id"], unique=False)
    op.create_index(op.f("ix_sales_activities_customer_id"), "sales_activities", ["customer_id"], unique=False)
    op.create_index(op.f("ix_sales_activities_lead_id"), "sales_activities", ["lead_id"], unique=False)
    op.create_index(op.f("ix_sales_activities_created_by_user_id"), "sales_activities", ["created_by_user_id"], unique=False)
    op.create_index(
        "ix_sales_activities_customer_id_occurred_at",
        "sales_activities",
        ["customer_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_sales_activities_rep_user_id_occurred_at",
        "sales_activities",
        ["rep_user_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_table("sales_activities")
    activity_type.drop(bind, checkfirst=True)
