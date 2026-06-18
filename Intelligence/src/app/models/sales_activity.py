"""Sales-activity ORM model — the append-only activity ledger.

One table covers every activity input the intelligence engines need: the
effort score (visits/meetings/calls/follow-ups weighted), engagement
(visit frequency), the visit-gap and communication-gap signals, and the
service-risk signal (complaints).

Activities are **facts**: there are no PATCH/DELETE endpoints (a correction
is a new row, same rule as stock adjustments). Every row has a *subject* —
a customer, a lead, or both — enforced by a CHECK so a contextless activity
can never be recorded.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ActivityType(StrEnum):
    """Kind of sales activity. COMPLAINT feeds churn-risk, not effort."""

    VISIT = "VISIT"
    MEETING = "MEETING"
    FOLLOW_UP = "FOLLOW_UP"
    CALL = "CALL"
    COMPLAINT = "COMPLAINT"


class SalesActivity(Base):
    """An append-only record of a sales interaction."""

    __tablename__ = "sales_activities"
    __table_args__ = (
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name="ck_sales_activities_duration_positive",
        ),
        # Every activity must be about a customer, a lead, or both — a
        # contextless activity can't feed any engine. The DB is the contract.
        CheckConstraint(
            "customer_id IS NOT NULL OR lead_id IS NOT NULL",
            name="ck_sales_activities_has_subject",
        ),
        # Composite indexes backing the per-subject / per-rep time-ordered
        # scans the engines run (visit gap, engagement, effort).
        Index("ix_sales_activities_customer_id_occurred_at", "customer_id", "occurred_at"),
        Index("ix_sales_activities_rep_user_id_occurred_at", "rep_user_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[ActivityType] = mapped_column(
        Enum(ActivityType, name="activity_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        index=True,
    )
    # Who performed the activity (the rep) — distinct from created_by (the
    # actor who logged it; a manager may log on a rep's behalf).
    rep_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

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
