"""Data-access layer for ``sales_activities`` (append-only)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sales_activity import ActivityType, SalesActivity


class SalesActivityRepository:
    """Repository for :class:`SalesActivity`. Insert + read only."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        type_: ActivityType | None = None,
        rep_user_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        lead_id: uuid.UUID | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> tuple[list[SalesActivity], int]:
        """Return ``(activities_page, total_matching)`` — most recent first."""
        filtered: Select[tuple[SalesActivity]] = select(SalesActivity)
        if type_ is not None:
            filtered = filtered.where(SalesActivity.type == type_)
        if rep_user_id is not None:
            filtered = filtered.where(SalesActivity.rep_user_id == rep_user_id)
        if customer_id is not None:
            filtered = filtered.where(SalesActivity.customer_id == customer_id)
        if lead_id is not None:
            filtered = filtered.where(SalesActivity.lead_id == lead_id)
        if occurred_from is not None:
            filtered = filtered.where(SalesActivity.occurred_at >= occurred_from)
        if occurred_to is not None:
            filtered = filtered.where(SalesActivity.occurred_at < occurred_to)

        count_stmt = select(func.count()).select_from(filtered.subquery())
        page_stmt = filtered.order_by(SalesActivity.occurred_at.desc()).limit(limit).offset(offset)

        total = (await self._session.execute(count_stmt)).scalar_one()
        page = list((await self._session.execute(page_stmt)).scalars().all())
        return page, int(total)

    async def add(self, activity: SalesActivity) -> SalesActivity:
        """Persist a new activity. Flush so server-side defaults populate."""
        self._session.add(activity)
        await self._session.flush()
        await self._session.refresh(activity)
        return activity
