"""Data-access layer for the ``vendors`` table."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vendor import Vendor


class VendorRepository:
    """Repository for :class:`Vendor`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, vendor_id: uuid.UUID) -> Vendor | None:
        stmt = select(Vendor).where(Vendor.id == vendor_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, vendor_code: str) -> Vendor | None:
        stmt = select(Vendor).where(Vendor.vendor_code == vendor_code)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_gstin(self, gstin: str) -> Vendor | None:
        stmt = select(Vendor).where(Vendor.gstin == gstin)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Vendor], int]:
        """Return ``(vendors_page, total_matching)``.

        ``total`` is the count after filters but before pagination —
        what the UI needs to render pager controls.
        """
        filtered: Select[tuple[Vendor]] = select(Vendor)
        if search:
            term = f"%{search.lower()}%"
            filtered = filtered.where(
                or_(
                    func.lower(Vendor.vendor_name).like(term),
                    func.lower(Vendor.vendor_code).like(term),
                )
            )
        if is_active is not None:
            filtered = filtered.where(Vendor.is_active == is_active)

        count_stmt = select(func.count()).select_from(filtered.subquery())
        page_stmt = filtered.order_by(Vendor.created_at.desc()).limit(limit).offset(offset)

        total = (await self._session.execute(count_stmt)).scalar_one()
        page = list((await self._session.execute(page_stmt)).scalars().all())
        return page, int(total)

    async def add(self, vendor: Vendor) -> Vendor:
        """Persist a new vendor. Flush so server-side defaults populate."""
        self._session.add(vendor)
        await self._session.flush()
        await self._session.refresh(vendor)
        return vendor
