"""OAuth token state for the Zoho connection.

A single logical row holds the live access token, its expiry, and the
long-lived refresh token. Zoho's refresh-token grant does not return a new
refresh token, so the same refresh token persists across access-token
refreshes. The ``provider`` column is unique, which is what guarantees there
is exactly one token row per upstream (only ``zoho`` today).

Tokens are stored as plain text. Field-level encryption at rest is a sanctioned
follow-up: it needs a dedicated encryption-key setting that is not yet specced,
so introducing one silently would violate "``.env.example`` is the source of
truth". The columns are ``Text`` so adding encryption later is non-breaking.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin

ZOHO_PROVIDER = "zoho"


class ZohoToken(Base, TimestampMixin):
    """Persisted OAuth state for a single upstream provider."""

    __tablename__ = "zoho_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, default=ZOHO_PROVIDER
    )
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_type: Mapped[str] = mapped_column(String(32), nullable=False, default="Bearer")
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Absolute UTC instant the access token stops being valid.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
