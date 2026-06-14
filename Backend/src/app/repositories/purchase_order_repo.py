"""Data-access layer for ``purchase_orders`` (+ ``purchase_order_items``).

The receive flow needs a row-locking read; that's why ``get_by_id``
and ``get_by_id_for_update`` are separate methods rather than a flag
on one — the call sites are different enough that explicit naming
pays for itself.

Lines are loaded eagerly via the ``selectin`` relationship configured
on :class:`PurchaseOrder` so neither path has to remember to ``join``.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Select, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.purchase_order import PurchaseOrder, PurchaseOrderStatus


class PurchaseOrderRepository:
    """Repository for :class:`PurchaseOrder`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, po_id: uuid.UUID) -> PurchaseOrder | None:
        stmt = select(PurchaseOrder).where(PurchaseOrder.id == po_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_id_for_update(self, po_id: uuid.UUID) -> PurchaseOrder | None:
        """SELECT ... FOR UPDATE the PO row.

        Used by the receive flow to serialise concurrent receive
        attempts on the same PO. Without it, two parallel POST
        ``/receive`` calls could both pass the status check and
        double-apply stock movements before either commits.
        """
        stmt = select(PurchaseOrder).where(PurchaseOrder.id == po_id).with_for_update()
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        vendor_id: uuid.UUID | None = None,
        status: PurchaseOrderStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[PurchaseOrder], int]:
        """Return ``(page, total_matching)`` ordered newest first.

        ``date_from`` / ``date_to`` filter on ``order_date`` (the PO's
        own date), inclusive on both ends.
        """
        filtered: Select[tuple[PurchaseOrder]] = select(PurchaseOrder)
        if vendor_id is not None:
            filtered = filtered.where(PurchaseOrder.vendor_id == vendor_id)
        if status is not None:
            filtered = filtered.where(PurchaseOrder.status == status)
        if date_from is not None:
            filtered = filtered.where(PurchaseOrder.order_date >= date_from)
        if date_to is not None:
            filtered = filtered.where(PurchaseOrder.order_date <= date_to)

        count_stmt = select(func.count()).select_from(filtered.subquery())
        page_stmt = filtered.order_by(PurchaseOrder.created_at.desc()).limit(limit).offset(offset)

        total = (await self._session.execute(count_stmt)).scalar_one()
        page = list((await self._session.execute(page_stmt)).scalars().all())
        return page, int(total)

    async def add(self, po: PurchaseOrder) -> PurchaseOrder:
        """Persist a new PO (with its lines, via the relationship cascade).

        Flushes so server-side defaults populate; refresh so the caller
        sees the materialised columns (``created_at``, etc.).
        """
        self._session.add(po)
        await self._session.flush()
        await self._session.refresh(po)
        return po

    async def next_po_number(self) -> str:
        """Generate the next ``PO-YYYYMM-NNNNNN`` identifier.

        Uses the Postgres sequence ``purchase_order_number_seq``. The
        YYYYMM prefix is the *order date* (today), so monotonicity
        within a month is preserved while letting the year/month roll
        over naturally. The sequence is non-transactional, so a
        rolled-back PO leaves a gap — acceptable here.
        """
        result = await self._session.execute(text("SELECT nextval('purchase_order_number_seq')"))
        seq = int(result.scalar_one())
        today = date.today()
        return f"PO-{today:%Y%m}-{seq:06d}"
