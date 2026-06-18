"""Score-snapshot ORM models — append-only history for every engine.

Snapshots are **inserted, never updated** (same philosophy as
``stock_movements``); trends come for free. Every row carries the
``config_id`` it was computed with (ADR-001 versioning) and a
``defaults_applied`` JSONB array naming the parameters that fell back to a
documented default. "Latest score" for an entity is the newest ``computed_at``
(backed by a ``(entity_id, computed_at DESC)`` composite index).

This module grows over Phase 2B — 2B.1 adds :class:`LeadScore`; later slices
append the customer-health, effort-efficiency, and beat-planning snapshots.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.scoring_config import ScoringConfig


class LeadClassification(StrEnum):
    """Lead-score band."""

    HOT = "HOT"
    MEDIUM = "MEDIUM"
    COLD = "COLD"


class HealthClassification(StrEnum):
    """Customer-health band."""

    HEALTHY = "HEALTHY"
    STABLE = "STABLE"
    AT_RISK = "AT_RISK"
    CRITICAL = "CRITICAL"


class EffortQuadrant(StrEnum):
    """Effort x efficiency quadrant for a sales rep."""

    HIGH_EFFORT_HIGH_EFFICIENCY = "HIGH_EFFORT_HIGH_EFFICIENCY"
    HIGH_EFFORT_LOW_EFFICIENCY = "HIGH_EFFORT_LOW_EFFICIENCY"
    LOW_EFFORT_HIGH_EFFICIENCY = "LOW_EFFORT_HIGH_EFFICIENCY"
    LOW_EFFORT_LOW_EFFICIENCY = "LOW_EFFORT_LOW_EFFICIENCY"


class VisitPriority(StrEnum):
    """Beat-planning visit-priority band for a customer (per rep)."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class LeadScore(Base):
    """An append-only lead-score snapshot (§3.10)."""

    __tablename__ = "lead_scores"
    __table_args__ = (Index("ix_lead_scores_lead_id_computed_at", "lead_id", "computed_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scoring_configs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    urgency_score: Mapped[int] = mapped_column(Integer, nullable=False)
    location_score: Mapped[int] = mapped_column(Integer, nullable=False)
    contribution_margin_score: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    product_margin_score: Mapped[int] = mapped_column(Integer, nullable=False)
    total_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    classification: Mapped[LeadClassification] = mapped_column(
        Enum(
            LeadClassification,
            name="lead_classification",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        index=True,
    )
    defaults_applied: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )

    # Read-only convenience — lets a read surface the config version without a
    # manual join. Eager so reads never trigger lazy I/O (MissingGreenlet).
    config: Mapped[ScoringConfig] = relationship("ScoringConfig", lazy="selectin")


class CustomerHealthScore(Base):
    """An append-only customer-health snapshot (§3.10).

    ``components`` carries all ten sub-scores as ``{"cps": {...}, "crs": {...}}``.
    Health is live-computed on read; snapshots exist for trend history and are
    produced by the recompute endpoint (Decision D-9).
    """

    __tablename__ = "customer_health_scores"
    __table_args__ = (
        Index(
            "ix_customer_health_scores_customer_id_computed_at",
            "customer_id",
            "computed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scoring_configs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    cps: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    crs: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    components: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    weight_profile: Mapped[str] = mapped_column(String(40), nullable=False)
    health_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    classification: Mapped[HealthClassification] = mapped_column(
        Enum(
            HealthClassification,
            name="health_classification",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        index=True,
    )
    defaults_applied: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )


class EffortEfficiencyScore(Base):
    """An append-only effort & efficiency snapshot for one rep + period (§3.10).

    Cohort-relative (normalized within all active reps in the period), so it is
    live-computed on read; snapshots are produced by the recompute endpoint.
    """

    __tablename__ = "effort_efficiency_scores"
    __table_args__ = (
        Index(
            "ix_effort_efficiency_scores_rep_user_id_computed_at",
            "rep_user_id",
            "computed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rep_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scoring_configs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    effort_raw: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    effort_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    efficiency_components: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    efficiency_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    quadrant: Mapped[EffortQuadrant] = mapped_column(
        Enum(
            EffortQuadrant,
            name="effort_quadrant",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        index=True,
    )


class VisitPriorityScore(Base):
    """An append-only beat-planning (visit-priority) snapshot for a customer +
    rep (§3.10). Live-computed on read; snapshots produced by recompute."""

    __tablename__ = "visit_priority_scores"
    __table_args__ = (
        Index(
            "ix_visit_priority_scores_rep_user_id_computed_at",
            "rep_user_id",
            "computed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rep_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scoring_configs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revenue_score: Mapped[int] = mapped_column(Integer, nullable=False)
    visit_gap_score: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_type_score: Mapped[int] = mapped_column(Integer, nullable=False)
    location_density_score: Mapped[int] = mapped_column(Integer, nullable=False)
    vps: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    priority: Mapped[VisitPriority] = mapped_column(
        Enum(VisitPriority, name="visit_priority", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        index=True,
    )
