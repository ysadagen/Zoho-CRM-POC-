"""Sales-activity Pydantic schemas.

``occurred_at`` cannot be in the future (an activity is something that
happened). The subject rule (customer and/or lead required) is enforced in
the service so it can return the specific ``SUBJECT_REQUIRED`` code, with
the DB CHECK as the final safety net.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.sales_activity import ActivityType

__all__ = [
    "ActivityCreate",
    "ActivityList",
    "ActivityRead",
    "ActivityType",
]


class ActivityCreate(BaseModel):
    """Payload to record a sales activity (append-only)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: ActivityType
    occurred_at: datetime
    # Defaults to the authenticated user in the service when omitted.
    rep_user_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    remarks: str | None = Field(default=None, max_length=2000)

    @field_validator("occurred_at")
    @classmethod
    def _not_in_future(cls, value: datetime) -> datetime:
        now = datetime.now(UTC)
        normalised = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        if normalised > now:
            raise ValueError("occurred_at cannot be in the future")
        return value


class ActivityRead(BaseModel):
    """Activity as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: ActivityType
    rep_user_id: uuid.UUID
    customer_id: uuid.UUID | None
    lead_id: uuid.UUID | None
    occurred_at: datetime
    duration_minutes: int | None
    remarks: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime


class ActivityList(BaseModel):
    """Paginated envelope for ``GET /activities`` (CLAUDE.md §6)."""

    items: list[ActivityRead]
    total: int
    limit: int
    offset: int
