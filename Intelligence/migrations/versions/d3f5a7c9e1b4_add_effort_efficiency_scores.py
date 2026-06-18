"""add effort_efficiency_scores snapshot table (Phase 2B.3)

Revision ID: d3f5a7c9e1b4
Revises: c2e4f6a8b1d3
Create Date: 2026-06-18 03:00:00.000000

Phase 2B.3 — the append-only effort & efficiency snapshot (§3.10). Scores are
cohort-relative (normalized within all active reps in the period) and
live-computed on read; snapshots are produced by the recompute endpoint for
trend history. Creates the ``effort_quadrant`` enum and the
``effort_efficiency_scores`` table (raw + normalized effort, the five
efficiency sub-scores as JSONB, the composite efficiency score, the quadrant,
and the period the scores cover).

Hand-written to match the existing migration conventions.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d3f5a7c9e1b4"
down_revision: str | None = "c2e4f6a8b1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

effort_quadrant = postgresql.ENUM(
    "HIGH_EFFORT_HIGH_EFFICIENCY",
    "HIGH_EFFORT_LOW_EFFICIENCY",
    "LOW_EFFORT_HIGH_EFFICIENCY",
    "LOW_EFFORT_LOW_EFFICIENCY",
    name="effort_quadrant",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    effort_quadrant.create(bind, checkfirst=True)

    op.create_table(
        "effort_efficiency_scores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("rep_user_id", sa.UUID(), nullable=False),
        sa.Column("config_id", sa.UUID(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("effort_raw", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("effort_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("efficiency_components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("efficiency_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("quadrant", effort_quadrant, nullable=False),
        sa.ForeignKeyConstraint(["rep_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["config_id"], ["scoring_configs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_effort_efficiency_scores_rep_user_id"),
        "effort_efficiency_scores",
        ["rep_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_effort_efficiency_scores_config_id"),
        "effort_efficiency_scores",
        ["config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_effort_efficiency_scores_quadrant"),
        "effort_efficiency_scores",
        ["quadrant"],
        unique=False,
    )
    op.create_index(
        "ix_effort_efficiency_scores_rep_user_id_computed_at",
        "effort_efficiency_scores",
        ["rep_user_id", "computed_at"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index(
        "ix_effort_efficiency_scores_rep_user_id_computed_at",
        table_name="effort_efficiency_scores",
    )
    op.drop_index(
        op.f("ix_effort_efficiency_scores_quadrant"), table_name="effort_efficiency_scores"
    )
    op.drop_index(
        op.f("ix_effort_efficiency_scores_config_id"), table_name="effort_efficiency_scores"
    )
    op.drop_index(
        op.f("ix_effort_efficiency_scores_rep_user_id"), table_name="effort_efficiency_scores"
    )
    op.drop_table("effort_efficiency_scores")
    effort_quadrant.drop(bind, checkfirst=True)
