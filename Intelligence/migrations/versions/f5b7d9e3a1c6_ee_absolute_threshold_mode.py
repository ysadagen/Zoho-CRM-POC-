"""seed EFFORT_EFFICIENCY v2 config — absolute-threshold scoring mode

Revision ID: f5b7d9e3a1c6
Revises: e4a6c8b2d5f1
Create Date: 2026-06-29 00:00:00.000000

Adds a second EFFORT_EFFICIENCY config version that uses absolute thresholds
instead of cohort-relative normalization.  Recommended for small teams (<= 4
reps) where cohort scoring is misleading: one rep always scores high and the
other always scores low regardless of absolute performance.

Changes:
  - Inserts scoring_configs version 2 for EFFORT_EFFICIENCY with
    scoring_mode="absolute" and sensible default absolute_thresholds.
  - Deactivates v1, activates v2.

downgrade() reverses: deactivates v2, reactivates v1.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.services.scoring.default_configs import EFFORT_EFFICIENCY_V2

revision: str = "f5b7d9e3a1c6"
down_revision: str | None = "e4a6c8b2d5f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENGINE = "EFFORT_EFFICIENCY"


def upgrade() -> None:
    bind = op.get_bind()

    # Deactivate v1.
    # CAST(:param AS type) is used throughout — :param::type confuses the
    # SQLAlchemy asyncpg dialect parser, which fails to substitute :param → $n
    # when :: immediately follows the parameter name.
    bind.execute(
        sa.text(
            "UPDATE scoring_configs SET is_active = false"
            " WHERE engine = CAST(:engine AS scoring_engine) AND version = 1"
        ),
        {"engine": _ENGINE},
    )

    # Insert v2 as active.
    bind.execute(
        sa.text(
            "INSERT INTO scoring_configs"
            " (id, engine, version, params, is_active, description)"
            " VALUES (CAST(:id AS uuid), CAST(:engine AS scoring_engine),"
            " :version, CAST(:params AS jsonb), :is_active, :description)"
        ),
        {
            "id": str(uuid.uuid4()),
            "engine": _ENGINE,
            "version": 2,
            "params": json.dumps(EFFORT_EFFICIENCY_V2),
            "is_active": True,
            "description": (
                "Absolute-threshold scoring mode — recommended for teams <= 4 reps. "
                "Tune effort_target / revenue_per_effort_target / close_target_days "
                "via POST /intelligence/configs to match your business targets."
            ),
        },
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Remove v2.
    bind.execute(
        sa.text(
            "DELETE FROM scoring_configs"
            " WHERE engine = CAST(:engine AS scoring_engine) AND version = 2"
        ),
        {"engine": _ENGINE},
    )

    # Reactivate v1.
    bind.execute(
        sa.text(
            "UPDATE scoring_configs SET is_active = true"
            " WHERE engine = CAST(:engine AS scoring_engine) AND version = 1"
        ),
        {"engine": _ENGINE},
    )
