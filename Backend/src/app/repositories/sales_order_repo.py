"""Data-access layer for ``sales_orders`` (+ ``sales_order_items``).

Symmetric to :class:`PurchaseOrderRepository`. ``get_by_id`` returns
a normal read; ``get_by_id_for_update`` adds ``SELECT ... FOR UPDATE``
to serialise concurrent ship attempts on the same SO.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Select, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sales_order import SalesOrder, SalesOrderStatus


class SalesOrderRepository:
    """Repository for :class:`SalesOrder`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, so_id: uuid.UUID) -> SalesOrder | None:
        stmt = select(SalesOrder).where(SalesOrder.id == so_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_id_for_update(self, so_id: uuid.UUID) -> SalesOrder | None:
        """SELECT ... FOR UPDATE the SO row.

        Used by the ship flow to serialise concurrent ship attempts on
        the same SO. Without it, two parallel POST ``/ship`` calls
        could both pass the status check and double-deduct stock.
        """
        stmt = select(SalesOrder).where(SalesOrder.id == so_id).with_for_update()
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        customer_id: uuid.UUID | None = None,
        status: SalesOrderStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[SalesOrder], int]:
        """Return ``(page, total_matching)`` ordered newest first.

        ``date_from`` / ``date_to`` filter on ``order_date``, inclusive
        on both ends.
        """
        filtered: Select[tuple[SalesOrder]] = select(SalesOrder)
        if customer_id is not None:
            filtered = filtered.where(SalesOrder.customer_id == customer_id)
        if status is not None:
            filtered = filtered.where(SalesOrder.status == status)
        if date_from is not None:
            filtered = filtered.where(SalesOrder.order_date >= date_from)
        if date_to is not None:
            filtered = filtered.where(SalesOrder.order_date <= date_to)

        count_stmt = select(func.count()).select_from(filtered.subquery())
        page_stmt = filtered.order_by(SalesOrder.created_at.desc()).limit(limit).offset(offset)

        total = (await self._session.execute(count_stmt)).scalar_one()
        page = list((await self._session.execute(page_stmt)).scalars().all())
        return page, int(total)

    async def add(self, so: SalesOrder) -> SalesOrder:
        """Persist a new SO (with its lines, via the relationship cascade)."""
        self._session.add(so)
        await self._session.flush()
        await self._session.refresh(so)
        return so

    async def next_so_number(self) -> str:
        """Generate the next ``SO-YYYYMM-NNNNNN`` identifier.

        Uses the Postgres sequence ``sales_order_number_seq``. YYYYMM
        prefix is the order date (today). Non-transactional sequence
        means a rolled-back SO leaves a gap — acceptable per the
        Phase 7 precedent.
        """
        result = await self._session.execute(text("SELECT nextval('sales_order_number_seq')"))
        seq = int(result.scalar_one())
        today = date.today()
        return f"SO-{today:%Y%m}-{seq:06d}"
