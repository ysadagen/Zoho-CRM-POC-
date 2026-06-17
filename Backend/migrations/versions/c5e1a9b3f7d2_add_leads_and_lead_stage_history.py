"""add leads + lead_stage_history (Phase 2A.2)

Revision ID: c5e1a9b3f7d2
Revises: b8d4f2a17c93
Create Date: 2026-06-16 00:30:00.000000

Phase 2A.2 of the intelligence layer — the central ``leads`` entity and its
append-only ``lead_stage_history`` trail. Purely additive. See
``INTELLIGENCE_SPECIFICATION.md`` §3.2–§3.3.

What this does:

* New enum types ``lead_stage``, ``lead_source``, ``dealer_potential``.
* ``lead_number_seq`` SEQUENCE — backs the ``LD-YYYYMM-NNNNNN`` identifier
  (mirrors ``sales_order_number_seq``).
* ``leads`` table with money/quantity CHECKs and the WON/LOST terminal-state
  consistency CHECKs.
* ``lead_stage_history`` table (append-only; ON DELETE CASCADE from leads).

Hand-written to match the existing migration conventions.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c5e1a9b3f7d2"
down_revision: str | None = "b8d4f2a17c93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


lead_stage = postgresql.ENUM(
    "NEW", "QUALIFICATION", "NEGOTIATION", "WON", "LOST",
    name="lead_stage",
    create_type=False,
)
lead_source = postgresql.ENUM(
    "PHONE_IN", "WALK_IN", "REFERENCE", "CAMPAIGN", "FIELD_VISIT", "OTHER",
    name="lead_source",
    create_type=False,
)
dealer_potential = postgresql.ENUM(
    "HIGH", "MEDIUM", "LOW",
    name="dealer_potential",
    create_type=False,
)

_ALL_ENUMS = (lead_stage, lead_source, dealer_potential)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in _ALL_ENUMS:
        enum.create(bind, checkfirst=True)

    op.execute("CREATE SEQUENCE IF NOT EXISTS lead_number_seq")

    # --- leads ------------------------------------------------------------
    op.create_table(
        "leads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lead_number", sa.String(length=32), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=True),
        sa.Column("contact_name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=160), nullable=True),
        sa.Column("item_id", sa.UUID(), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("estimated_budget", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("dealer_potential", dealer_potential, nullable=True),
        sa.Column("required_by_date", sa.Date(), nullable=True),
        sa.Column("source", lead_source, nullable=False),
        sa.Column("stage", lead_stage, server_default="NEW", nullable=False),
        sa.Column("assigned_to_user_id", sa.UUID(), nullable=False),
        sa.Column("state", sa.String(length=120), nullable=True),
        sa.Column("district", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("pincode", sa.String(length=20), nullable=True),
        sa.Column("won_value", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("won_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_reason", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_leads_quantity_positive"),
        sa.CheckConstraint(
            "estimated_budget IS NULL OR estimated_budget >= 0",
            name="ck_leads_estimated_budget_non_negative",
        ),
        sa.CheckConstraint("won_value IS NULL OR won_value > 0", name="ck_leads_won_value_positive"),
        sa.CheckConstraint(
            "(stage = 'WON') = (won_at IS NOT NULL AND won_value IS NOT NULL)",
            name="ck_leads_won_consistency",
        ),
        sa.CheckConstraint(
            "(stage = 'LOST') = (lost_at IS NOT NULL AND lost_reason IS NOT NULL)",
            name="ck_leads_lost_consistency",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lead_number", name="uq_leads_lead_number"),
    )
    op.create_index(op.f("ix_leads_lead_number"), "leads", ["lead_number"], unique=False)
    op.create_index(op.f("ix_leads_customer_id"), "leads", ["customer_id"], unique=False)
    op.create_index(op.f("ix_leads_item_id"), "leads", ["item_id"], unique=False)
    op.create_index(op.f("ix_leads_stage"), "leads", ["stage"], unique=False)
    op.create_index(op.f("ix_leads_assigned_to_user_id"), "leads", ["assigned_to_user_id"], unique=False)
    op.create_index(op.f("ix_leads_created_by_user_id"), "leads", ["created_by_user_id"], unique=False)

    # --- lead_stage_history (append-only) ---------------------------------
    op.create_table(
        "lead_stage_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("from_stage", lead_stage, nullable=True),
        sa.Column("to_stage", lead_stage, nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("changed_by_user_id", sa.UUID(), nullable=False),
        sa.Column("remark", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lead_stage_history_lead_id"), "lead_stage_history", ["lead_id"], unique=False)
    op.create_index(
        "ix_lead_stage_history_lead_id_changed_at",
        "lead_stage_history",
        ["lead_id", "changed_at"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_table("lead_stage_history")
    op.drop_table("leads")
    op.execute("DROP SEQUENCE IF EXISTS lead_number_seq")

    for enum in reversed(_ALL_ENUMS):
        enum.drop(bind, checkfirst=True)
