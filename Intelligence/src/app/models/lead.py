"""Lead ORM models — the central entity of the intelligence layer.

A lead is a sales opportunity. It may exist with or without a linked
customer (a brand-new prospect vs an expansion of an existing account).
Its lifecycle moves through a small state machine (NEW → QUALIFICATION →
NEGOTIATION → WON | LOST); every transition is recorded append-only in
``lead_stage_history`` — the same philosophy as the ``stock_movements``
ledger, so stage-change rate, won dates, and time-to-close come for free.

Stage is mutated **only** via the transition flow (service +
``/leads/{id}/transition`` endpoint), never by a plain PATCH — so the
state machine and the history trail can never be bypassed.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LeadStage(StrEnum):
    """Lifecycle stage of a lead (the sales funnel)."""

    NEW = "NEW"
    QUALIFICATION = "QUALIFICATION"
    NEGOTIATION = "NEGOTIATION"
    WON = "WON"
    LOST = "LOST"


class LeadSource(StrEnum):
    """Where the lead came from."""

    PHONE_IN = "PHONE_IN"
    WALK_IN = "WALK_IN"
    REFERENCE = "REFERENCE"
    CAMPAIGN = "CAMPAIGN"
    FIELD_VISIT = "FIELD_VISIT"
    OTHER = "OTHER"


class DealerPotential(StrEnum):
    """A rep's judgement of the account's potential — feeds lead scoring."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


#: Legal stage transitions. Terminal stages map to an empty set. The lead
#: service validates every transition against this; anything absent is a
#: 409 ``INVALID_STAGE_TRANSITION``. Kept beside the enum so the rule lives
#: with the type it governs and is importable by tests.
LEAD_STAGE_TRANSITIONS: dict[LeadStage, frozenset[LeadStage]] = {
    LeadStage.NEW: frozenset({LeadStage.QUALIFICATION, LeadStage.LOST}),
    LeadStage.QUALIFICATION: frozenset({LeadStage.NEGOTIATION, LeadStage.LOST}),
    LeadStage.NEGOTIATION: frozenset({LeadStage.WON, LeadStage.LOST}),
    LeadStage.WON: frozenset(),
    LeadStage.LOST: frozenset(),
}


class Lead(Base):
    """A sales opportunity scored by the lead-scoring engine."""

    __tablename__ = "leads"
    __table_args__ = (
        # Money / quantity invariants — NULL means "not provided" and the
        # scoring engine falls back to a default; a real value must be sane.
        CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_leads_quantity_positive"),
        CheckConstraint(
            "estimated_budget IS NULL OR estimated_budget >= 0",
            name="ck_leads_estimated_budget_non_negative",
        ),
        CheckConstraint("won_value IS NULL OR won_value > 0", name="ck_leads_won_value_positive"),
        # Terminal-state invariants — the DB is the contract (CLAUDE.md §10.3).
        # A WON lead must carry its win timestamp + value, and only a WON lead
        # may; symmetrically for LOST and its reason.
        CheckConstraint(
            "(stage = 'WON') = (won_at IS NOT NULL AND won_value IS NOT NULL)",
            name="ck_leads_won_consistency",
        ),
        CheckConstraint(
            "(stage = 'LOST') = (lost_at IS NOT NULL AND lost_reason IS NOT NULL)",
            name="ck_leads_lost_consistency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_number: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)

    # A lead may be for an existing customer (expansion) or a fresh prospect.
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    contact_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)

    # Product of interest + commercial signals (all feed lead scoring).
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    estimated_budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    dealer_potential: Mapped[DealerPotential | None] = mapped_column(
        Enum(
            DealerPotential,
            name="dealer_potential",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    required_by_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    source: Mapped[LeadSource] = mapped_column(
        Enum(LeadSource, name="lead_source", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    stage: Mapped[LeadStage] = mapped_column(
        Enum(LeadStage, name="lead_stage", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=LeadStage.NEW,
        server_default=LeadStage.NEW.value,
        index=True,
    )
    assigned_to_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Structured location — drives the lead-scoring serviceability parameter.
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Terminal-state fields — set on transition to WON / LOST (see CHECKs).
    won_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    won_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lost_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lost_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class LeadStageHistory(Base):
    """Append-only record of every lead stage transition.

    The creation row has ``from_stage = NULL`` and ``to_stage = NEW``. Rows
    are never updated or deleted. ON DELETE CASCADE is a DB-level safety net
    only — leads are soft-deleted, never hard-deleted.
    """

    __tablename__ = "lead_stage_history"
    __table_args__ = (Index("ix_lead_stage_history_lead_id_changed_at", "lead_id", "changed_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_stage: Mapped[LeadStage | None] = mapped_column(
        Enum(LeadStage, name="lead_stage", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    to_stage: Mapped[LeadStage] = mapped_column(
        Enum(LeadStage, name="lead_stage", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
