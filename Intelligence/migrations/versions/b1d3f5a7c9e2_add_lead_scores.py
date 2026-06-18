"""add lead_scores snapshot table (Phase 2B.1)

Revision ID: b1d3f5a7c9e2
Revises: a7c3e5f1b9d2
Create Date: 2026-06-18 01:00:00.000000

Phase 2B.1 — the append-only lead-score snapshot (§3.10). Creates the
``lead_classification`` enum (HOT/MEDIUM/COLD) and the ``lead_scores`` table:
the five component scores, the total, the band, the ``defaults_applied`` JSONB
array, and the ``config_id`` the score was computed with. A composite
``(lead_id, computed_at)`` index backs the "latest score per lead" reads.

Hand-written to match the existing migration conventions.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b1d3f5a7c9e2"
down_revision: str | None = "a7c3e5f1b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

lead_classification = postgresql.ENUM(
    "HOT", "MEDIUM", "COLD", name="lead_classification", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    lead_classification.create(bind, checkfirst=True)

    op.create_table(
        "lead_scores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("config_id", sa.UUID(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("urgency_score", sa.Integer(), nullable=False),
        sa.Column("location_score", sa.Integer(), nullable=False),
        sa.Column("contribution_margin_score", sa.Integer(), nullable=False),
        sa.Column("quantity_score", sa.Integer(), nullable=False),
        sa.Column("product_margin_score", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("classification", lead_classification, nullable=False),
        sa.Column(
            "defaults_applied",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["config_id"], ["scoring_configs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lead_scores_lead_id"), "lead_scores", ["lead_id"], unique=False)
    op.create_index(op.f("ix_lead_scores_config_id"), "lead_scores", ["config_id"], unique=False)
    op.create_index(
        op.f("ix_lead_scores_classification"), "lead_scores", ["classification"], unique=False
    )
    op.create_index(
        "ix_lead_scores_lead_id_computed_at", "lead_scores", ["lead_id", "computed_at"], unique=False
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_lead_scores_lead_id_computed_at", table_name="lead_scores")
    op.drop_index(op.f("ix_lead_scores_classification"), table_name="lead_scores")
    op.drop_index(op.f("ix_lead_scores_config_id"), table_name="lead_scores")
    op.drop_index(op.f("ix_lead_scores_lead_id"), table_name="lead_scores")
    op.drop_table("lead_scores")
    lead_classification.drop(bind, checkfirst=True)
