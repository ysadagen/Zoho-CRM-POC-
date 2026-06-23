"""Idempotency records for inbound push requests (Track B).

Each inbound ``/sync`` request carries an ``Idempotency-Key`` header. We store
the key with a hash of the canonicalised request body and the response we
returned, so a replay within the TTL returns the cached response without
re-calling Zoho, and the same key with a *different* body is a 409 conflict
(CLAUDE.md §12).

The table is created in A0 for schema completeness; the contract is exercised
when the push endpoints land. Ingest (Track A) does not use this table — it
dedupes on the Zoho record id via ``crm_mappings`` instead.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class IdempotencyKey(Base, TimestampMixin):
    """A remembered request/response pair keyed by the Idempotency-Key header."""

    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # Hash of the canonicalised request body — same key + different body → 409.
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
