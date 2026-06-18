"""Data-access layer for the append-only score-snapshot tables.

Inserts and "latest per entity" reads for every engine's snapshots. Grows
over Phase 2B; 2B.1 covers :class:`LeadScore`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.score_snapshot import (
    CustomerHealthScore,
    LeadClassification,
    LeadScore,
)


class ScoreSnapshotRepository:
    """Repository for score snapshots (append-only)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- lead scores ------------------------------------------------------

    async def add_lead_score(self, score: LeadScore) -> LeadScore:
        self._session.add(score)
        await self._session.flush()
        await self._session.refresh(score)
        return score

    async def latest_lead_score(self, lead_id: uuid.UUID) -> LeadScore | None:
        stmt = (
            select(LeadScore)
            .where(LeadScore.lead_id == lead_id)
            .order_by(LeadScore.computed_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def lead_score_history(self, lead_id: uuid.UUID) -> list[LeadScore]:
        stmt = (
            select(LeadScore)
            .where(LeadScore.lead_id == lead_id)
            .order_by(LeadScore.computed_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def latest_lead_scores_map(self, lead_ids: list[uuid.UUID]) -> dict[uuid.UUID, LeadScore]:
        """Latest score per lead for a set of ids (no N+1).

        Uses ``DISTINCT ON (lead_id)`` ordered by ``computed_at`` desc.
        """
        if not lead_ids:
            return {}
        stmt = (
            select(LeadScore)
            .where(LeadScore.lead_id.in_(lead_ids))
            .distinct(LeadScore.lead_id)
            .order_by(LeadScore.lead_id, LeadScore.computed_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return {row.lead_id: row for row in rows}

    async def list_latest_lead_scores(
        self,
        *,
        limit: int,
        offset: int,
        classification: LeadClassification | None = None,
        assigned_to_user_id: uuid.UUID | None = None,
    ) -> tuple[list[tuple[LeadScore, Lead]], int]:
        """Latest score per **active** lead, joined to the lead, highest score
        first. Filters by classification and owning rep."""
        latest_ids = (
            select(LeadScore.id)
            .distinct(LeadScore.lead_id)
            .order_by(LeadScore.lead_id, LeadScore.computed_at.desc())
            .subquery()
        )
        filtered = (
            select(LeadScore, Lead)
            .join(Lead, Lead.id == LeadScore.lead_id)
            .where(LeadScore.id.in_(select(latest_ids.c.id)))
            .where(Lead.is_active.is_(True))
        )
        if classification is not None:
            filtered = filtered.where(LeadScore.classification == classification)
        if assigned_to_user_id is not None:
            filtered = filtered.where(Lead.assigned_to_user_id == assigned_to_user_id)

        count_stmt = select(func.count()).select_from(filtered.subquery())
        page_stmt = (
            filtered.order_by(LeadScore.total_score.desc(), LeadScore.computed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        total = (await self._session.execute(count_stmt)).scalar_one()
        rows = (await self._session.execute(page_stmt)).all()
        page = [(row[0], row[1]) for row in rows]
        return page, int(total)

    # --- customer-health scores ------------------------------------------

    async def add_customer_health_score(self, score: CustomerHealthScore) -> CustomerHealthScore:
        self._session.add(score)
        await self._session.flush()
        await self._session.refresh(score)
        return score

    async def customer_health_history(self, customer_id: uuid.UUID) -> list[CustomerHealthScore]:
        stmt = (
            select(CustomerHealthScore)
            .where(CustomerHealthScore.customer_id == customer_id)
            .order_by(CustomerHealthScore.computed_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())
