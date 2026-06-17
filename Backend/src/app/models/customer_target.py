"""Customer-target ORM model.

A sales target for a customer over a period — the denominator of the
customer-health "volume achievement" component (dispatch ÷ target). Periods
for the same customer may not overlap (enforced in the service; the UNIQUE
constraint is the DB-level safety net for the exact-duplicate case).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CustomerTarget(Base):
    """A volume/revenue target for a customer over a date period."""

    __tablename__ = "customer_targets"
    __table_args__ = (
        CheckConstraint("period_end > period_start", name="ck_customer_targets_period_order"),
        CheckConstraint("target_quantity > 0", name="ck_customer_targets_quantity_positive"),
        CheckConstraint(
            "target_revenue IS NULL OR target_revenue >= 0",
            name="ck_customer_targets_revenue_non_negative",
        ),
        UniqueConstraint(
            "customer_id", "period_start", "period_end",
            name="uq_customer_targets_customer_period",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    target_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    target_revenue: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

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
