"""Vendor ORM model.

A vendor is a company the business buys from. Master data only — the
relationship history (calls, follow-ups, tasks) lives in Zoho CRM and
is synced by the Integration Layer in Phase 9. This service is the
source of truth for the master record.

Soft-delete via ``is_active`` — hard delete is unsupported because
purchase_orders (Phase 7) and vendor_item_terms (Phase 5 part 3) will
reference vendors via FK with RESTRICT.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Vendor(Base):
    """A company the business buys from."""

    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    vendor_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    contact_person: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional business identifiers, unique among non-null values.
    # Postgres treats NULLs as distinct by default — no partial index needed.
    vendor_code: Mapped[str | None] = mapped_column(
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
