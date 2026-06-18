"""Data-access layer for ``customer_targets``."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer_target import CustomerTarget


class CustomerTargetRepository:
    """Repository for :class:`CustomerTarget`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, target_id: uuid.UUID) -> CustomerTarget | None:
        stmt = select(CustomerTarget).where(CustomerTarget.id == target_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_customer(self, customer_id: uuid.UUID) -> list[CustomerTarget]:
        """Return a customer's targets, most recent period first."""
        stmt = (
            select(CustomerTarget)
            .where(CustomerTarget.customer_id == customer_id)
            .order_by(CustomerTarget.period_start.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def find_overlapping(
        self,
        *,
        customer_id: uuid.UUID,
        period_start: date,
        period_end: date,
        exclude_id: uuid.UUID | None = None,
    ) -> CustomerTarget | None:
        """Return any existing target whose period overlaps the given one.

        Two half-open periods overlap when ``start < other_end`` and
        ``other_start < end``. ``exclude_id`` lets an update skip itself.
        """
        stmt = select(CustomerTarget).where(
            CustomerTarget.customer_id == customer_id,
            CustomerTarget.period_start < period_end,
            period_start < CustomerTarget.period_end,
        )
        if exclude_id is not None:
            stmt = stmt.where(CustomerTarget.id != exclude_id)
        return (await self._session.execute(stmt)).scalars().first()

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

    async def add(self, target: CustomerTarget) -> CustomerTarget:
        self._session.add(target)
        await self._session.flush()
        await self._session.refresh(target)
        return target
