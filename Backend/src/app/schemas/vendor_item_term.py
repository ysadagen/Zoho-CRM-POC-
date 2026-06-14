"""Pydantic schemas for vendor-item pricing terms.

``vendor_id`` is **not** in the request bodies — it's always taken
from the URL path (``/vendors/{vendor_id}/terms/...``). ``item_id`` IS
in the create body because it's the other half of the natural key.

``item_id`` is **not updatable** — changing the item on an existing
term is conceptually creating a new term, not editing this one.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "VendorItemTermCreate",
    "VendorItemTermList",
    "VendorItemTermRead",
    "VendorItemTermUpdate",
]


class VendorItemTermCreate(BaseModel):
    """Payload to create a new pricing term for a vendor + item."""

    model_config = ConfigDict(extra="forbid")

    item_id: uuid.UUID
    rate: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    discount_percent: Decimal = Field(
        default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2
    )
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def _check_date_range(self) -> Self:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be >= effective_from")
        return self


class VendorItemTermUpdate(BaseModel):
    """Partial update for an existing pricing term.

    ``item_id`` is deliberately omitted — changing the item is creating
    a different term, not editing this one. ``vendor_id`` is fixed by
    the URL path.
    """

    model_config = ConfigDict(extra="forbid")

    rate: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    discount_percent: Decimal | None = Field(
        default=None, ge=0, le=100, max_digits=5, decimal_places=2
    )
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None


class VendorItemTermRead(BaseModel):
    """Pricing term as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vendor_id: uuid.UUID
    item_id: uuid.UUID
    rate: Decimal
    discount_percent: Decimal
    effective_from: date
    effective_to: date | None
    is_active: bool
    created_by_user_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class VendorItemTermList(BaseModel):
    """Paginated envelope (CLAUDE.md §6)."""

    items: list[VendorItemTermRead]
    total: int
    limit: int
    offset: int
