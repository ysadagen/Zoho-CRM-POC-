"""add customer_health_scores snapshot table (Phase 2B.2)

Revision ID: c2e4f6a8b1d3
Revises: b1d3f5a7c9e2
Create Date: 2026-06-18 02:00:00.000000

Phase 2B.2 — the append-only customer-health snapshot (§3.10). Health is
live-computed on read; snapshots exist for trend history and are produced by
the recompute endpoint. Creates the ``health_classification`` enum and the
``customer_health_scores`` table (CPS, CRS, ten sub-scores as JSONB, the
weight profile used, the normalized health score, and the config_id).

Hand-written to match the existing migration conventions.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c2e4f6a8b1d3"
down_revision: str | None = "b1d3f5a7c9e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

health_classification = postgresql.ENUM(
    "HEALTHY",
    "STABLE",
    "AT_RISK",
    "CRITICAL",
    name="health_classification",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    health_classification.create(bind, checkfirst=True)

    op.create_table(
        "customer_health_scores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("config_id", sa.UUID(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cps", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("crs", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("weight_profile", sa.String(length=40), nullable=False),
        sa.Column("health_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("classification", health_classification, nullable=False),
        sa.Column(
            "defaults_applied",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["config_id"], ["scoring_configs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_customer_health_scores_customer_id"),
        "customer_health_scores",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_customer_health_scores_config_id"),
        "customer_health_scores",
        ["config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_customer_health_scores_classification"),
        "customer_health_scores",
        ["classification"],
        unique=False,
    )
    op.create_index(
        "ix_customer_health_scores_customer_id_computed_at",
        "customer_health_scores",
        ["customer_id", "computed_at"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index(
        "ix_customer_health_scores_customer_id_computed_at", table_name="customer_health_scores"
    )
    op.drop_index(
        op.f("ix_customer_health_scores_classification"), table_name="customer_health_scores"
    )
    op.drop_index(op.f("ix_customer_health_scores_config_id"), table_name="customer_health_scores")
    op.drop_index(
        op.f("ix_customer_health_scores_customer_id"), table_name="customer_health_scores"
    )
    op.drop_table("customer_health_scores")
    health_classification.drop(bind, checkfirst=True)
