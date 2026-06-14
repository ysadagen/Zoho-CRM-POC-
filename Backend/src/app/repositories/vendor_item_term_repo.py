"""Data-access layer for ``vendor_item_terms``.

Owns the overlap-detection SQL — the central business invariant for
this resource. See :meth:`find_overlapping_active` for the predicate.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vendor_item_term import VendorItemTerm


class VendorItemTermRepository:
    """Repository for :class:`VendorItemTerm`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, term_id: uuid.UUID) -> VendorItemTerm | None:
        stmt = select(VendorItemTerm).where(VendorItemTerm.id == term_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_vendor(
        self,
        *,
        vendor_id: uuid.UUID,
        limit: int,
        offset: int,
        item_id: uuid.UUID | None = None,
        active_only: bool = False,
    ) -> tuple[list[VendorItemTerm], int]:
        """Return ``(terms_page, total_matching)`` scoped to ``vendor_id``."""
        filtered: Select[tuple[VendorItemTerm]] = select(VendorItemTerm).where(
            VendorItemTerm.vendor_id == vendor_id
        )
        if item_id is not None:
            filtered = filtered.where(VendorItemTerm.item_id == item_id)
        if active_only:
            filtered = filtered.where(VendorItemTerm.is_active.is_(True))

        count_stmt = select(func.count()).select_from(filtered.subquery())
        page_stmt = (
            filtered.order_by(VendorItemTerm.effective_from.desc()).limit(limit).offset(offset)
        )

        total = (await self._session.execute(count_stmt)).scalar_one()
        page = list((await self._session.execute(page_stmt)).scalars().all())
        return page, int(total)

    async def find_overlapping_active(
        self,
        *,
        vendor_id: uuid.UUID,
        item_id: uuid.UUID,
        effective_from: date,
        effective_to: date | None,
        exclude_id: uuid.UUID | None = None,
    ) -> list[VendorItemTerm]:
        """Find active terms that overlap with ``[effective_from, effective_to]``.

        Two ranges ``[a1, a2]`` and ``[b1, b2]`` overlap iff
        ``a1 <= b2 AND b1 <= a2``. With nullable end dates treated as
        ``+infinity``:

        - ``existing.effective_to IS NULL`` ⇒ always satisfies
          ``new_from <= existing_to``
        - ``new_effective_to IS NULL`` ⇒ always satisfies
          ``existing_from <= new_to``

        ``exclude_id`` lets an UPDATE skip self-conflict.
        """
        stmt = select(VendorItemTerm).where(
            VendorItemTerm.vendor_id == vendor_id,
            VendorItemTerm.item_id == item_id,
            VendorItemTerm.is_active.is_(True),
            or_(
                VendorItemTerm.effective_to.is_(None),
                VendorItemTerm.effective_to >= effective_from,
            ),
        )
        if effective_to is not None:
            stmt = stmt.where(VendorItemTerm.effective_from <= effective_to)
        if exclude_id is not None:
            stmt = stmt.where(VendorItemTerm.id != exclude_id)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, term: VendorItemTerm) -> VendorItemTerm:
        """Persist a new term. Flush so server-side defaults populate."""
        self._session.add(term)
        await self._session.flush()
        await self._session.refresh(term)
        return term
