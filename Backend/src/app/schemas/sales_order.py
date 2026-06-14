"""Pydantic schemas for sales orders.

Three I/O surfaces — Phase 8 exposes no edit path, mirroring Phase 7:

- :class:`SalesOrderCreate` (with nested :class:`SalesOrderLineCreate`)
- :class:`SalesOrderRead` (with nested :class:`SalesOrderLineRead`)
- :class:`SalesOrderList` (paginated envelope per CLAUDE.md §6)

No update / patch / delete shapes. A wrong DRAFT sits and a SHIPPED SO
is terminal — accurate to the API surface.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.sales_order import SalesOrderStatus

__all__ = [
    "SalesOrderCreate",
    "SalesOrderLineCreate",
    "SalesOrderLineRead",
    "SalesOrderList",
    "SalesOrderRead",
    "SalesOrderStatus",
]


class SalesOrderLineCreate(BaseModel):
    """One line on an SO create payload.

    ``unit_price`` is optional. When omitted, the service falls back
    to the item's catalog ``unit_price`` (the list price) — Phase 1
    has no per-customer pricing table; every customer pays the list
    price unless overridden per line.
    """

    model_config = ConfigDict(extra="forbid")

    item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class SalesOrderCreate(BaseModel):
    """Payload to create a new SO in DRAFT status."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    customer_id: uuid.UUID
    expected_delivery_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    items: list[SalesOrderLineCreate] = Field(min_length=1)


class SalesOrderLineRead(BaseModel):
    """An SO line as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    created_at: datetime


class SalesOrderRead(BaseModel):
    """An SO header + lines as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    so_number: str
    customer_id: uuid.UUID
    order_date: date
    expected_delivery_date: date | None
    shipped_date: date | None
    status: SalesOrderStatus
    subtotal: Decimal
    total: Decimal
    notes: str | None
    items: list[SalesOrderLineRead]
    created_by_user_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class SalesOrderList(BaseModel):
    """Paginated envelope for ``GET /sales-orders`` (CLAUDE.md §6)."""

    items: list[SalesOrderRead]
    total: int
    limit: int
    offset: int
