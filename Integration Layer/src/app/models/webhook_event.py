"""Inbound Zoho webhook events (signature-verified, stored, then processed).

Zoho's event id is the natural dedupe key (unique), so a duplicate delivery is
a no-op (CLAUDE.md §13). The table is created in A0 for schema completeness;
the verify-persist-dispatch flow lands with the webhook endpoint in a later
phase.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class WebhookStatus(StrEnum):
    """Processing state of a received webhook event."""

    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class WebhookEvent(Base, TimestampMixin):
    """A persisted inbound webhook delivery from Zoho."""

    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Zoho's event id — the dedupe key. Duplicate delivery → 200 no-op.
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    module: Mapped[str | None] = mapped_column(String(100), nullable=True)
    operation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[WebhookStatus] = mapped_column(
        Enum(WebhookStatus, name="webhook_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=WebhookStatus.PENDING,
        index=True,
    )
