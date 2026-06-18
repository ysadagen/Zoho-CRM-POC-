"""add visit_priority_scores snapshot table (Phase 2B.4)

Revision ID: e4a6c8b2d5f1
Revises: d3f5a7c9e1b4
Create Date: 2026-06-18 04:00:00.000000

Phase 2B.4 — the append-only beat-planning (visit-priority) snapshot (§3.10).
Scored per (customer, rep) and live-computed on read; snapshots are produced
by the recompute endpoint for trend history. Creates the ``visit_priority``
enum and the ``visit_priority_scores`` table (the four VPS sub-scores, the
composite VPS, and the priority band).

Hand-written to match the existing migration conventions.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e4a6c8b2d5f1"
down_revision: str | None = "d3f5a7c9e1b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

visit_priority = postgresql.ENUM(
    "CRITICAL", "HIGH", "MEDIUM", "LOW", name="visit_priority", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    visit_priority.create(bind, checkfirst=True)

    op.create_table(
        "visit_priority_scores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("rep_user_id", sa.UUID(), nullable=False),
        sa.Column("config_id", sa.UUID(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revenue_score", sa.Integer(), nullable=False),
        sa.Column("visit_gap_score", sa.Integer(), nullable=False),
        sa.Column("customer_type_score", sa.Integer(), nullable=False),
        sa.Column("location_density_score", sa.Integer(), nullable=False),
        sa.Column("vps", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("priority", visit_priority, nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rep_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["config_id"], ["scoring_configs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_visit_priority_scores_customer_id"),
        "visit_priority_scores",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_visit_priority_scores_rep_user_id"),
        "visit_priority_scores",
        ["rep_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_visit_priority_scores_config_id"),
        "visit_priority_scores",
        ["config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_visit_priority_scores_priority"),
        "visit_priority_scores",
        ["priority"],
        unique=False,
    )
    op.create_index(
        "ix_visit_priority_scores_rep_user_id_computed_at",
        "visit_priority_scores",
        ["rep_user_id", "computed_at"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index(
        "ix_visit_priority_scores_rep_user_id_computed_at", table_name="visit_priority_scores"
    )
    op.drop_index(op.f("ix_visit_priority_scores_priority"), table_name="visit_priority_scores")
    op.drop_index(op.f("ix_visit_priority_scores_config_id"), table_name="visit_priority_scores")
    op.drop_index(op.f("ix_visit_priority_scores_rep_user_id"), table_name="visit_priority_scores")
    op.drop_index(op.f("ix_visit_priority_scores_customer_id"), table_name="visit_priority_scores")
    op.drop_table("visit_priority_scores")
    visit_priority.drop(bind, checkfirst=True)
