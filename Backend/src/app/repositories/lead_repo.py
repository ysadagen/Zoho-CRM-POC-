"""Data-access layer for ``leads`` and ``lead_stage_history``.

All SQL touching leads lives here. The append-only stage-history rows are
written through :meth:`add_stage_history`; the service composes the two so
a lead and its creation-history row are persisted in one transaction.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadSource, LeadStage, LeadStageHistory


class LeadRepository:
    """Repository for :class:`Lead` and its stage history."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, lead_id: uuid.UUID) -> Lead | None:
        stmt = select(Lead).where(Lead.id == lead_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        stage: LeadStage | None = None,
        source: LeadSource | None = None,
        assigned_to_user_id: uuid.UUID | None = None,
        state: str | None = None,
        district: str | None = None,
        created_from: date | None = None,
        created_to: date | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Lead], int]:
        """Return ``(leads_page, total_matching)`` — count after filters,
        before pagination, newest first."""
        filtered: Select[tuple[Lead]] = select(Lead)
        if search is not None:
            term = f"%{search.lower()}%"
            filtered = filtered.where(
                or_(
                    func.lower(Lead.contact_name).like(term),
                    func.lower(Lead.email).like(term),
                )
            )
        if stage is not None:
            filtered = filtered.where(Lead.stage == stage)
        if source is not None:
            filtered = filtered.where(Lead.source == source)
        if assigned_to_user_id is not None:
            filtered = filtered.where(Lead.assigned_to_user_id == assigned_to_user_id)
        if state is not None:
            filtered = filtered.where(Lead.state == state)
        if district is not None:
            filtered = filtered.where(Lead.district == district)
        if created_from is not None:
            filtered = filtered.where(Lead.created_at >= created_from)
        if created_to is not None:
            filtered = filtered.where(Lead.created_at < created_to)
        if is_active is not None:
            filtered = filtered.where(Lead.is_active == is_active)

        count_stmt = select(func.count()).select_from(filtered.subquery())
        page_stmt = filtered.order_by(Lead.created_at.desc()).limit(limit).offset(offset)

        total = (await self._session.execute(count_stmt)).scalar_one()
        page = list((await self._session.execute(page_stmt)).scalars().all())
        return page, int(total)

    async def list_stage_history(self, lead_id: uuid.UUID) -> list[LeadStageHistory]:
        """Return a lead's stage history, newest first."""
        stmt = (
            select(LeadStageHistory)
            .where(LeadStageHistory.lead_id == lead_id)
            .order_by(LeadStageHistory.changed_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def add(self, lead: Lead) -> Lead:
        """Persist a new lead. Flush so server-side defaults populate."""
        self._session.add(lead)
        await self._session.flush()
        await self._session.refresh(lead)
        return lead

    async def add_stage_history(self, history: LeadStageHistory) -> LeadStageHistory:
        """Append a stage-transition row (never updated/deleted)."""
        self._session.add(history)
        await self._session.flush()
        return history

    async def next_lead_number(self) -> str:
        """Generate the next ``LD-YYYYMM-NNNNNN`` identifier.

        Uses the Postgres sequence ``lead_number_seq`` — mirrors the
        ``sales_order_number_seq`` precedent. Non-transactional, so a
        rolled-back lead leaves a gap; that's acceptable (numbers are for
        identification, not accounting continuity).
        """
        result = await self._session.execute(text("SELECT nextval('lead_number_seq')"))
        seq = int(result.scalar_one())
        today = date.today()
        return f"LD-{today:%Y%m}-{seq:06d}"
