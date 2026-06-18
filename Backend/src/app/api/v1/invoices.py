"""Invoice endpoints — create / list / detail, plus recording payments.

Invoices and payments are not editable or deletable; a correction is a new
payment (or a credit note in a future phase). ``outstanding`` / ``is_paid`` /
``is_overdue`` are derived per request from the payments applied so far.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceDetailRead,
    InvoiceList,
    InvoiceRead,
    PaymentCreate,
    PaymentRead,
)
from app.services.invoice_service import InvoiceService

router = APIRouter(prefix="/invoices", tags=["invoices"])

_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an invoice",
)
async def create_invoice(
    payload: InvoiceCreate,
    session: _Session,
    current_user: _CurrentUser,
) -> InvoiceRead:
    """Create an invoice (number is generated). 404 if the customer or
    referenced sales order does not exist; 422 if ``due_date`` precedes
    ``invoice_date``."""
    invoice = await InvoiceService(session).create_invoice(payload, actor_id=current_user.id)
    return InvoiceRead.from_invoice(invoice, paid_total=Decimal("0"), today=date.today())


@router.get(
    "",
    response_model=InvoiceList,
    summary="List invoices with pagination",
)
async def list_invoices(
    session: _Session,
    current_user: _CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    customer_id: Annotated[uuid.UUID | None, Query()] = None,
) -> InvoiceList:
    """Return a page of invoices, newest first, with derived balances.
    Filter by ``customer_id``."""
    today = date.today()
    enriched, total = await InvoiceService(session).list_invoices(
        limit=limit, offset=offset, customer_id=customer_id
    )
    return InvoiceList(
        items=[InvoiceRead.from_invoice(inv, paid, today=today) for inv, paid in enriched],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceDetailRead,
    summary="Return an invoice by id with its payments",
)
async def get_invoice(
    invoice_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> InvoiceDetailRead:
    """Return one invoice, its derived balance, and its payments (newest
    first). 404 if the id does not exist."""
    invoice, paid, payments = await InvoiceService(session).get_invoice(invoice_id)
    base = InvoiceRead.from_invoice(invoice, paid, today=date.today())
    return InvoiceDetailRead(
        **base.model_dump(),
        payments=[PaymentRead.model_validate(p) for p in payments],
    )


@router.post(
    "/{invoice_id}/payments",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a payment against an invoice",
)
async def record_payment(
    invoice_id: uuid.UUID,
    payload: PaymentCreate,
    session: _Session,
    current_user: _CurrentUser,
) -> InvoiceRead:
    """Record a payment. 404 if the invoice is unknown; 409 ``OVERPAYMENT``
    if the total paid would exceed the invoice amount. Returns the invoice
    with its updated balance."""
    invoice, paid = await InvoiceService(session).record_payment(
        invoice_id, payload, actor_id=current_user.id
    )
    return InvoiceRead.from_invoice(invoice, paid, today=date.today())
