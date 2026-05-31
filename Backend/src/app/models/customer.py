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

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


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
