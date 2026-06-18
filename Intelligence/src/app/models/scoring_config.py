"""Scoring-config ORM model — versioned, immutable engine parameters.

Every score is computed against the **active** ``scoring_configs`` row for its
engine, and every persisted snapshot records the ``config_id`` it used
(ADR-001: "Log framework version with each score"). Weights live in data, not
code (ADR-001: "Store BU-specific weights in configuration") — changing a
weight is a new version row + an activation swap, never a deploy.

Invariants enforced at the DB (``Backend/CLAUDE.md`` §10.3):

* ``UNIQUE (engine, version)`` — a version means exactly one parameter set.
* a **partial unique index** on ``engine WHERE is_active`` — at most one
  active config per engine, so "the active config" is always unambiguous.

Configs are immutable once created (no ``updated_at``); a change is a new row.
``created_by_user_id`` is nullable because the v1 rows are seeded by the
Alembic migration before any user exists (same chicken/egg exception the
``users`` audit fields make) — NULL means "system / migration-seeded".
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ScoringEngine(StrEnum):
    """The four deterministic scoring engines."""

    LEAD_SCORING = "LEAD_SCORING"
    EFFORT_EFFICIENCY = "EFFORT_EFFICIENCY"
    CUSTOMER_HEALTH = "CUSTOMER_HEALTH"
    BEAT_PLANNING = "BEAT_PLANNING"


class ScoringConfig(Base):
    """A versioned parameter set for one scoring engine."""

    __tablename__ = "scoring_configs"
    __table_args__ = (
        UniqueConstraint("engine", "version", name="uq_scoring_configs_engine_version"),
        # At most one active config per engine. A partial unique index is the
        # DB-level guarantee that "the active config" is never ambiguous.
        Index(
            "uq_scoring_configs_one_active_per_engine",
            "engine",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engine: Mapped[ScoringEngine] = mapped_column(
        Enum(ScoringEngine, name="scoring_engine", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # NULL for migration-seeded (system) configs; set to the actor for
    # configs created via the admin endpoint.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
