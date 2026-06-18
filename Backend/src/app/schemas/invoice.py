"""Invoice + Payment Pydantic schemas.

``invoice_number`` is server-generated, never supplied. ``outstanding`` /
``is_paid`` / ``is_overdue`` are derived (never stored) and assembled by
:meth:`InvoiceRead.from_invoice`, which keeps the derivation rule in the
schema layer that owns the read shape.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from app.models.invoice import Invoice

__all__ = [
    "InvoiceCreate",
    "InvoiceDetailRead",
    "InvoiceList",
    "InvoiceRead",
    "PaymentCreate",
    "PaymentRead",
]


class InvoiceCreate(BaseModel):
    """Payload to create an invoice. ``invoice_number`` is generated."""

    model_config = ConfigDict(extra="forbid")

    customer_id: uuid.UUID
    invoice_date: date
    due_date: date
    amount: Decimal = Field(gt=0)
    sales_order_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _check_due_date(self) -> InvoiceCreate:
        if self.due_date < self.invoice_date:
            raise ValueError("due_date cannot be before invoice_date")
        return self


class PaymentCreate(BaseModel):
    """Payload to record a payment against an invoice."""

    model_config = ConfigDict(extra="forbid")

    paid_date: date
    amount: Decimal = Field(gt=0)


class PaymentRead(BaseModel):
    """A payment as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    paid_date: date
    amount: Decimal
    created_at: datetime


class InvoiceRead(BaseModel):
    """Invoice as returned to clients, with the derived balance fields."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str
    customer_id: uuid.UUID
    sales_order_id: uuid.UUID | None
    invoice_date: date
    due_date: date
    amount: Decimal
    amount_paid: Decimal
    outstanding: Decimal
    is_paid: bool
    is_overdue: bool
    created_by_user_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_invoice(cls, invoice: Invoice, paid_total: Decimal, *, today: date) -> InvoiceRead:
        # Normalise money to 2 dp so derived fields serialise consistently
        # (e.g. "0.00", not "0") regardless of the SUM()'s native scale.
        cents = Decimal("0.01")
        paid = paid_total.quantize(cents)
        outstanding = (invoice.amount - paid_total).quantize(cents)
        return cls(
            id=invoice.id,
            invoice_number=invoice.invoice_number,
            customer_id=invoice.customer_id,
            sales_order_id=invoice.sales_order_id,
            invoice_date=invoice.invoice_date,
            due_date=invoice.due_date,
            amount=invoice.amount,
            amount_paid=paid,
            outstanding=outstanding,
            is_paid=outstanding <= 0,
            is_overdue=outstanding > 0 and invoice.due_date < today,
            created_by_user_id=invoice.created_by_user_id,
            updated_by_user_id=invoice.updated_by_user_id,
            created_at=invoice.created_at,
            updated_at=invoice.updated_at,
        )


class InvoiceDetailRead(InvoiceRead):
    """Invoice detail — the record plus its payments (newest first)."""

    payments: list[PaymentRead]


class InvoiceList(BaseModel):
    """Paginated envelope for ``GET /invoices`` (CLAUDE.md §6)."""

    items: list[InvoiceRead]
    total: int
    limit: int
    offset: int
