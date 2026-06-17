"""Customer-target Pydantic schemas.

``customer_id`` is taken from the URL path, never the body. Period order
(``period_end > period_start``) is validated here for create; for a partial
update it's re-validated in the service against the merged values.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "CustomerTargetCreate",
    "CustomerTargetRead",
    "CustomerTargetUpdate",
]


class CustomerTargetCreate(BaseModel):
    """Payload to create a target for a customer."""

    model_config = ConfigDict(extra="forbid")

    period_start: date
    period_end: date
    target_quantity: Decimal = Field(gt=0)
    target_revenue: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check_period_order(self) -> CustomerTargetCreate:
        if self.period_end <= self.period_start:
            raise ValueError("period_end must be after period_start")
        return self


class CustomerTargetUpdate(BaseModel):
    """Partial update for a target. Period order is checked in the service."""

    model_config = ConfigDict(extra="forbid")

    period_start: date | None = None
    period_end: date | None = None
    target_quantity: Decimal | None = Field(default=None, gt=0)
    target_revenue: Decimal | None = Field(default=None, ge=0)


class CustomerTargetRead(BaseModel):
    """Target as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    period_start: date
    period_end: date
    target_quantity: Decimal
    target_revenue: Decimal | None
    created_by_user_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
