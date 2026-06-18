"""Read-only data access for ``customer_targets`` (volume-achievement input)."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer_target import CustomerTarget


class CustomerTargetRepository:
    """Read-only repository for :class:`CustomerTarget`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def target_for_date(self, customer_id: uuid.UUID, on_date: date) -> CustomerTarget | None:
        """The target whose period contains ``on_date`` (``period_start <=
        on_date < period_end``). Drives customer-health volume achievement."""
        stmt = (
            select(CustomerTarget)
            .where(
                CustomerTarget.customer_id == customer_id,
                CustomerTarget.period_start <= on_date,
                on_date < CustomerTarget.period_end,
            )
            .order_by(CustomerTarget.period_start.desc())
        )
        return (await self._session.execute(stmt)).scalars().first()
