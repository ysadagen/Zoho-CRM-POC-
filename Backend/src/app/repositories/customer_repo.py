"""Data-access layer for the ``customers`` table."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer


class CustomerRepository:
    """Repository for :class:`Customer`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None:
        stmt = select(Customer).where(Customer.id == customer_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, customer_code: str) -> Customer | None:
        stmt = select(Customer).where(Customer.customer_code == customer_code)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_gstin(self, gstin: str) -> Customer | None:
        stmt = select(Customer).where(Customer.gstin == gstin)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        is_privileged: bool | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Customer], int]:
        """Return ``(customers_page, total_matching)``.

        ``total`` is the count after filters but before pagination —
        what the UI needs to render pager controls.
        """
        filtered: Select[tuple[Customer]] = select(Customer)
        if search:
            term = f"%{search.lower()}%"
            filtered = filtered.where(
                or_(
                    func.lower(Customer.company_name).like(term),
                    func.lower(Customer.customer_code).like(term),
                )
            )
        if is_privileged is not None:
            filtered = filtered.where(Customer.is_privileged == is_privileged)
        if is_active is not None:
            filtered = filtered.where(Customer.is_active == is_active)

        count_stmt = select(func.count()).select_from(filtered.subquery())
        page_stmt = filtered.order_by(Customer.created_at.desc()).limit(limit).offset(offset)

        total = (await self._session.execute(count_stmt)).scalar_one()
        page = list((await self._session.execute(page_stmt)).scalars().all())
        return page, int(total)

    async def add(self, customer: Customer) -> Customer:
        """Persist a new customer. Flush so server-side defaults populate."""
        self._session.add(customer)
        await self._session.flush()
        await self._session.refresh(customer)
        return customer
