"""Audit ledger for every outbound sync (push) and inbound ingest attempt.

One row per attempt, success or failure, carrying the structured fields
CLAUDE.md §8 requires plus the payload/response for replay and debugging.
The ``status`` lifecycle (CLAUDE.md §7/§19) covers the in-process retry model
(no queue): terminal failures rest in ``FAILED_PERMANENT`` and are re-driven by
an admin endpoint; an unmatched ingest owner rests in ``PARKED``.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import Enum, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.models.crm_mapping import MappingEntityType


class SyncDirection(StrEnum):
    """Which way the data flowed for this attempt."""

    PUSH = "PUSH"  # app → Zoho (Track B)
    INGEST = "INGEST"  # Zoho → app (Track A)


class SyncStatus(StrEnum):
    """Lifecycle state of a sync/ingest attempt."""

    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"  # failed this attempt, may be retried
    FAILED_PERMANENT = "FAILED_PERMANENT"  # dead-lettered; admin re-drive only
    RATE_LIMITED = "RATE_LIMITED"  # Zoho 429; surfaced as 503 to the caller
    PARKED = "PARKED"  # ingest could not attribute (e.g. unmatched owner)


class SyncLog(Base, TimestampMixin):
    """An append-style record of one sync or ingest attempt."""

    __tablename__ = "sync_logs"
    __table_args__ = (
        # Backs the most-recent-attempts-for-an-entity scan (CLAUDE.md §10).
        # A composite btree on (entity_type, local_id, created_at) serves the
        # ``WHERE entity_type=? AND local_id=? ORDER BY created_at DESC`` pattern.
        Index(
            "ix_sync_logs_entity_type_local_id_created_at",
            "entity_type",
            "local_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    direction: Mapped[SyncDirection] = mapped_column(
        Enum(SyncDirection, name="sync_direction", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    entity_type: Mapped[MappingEntityType | None] = mapped_column(
        Enum(
            MappingEntityType,
            name="mapping_entity_type",
            values_callable=lambda e: [m.value for m in e],
            # The type is created by the crm_mappings migration; don't re-emit it.
            create_type=False,
        ),
        nullable=True,
    )
    local_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zoho_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    operation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, name="sync_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=SyncStatus.PENDING,
        index=True,
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    zoho_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
