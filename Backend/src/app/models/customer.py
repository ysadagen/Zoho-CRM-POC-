"""Customer ORM model.

A customer is a company the business sells to. Light master-data — the
heavy relationship work (calls, tasks, history) lives in Zoho CRM and is
synced by the Integration Layer in Phase 9. This service is the source
of truth for the master record only.

Soft-delete via ``is_active`` — hard delete is unsupported because
sales_orders (Phase 8) will reference customers via FK with RESTRICT.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CustomerType(StrEnum):
    """Channel tier of a customer.

    Drives the beat-planning customer-type weight (DEALER ranks above
    SUB_DEALER above RETAILER). Defaults to ``RETAILER`` — the most
    conservative (lowest-priority) tier — for existing rows and for
    create calls that omit it.
    """

    DEALER = "DEALER"
    SUB_DEALER = "SUB_DEALER"
    RETAILER = "RETAILER"


class CompetitiveRiskLevel(StrEnum):
    """Manual flag of competitive pressure on a customer.

    Real signals (price undercutting, volume migration) require data we
    don't capture in the POC; this rep-maintained enum is the honest
    stand-in that feeds the customer-health churn-risk engine. Defaults
    to ``NONE``.
    """

    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Customer(Base):
    """A company the business sells to."""

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    company_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    contact_person: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_privileged: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    # Optional business identifiers. Unique among non-null values —
    # Postgres treats NULLs as distinct by default, so the unique
    # constraint allows many rows with NULL but rejects duplicates of
    # any real value. No partial index needed.
    customer_code: Mapped[str | None] = mapped_column(
        String(60),
        unique=True,
        index=True,
        nullable=True,
    )
    gstin: Mapped[str | None] = mapped_column(
        String(15),
        unique=True,
        index=True,
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Intelligence-layer attributes (Phase 2A) -------------------------
    # Channel tier — feeds the beat-planning customer-type weight.
    customer_type: Mapped[CustomerType] = mapped_column(
        Enum(CustomerType, name="customer_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=CustomerType.RETAILER,
        server_default=CustomerType.RETAILER.value,
    )
    # Structured location — feeds lead-scoring serviceability and the
    # beat-planning location-density (district clustering). The free-text
    # ``address`` above stays for display; these are for computation.
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Manual competitive-pressure flag — feeds customer-health churn risk.
    competitive_risk_level: Mapped[CompetitiveRiskLevel] = mapped_column(
        Enum(
            CompetitiveRiskLevel,
            name="competitive_risk_level",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=CompetitiveRiskLevel.NONE,
        server_default=CompetitiveRiskLevel.NONE.value,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # Audit attribution per CLAUDE.md §10.2.
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
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
