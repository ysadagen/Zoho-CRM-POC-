"""Pydantic schemas for purchase orders.

Three I/O surfaces only — Phase 7 doesn't expose an edit path:

- :class:`PurchaseOrderCreate` (with nested :class:`PurchaseOrderLineCreate`)
- :class:`PurchaseOrderRead` (with nested :class:`PurchaseOrderLineRead`)
- :class:`PurchaseOrderList` (paginated envelope per CLAUDE.md §6)

Note the absence of ``PurchaseOrderUpdate`` and any line-update schema
— that is deliberate. A DRAFT PO is replaced (delete+recreate) if the
operator made a mistake; a RECEIVED PO is terminal. Adding patch
shapes later is additive; not having them today keeps the surface
honest about what's supported.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.purchase_order import PurchaseOrderStatus

__all__ = [
    "PurchaseOrderCreate",
    "PurchaseOrderLineCreate",
    "PurchaseOrderLineRead",
    "PurchaseOrderList",
    "PurchaseOrderRead",
    "PurchaseOrderReceive",
    "PurchaseOrderReceiveLine",
    "PurchaseOrderStatus",
]


class PurchaseOrderLineCreate(BaseModel):
    """One line on a PO create payload.

    ``unit_price`` is optional. If omitted, the service looks up an
    active ``vendor_item_term`` for (vendor, item) and uses
    ``rate * (1 - discount_percent / 100)`` quantized to 2 dp,
    HALF_UP. If no term is found and no explicit price is given,
    creation fails 422 ``PRICE_UNAVAILABLE``.
    """

    model_config = ConfigDict(extra="forbid")

    item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class PurchaseOrderCreate(BaseModel):
    """Payload to create a new PO in DRAFT status."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    vendor_id: uuid.UUID
    expected_delivery_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    items: list[PurchaseOrderLineCreate] = Field(min_length=1)


class PurchaseOrderReceiveLine(BaseModel):
    """Batch (lot) details for one PO line, supplied at receive time.

    The operator supplies the manufacturer's ``batch_number`` and the
    lot's ``expiry_date`` (required — pharma stock must enter with an
    expiry). One entry per PO line, matched by ``item_id``. The received
    quantity and unit cost come from the PO line itself, not from here.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    item_id: uuid.UUID
    batch_number: str = Field(min_length=1, max_length=64)
    expiry_date: date
    manufacturing_date: date | None = None
    storage_location: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _expiry_on_or_after_manufacture(self) -> Self:
        if self.manufacturing_date is not None and self.expiry_date < self.manufacturing_date:
            raise ValueError("expiry_date must be on or after manufacturing_date")
        return self


class PurchaseOrderReceive(BaseModel):
    """Payload for ``POST /purchase-orders/{id}/receive``.

    One batch entry per PO line — the service requires the entries to
    cover exactly the PO's lines (no missing, no extra).
    """

    model_config = ConfigDict(extra="forbid")

    lines: list[PurchaseOrderReceiveLine] = Field(min_length=1)


class PurchaseOrderLineRead(BaseModel):
    """A PO line as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    created_at: datetime


class PurchaseOrderRead(BaseModel):
    """A PO header + lines as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    po_number: str
    vendor_id: uuid.UUID
    order_date: date
    expected_delivery_date: date | None
    received_date: date | None
    status: PurchaseOrderStatus
    subtotal: Decimal
    total: Decimal
    notes: str | None
    items: list[PurchaseOrderLineRead]
    created_by_user_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PurchaseOrderList(BaseModel):
    """Paginated envelope for ``GET /purchase-orders`` (CLAUDE.md §6)."""

    items: list[PurchaseOrderRead]
    total: int
    limit: int
    offset: int
