"""Invoice + payment business logic.

Enforces the one rule the DB can't express cheaply: total payments may not
exceed the invoice amount (409 ``OVERPAYMENT``). ``outstanding`` is always
derived from ``amount - sum(payments)`` and returned as ``(invoice, paid_total)``
pairs so the endpoint can assemble the read model.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.invoice import Invoice, Payment
from app.repositories.customer_repo import CustomerRepository
from app.repositories.invoice_repo import InvoiceRepository
from app.repositories.sales_order_repo import SalesOrderRepository
from app.schemas.invoice import InvoiceCreate, PaymentCreate

logger = logging.getLogger(__name__)


class InvoiceService:
    """Orchestrates invoice create / read and payment recording."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._invoices = InvoiceRepository(session)
        self._customers = CustomerRepository(session)
        self._sos = SalesOrderRepository(session)

    async def create_invoice(self, payload: InvoiceCreate, *, actor_id: uuid.UUID) -> Invoice:
        """Create an invoice. 404 if the customer (or supplied sales order)
        does not exist."""
        if await self._customers.get_by_id(payload.customer_id) is None:
            raise NotFoundError("Customer not found", code="CUSTOMER_NOT_FOUND")
        if payload.sales_order_id is not None:
            so = await self._sos.get_by_id(payload.sales_order_id)
            if so is None:
                raise NotFoundError("Sales order not found", code="SALES_ORDER_NOT_FOUND")

        invoice_number = await self._invoices.next_invoice_number()
        invoice = Invoice(
            invoice_number=invoice_number,
            customer_id=payload.customer_id,
            sales_order_id=payload.sales_order_id,
            invoice_date=payload.invoice_date,
            due_date=payload.due_date,
            amount=payload.amount,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        invoice = await self._invoices.add(invoice)
        await self._session.commit()
        await self._session.refresh(invoice)
        logger.info(
            "invoice_created",
            extra={"invoice_id": str(invoice.id), "invoice_number": invoice.invoice_number},
        )
        return invoice

    async def get_invoice(
        self, invoice_id: uuid.UUID
    ) -> tuple[Invoice, Decimal, list[Payment]]:
        """Return ``(invoice, paid_total, payments)`` for the detail view."""
        invoice = await self._require_invoice(invoice_id)
        paid = await self._invoices.paid_total(invoice_id)
        payments = await self._invoices.list_payments(invoice_id)
        return invoice, paid, payments

    async def list_invoices(
        self,
        *,
        limit: int,
        offset: int,
        customer_id: uuid.UUID | None = None,
    ) -> tuple[list[tuple[Invoice, Decimal]], int]:
        """Return ``([(invoice, paid_total)], total)`` — paid totals batched."""
        invoices, total = await self._invoices.list_(
            limit=limit, offset=offset, customer_id=customer_id
        )
        paid_map = await self._invoices.paid_totals([inv.id for inv in invoices])
        enriched = [(inv, paid_map.get(inv.id, Decimal("0"))) for inv in invoices]
        return enriched, total

    async def record_payment(
        self,
        invoice_id: uuid.UUID,
        payload: PaymentCreate,
        *,
        actor_id: uuid.UUID,
    ) -> tuple[Invoice, Decimal]:
        """Record a payment. 404 if the invoice is unknown; 409
        ``OVERPAYMENT`` if it would exceed the invoice amount.

        Returns the invoice with its new paid total.
        """
        invoice = await self._require_invoice(invoice_id)
        already_paid = await self._invoices.paid_total(invoice_id)
        if already_paid + payload.amount > invoice.amount:
            raise ConflictError(
                "Payment would exceed the invoice amount",
                code="OVERPAYMENT",
            )

        await self._invoices.add_payment(
            Payment(
                invoice_id=invoice_id,
                paid_date=payload.paid_date,
                amount=payload.amount,
                created_by_user_id=actor_id,
                updated_by_user_id=actor_id,
            )
        )
        await self._session.commit()
        new_paid = already_paid + payload.amount
        logger.info(
            "payment_recorded",
            extra={
                "invoice_id": str(invoice_id),
                "amount": str(payload.amount),
                "paid_total": str(new_paid),
            },
        )
        return invoice, new_paid

    async def _require_invoice(self, invoice_id: uuid.UUID) -> Invoice:
        invoice = await self._invoices.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundError("Invoice not found", code="INVOICE_NOT_FOUND")
        return invoice
