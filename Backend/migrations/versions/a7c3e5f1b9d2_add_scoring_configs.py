"""add scoring_configs + seed v1 active configs (Phase 2B.0)

Revision ID: a7c3e5f1b9d2
Revises: f4b6c8e0a3d5
Create Date: 2026-06-18 00:00:00.000000

Phase 2B.0 — the configuration foundation every scoring engine reads. Creates
the ``scoring_engine`` enum and the ``scoring_configs`` table (UNIQUE
(engine, version) + a partial unique index enforcing at most one active config
per engine), then **seeds version 1 active** for all four engines with the
default parameters defined in ``INTELLIGENCE_SPECIFICATION.md`` §17.

The seed imports the frozen v1 constants from
``app.services.scoring.default_configs`` (Alembic's ``env.py`` already puts the
app on the path) so the seeded rows and the runtime config validator share one
source of truth. v1 is immutable by design — a parameter change is a new
version row, never an edit — so importing the constant here is safe.

Hand-written to match the existing migration conventions.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.models.scoring_config import ScoringEngine
from app.services.scoring.default_configs import DEFAULT_PARAMS_V1

# revision identifiers, used by Alembic.
revision: str = "a7c3e5f1b9d2"
down_revision: str | None = "f4b6c8e0a3d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

scoring_engine = postgresql.ENUM(
    "LEAD_SCORING",
    "EFFORT_EFFICIENCY",
    "CUSTOMER_HEALTH",
    "BEAT_PLANNING",
    name="scoring_engine",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    scoring_engine.create(bind, checkfirst=True)

    op.create_table(
        "scoring_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("engine", scoring_engine, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("engine", "version", name="uq_scoring_configs_engine_version"),
    )
    op.create_index(op.f("ix_scoring_configs_engine"), "scoring_configs", ["engine"], unique=False)
    op.create_index(
        op.f("ix_scoring_configs_created_by_user_id"),
        "scoring_configs",
        ["created_by_user_id"],
        unique=False,
    )
    # At most one active config per engine.
    op.create_index(
        "uq_scoring_configs_one_active_per_engine",
        "scoring_configs",
        ["engine"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    # --- Seed v1 active for every engine (§17 defaults) -------------------
    configs_table = sa.table(
        "scoring_configs",
        sa.column("id", sa.UUID()),
        sa.column("engine", scoring_engine),
        sa.column("version", sa.Integer()),
        sa.column("params", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("is_active", sa.Boolean()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        configs_table,
        [
            {
                "id": uuid.uuid4(),
                "engine": engine.value,
                "version": 1,
                "params": DEFAULT_PARAMS_V1[engine],
                "is_active": True,
                "description": "Seeded v1 defaults (INTELLIGENCE_SPECIFICATION.md §17)",
            }
            for engine in ScoringEngine
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("uq_scoring_configs_one_active_per_engine", table_name="scoring_configs")
    op.drop_index(op.f("ix_scoring_configs_created_by_user_id"), table_name="scoring_configs")
    op.drop_index(op.f("ix_scoring_configs_engine"), table_name="scoring_configs")
    op.drop_table("scoring_configs")
    scoring_engine.drop(bind, checkfirst=True)
