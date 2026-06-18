"""Read-only data access for the ``customers`` table."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer


class CustomerRepository:
    """Read-only repository for :class:`Customer`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None:
        stmt = select(Customer).where(Customer.id == customer_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_all_active(self) -> list[Customer]:
        """Every active customer (unpaginated) — for cohort scoring engines."""
        stmt = select(Customer).where(Customer.is_active.is_(True)).order_by(Customer.company_name)
        return list((await self._session.execute(stmt)).scalars().all())
