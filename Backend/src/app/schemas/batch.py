"""Batch (lot) Pydantic schemas.

Phase 1B records lots for **existing** item stock — an "opening balance"
association that does NOT change ``items.stock_quantity`` (new stock enters
via PO receive in 1C). The service enforces that a new lot's quantity does
not exceed the item's *unbatched* remainder.

``BatchRead`` exposes a computed ``is_expired`` so the UI doesn't repeat the
date math.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.models.batch import BatchStatus

__all__ = ["BatchCreate", "BatchList", "BatchRead"]


class BatchCreate(BaseModel):
    """Payload to record a lot against existing item stock.

    ``quantity`` is the on-hand amount this lot accounts for; the service
    sets ``initial_quantity`` equal to it. ``batch_status`` defaults to
    ``QUARANTINE`` but may be set (e.g. ``RELEASED`` for already-usable
    legacy stock). Provenance (``vendor_id`` / ``received_via_po_id``) is
    populated by the PO-receive flow (1C), not here.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    item_id: uuid.UUID
    batch_number: str = Field(min_length=1, max_length=64)
    expiry_date: date
    manufacturing_date: date | None = None
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=4)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    storage_location: str | None = Field(default=None, max_length=120)
    batch_status: BatchStatus = BatchStatus.QUARANTINE
    batch_received_date: date | None = None

    @model_validator(mode="after")
    def _expiry_on_or_after_manufacture(self) -> Self:
        if self.manufacturing_date is not None and self.expiry_date < self.manufacturing_date:
            raise ValueError("expiry_date must be on or after manufacturing_date")
        return self


class BatchRead(BaseModel):
    """A lot as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    batch_number: str
    batch_status: BatchStatus
    batch_received_date: date | None
    manufacturing_date: date | None
    expiry_date: date
    quantity: Decimal
    initial_quantity: Decimal
    unit_cost: Decimal | None
    storage_location: str | None
    vendor_id: uuid.UUID | None
    received_via_po_id: uuid.UUID | None
    created_by_user_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_expired(self) -> bool:
        """True once the lot is past its expiry date. Derived, never stored."""
        return self.expiry_date < date.today()


class BatchList(BaseModel):
    """Paginated envelope for ``GET /batches`` (CLAUDE.md §6)."""

    items: list[BatchRead]
    total: int
    limit: int
    offset: int
