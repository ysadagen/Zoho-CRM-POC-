"""Data-access layer for ``stock_movements``.

Read paths are normal SQLAlchemy queries. The write path is **insert
only** (``add``) — there is no ``update`` method here on purpose: the
ledger is append-only.

The item-stock mutation that pairs with each ledger insert lives in
:class:`StockMovementService`, not here, because it needs to compose
``SELECT ... FOR UPDATE`` on the items row with the insert in one
transaction.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock_movement import (
    MovementDirection,
    MovementReason,
    StockMovement,
)


class StockMovementRepository:
    """Repository for :class:`StockMovement`. Append-only by design."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, movement_id: uuid.UUID) -> StockMovement | None:
        stmt = select(StockMovement).where(StockMovement.id == movement_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        item_id: uuid.UUID | None = None,
        direction: MovementDirection | None = None,
        reason: MovementReason | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[StockMovement], int]:
        """Return ``(movements_page, total_matching)`` ordered newest first.

        ``date_from`` is inclusive at the start of day; ``date_to`` is
        inclusive at the end of day — i.e. ``created_at < (date_to + 1d)``.
        """
        filtered: Select[tuple[StockMovement]] = select(StockMovement)
        if item_id is not None:
            filtered = filtered.where(StockMovement.item_id == item_id)
        if direction is not None:
            filtered = filtered.where(StockMovement.direction == direction)
        if reason is not None:
            filtered = filtered.where(StockMovement.reason == reason)
        if date_from is not None:
            filtered = filtered.where(
                StockMovement.created_at >= datetime.combine(date_from, datetime.min.time())
            )
        if date_to is not None:
            # Inclusive end-of-day: created_at < (date_to + 1 day).
            from datetime import timedelta

            end_exclusive = datetime.combine(date_to + timedelta(days=1), datetime.min.time())
            filtered = filtered.where(StockMovement.created_at < end_exclusive)

        count_stmt = select(func.count()).select_from(filtered.subquery())
        page_stmt = filtered.order_by(StockMovement.created_at.desc()).limit(limit).offset(offset)

        total = (await self._session.execute(count_stmt)).scalar_one()
        page = list((await self._session.execute(page_stmt)).scalars().all())
        return page, int(total)

    async def add(self, movement: StockMovement) -> StockMovement:
        """Persist a new ledger row. Flush so server-side defaults populate.

        The caller (always :class:`StockMovementService`) owns the
        transaction — we never commit here, so the item-stock update
        and the ledger insert are atomic together.
        """
        self._session.add(movement)
        await self._session.flush()
        await self._session.refresh(movement)
        return movement
