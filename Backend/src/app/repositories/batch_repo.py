"""Data-access layer for ``batches``.

All SQL touching lots lives here. The item-stock reconciliation
(``Σ lot qty ≤ items.stock_quantity``) is composed in
:class:`~app.services.batch_service.BatchService`, which locks the item
row before reading :meth:`sum_quantity_for_item`.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import Batch, BatchStatus


class BatchRepository:
    """Repository for :class:`Batch`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, batch_id: uuid.UUID) -> Batch | None:
        stmt = select(Batch).where(Batch.id == batch_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_item_and_number(self, item_id: uuid.UUID, batch_number: str) -> Batch | None:
        stmt = select(Batch).where(Batch.item_id == item_id, Batch.batch_number == batch_number)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def sum_quantity_for_item(self, item_id: uuid.UUID) -> Decimal:
        """Total on-hand quantity already accounted for by lots of this item.

        ``coalesce(..., 0)`` so an item with no lots returns ``0``, not NULL.
        """
        stmt = select(func.coalesce(func.sum(Batch.quantity), 0)).where(Batch.item_id == item_id)
        return Decimal((await self._session.execute(stmt)).scalar_one())

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        item_id: uuid.UUID | None = None,
        status: BatchStatus | None = None,
        expiring_before: date | None = None,
    ) -> tuple[list[Batch], int]:
        """Return ``(lots_page, total_matching)`` ordered by soonest expiry first."""
        filtered: Select[tuple[Batch]] = select(Batch)
        if item_id is not None:
            filtered = filtered.where(Batch.item_id == item_id)
        if status is not None:
            filtered = filtered.where(Batch.batch_status == status)
        if expiring_before is not None:
            filtered = filtered.where(Batch.expiry_date <= expiring_before)

        count_stmt = select(func.count()).select_from(filtered.subquery())
        page_stmt = (
            filtered.order_by(Batch.expiry_date.asc(), Batch.created_at.asc())
            .limit(limit)
            .offset(offset)
        )

        total = (await self._session.execute(count_stmt)).scalar_one()
        page = list((await self._session.execute(page_stmt)).scalars().all())
        return page, int(total)

    async def list_consumable_for_item(self, item_id: uuid.UUID, *, as_of: date) -> list[Batch]:
        """Non-expired lots with stock for an item, earliest-expiry first, **locked**.

        For FEFO consumption (SO ship). ``with_for_update`` locks the lot rows
        so concurrent ships of the same item serialise and can't over-consume.
        Excludes expired (``expiry_date < as_of``) and depleted (``quantity = 0``)
        lots. ``batch_status`` is intentionally **not** filtered — QC-status
        eligibility (RELEASED-only) arrives with the QC workflow in a later phase.
        """
        stmt = (
            select(Batch)
            .where(
                Batch.item_id == item_id,
                Batch.expiry_date >= as_of,
                Batch.quantity > 0,
            )
            .order_by(Batch.expiry_date.asc(), Batch.created_at.asc())
            .with_for_update()
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def add(self, batch: Batch) -> Batch:
        """Persist a new lot. Flush so server-side defaults populate."""
        self._session.add(batch)
        await self._session.flush()
        await self._session.refresh(batch)
        return batch
