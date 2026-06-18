"""Data-access layer for ``invoices`` and ``payments``."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice, Payment


class InvoiceRepository:
    """Repository for :class:`Invoice` and its :class:`Payment` rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, invoice_id: uuid.UUID) -> Invoice | None:
        stmt = select(Invoice).where(Invoice.id == invoice_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        customer_id: uuid.UUID | None = None,
    ) -> tuple[list[Invoice], int]:
        """Return ``(invoices_page, total)`` — newest invoice date first."""
        filtered: Select[tuple[Invoice]] = select(Invoice)
        if customer_id is not None:
            filtered = filtered.where(Invoice.customer_id == customer_id)

        count_stmt = select(func.count()).select_from(filtered.subquery())
        page_stmt = (
            filtered.order_by(Invoice.invoice_date.desc(), Invoice.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        total = (await self._session.execute(count_stmt)).scalar_one()
        page = list((await self._session.execute(page_stmt)).scalars().all())
        return page, int(total)

    async def paid_total(self, invoice_id: uuid.UUID) -> Decimal:
        """Sum of payments applied to one invoice (0 if none)."""
        stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.invoice_id == invoice_id
        )
        return Decimal((await self._session.execute(stmt)).scalar_one())

    async def paid_totals(self, invoice_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
        """Sum of payments per invoice id, for a page of invoices (no N+1)."""
        if not invoice_ids:
            return {}
        stmt = (
            select(Payment.invoice_id, func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.invoice_id.in_(invoice_ids))
            .group_by(Payment.invoice_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return {row[0]: Decimal(row[1]) for row in rows}

    async def list_payments(self, invoice_id: uuid.UUID) -> list[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.invoice_id == invoice_id)
            .order_by(Payment.paid_date.desc(), Payment.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def add(self, invoice: Invoice) -> Invoice:
        self._session.add(invoice)
        await self._session.flush()
        await self._session.refresh(invoice)
        return invoice

    async def add_payment(self, payment: Payment) -> Payment:
        self._session.add(payment)
        await self._session.flush()
        await self._session.refresh(payment)
        return payment

    async def next_invoice_number(self) -> str:
        """Generate the next ``INV-YYYYMM-NNNNNN`` identifier via sequence."""
        result = await self._session.execute(text("SELECT nextval('invoice_number_seq')"))
        seq = int(result.scalar_one())
        today = date.today()
        return f"INV-{today:%Y%m}-{seq:06d}"
