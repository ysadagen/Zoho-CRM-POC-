"""Read-only data access for ``leads`` (cohort + scoring inputs).

This service does not create or mutate leads (the Backend owns that); it only
reads them to score. Exposes the lookups the lead-scoring engine needs:
fetch-by-id, the active-lead sweep, and the cohort-max-quantity normalizer.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item, ItemType
from app.models.lead import Lead


class LeadRepository:
    """Read-only repository for :class:`Lead`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, lead_id: uuid.UUID) -> Lead | None:
        stmt = select(Lead).where(Lead.id == lead_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_all_active(self) -> list[Lead]:
        """Every active lead (unpaginated) — the live/recompute cohort."""
        stmt = select(Lead).where(Lead.is_active.is_(True)).order_by(Lead.created_at)
        return list((await self._session.execute(stmt)).scalars().all())

    async def cohort_max_quantity(
        self, *, created_since: date, item_type: ItemType | None
    ) -> Decimal | None:
        """Max ``quantity`` over cohort leads (created on/after ``created_since``,
        non-null quantity) — restricted to leads whose linked item has
        ``item_type`` when given (§4.4). None for an empty cohort.
        """
        stmt = select(func.max(Lead.quantity)).where(
            Lead.quantity.is_not(None),
            Lead.created_at >= created_since,
        )
        if item_type is not None:
            stmt = stmt.join(Item, Item.id == Lead.item_id).where(Item.type == item_type)
        result = (await self._session.execute(stmt)).scalar_one_or_none()
        return Decimal(result) if result is not None else None
