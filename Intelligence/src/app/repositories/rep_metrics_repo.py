"""Per-rep aggregate metric queries backing the effort & efficiency engine.

Read-only aggregates over a rep's activities and assigned leads in a period.
Kept out of the entity repositories so the scoring orchestrator stays free of
SQL. Windows are half-open ``[start, end)``.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadStage
from app.models.sales_activity import ActivityType, SalesActivity
from app.models.score_snapshot import LeadClassification, LeadScore

_EFFORT_TYPES = (
    ActivityType.VISIT,
    ActivityType.MEETING,
    ActivityType.FOLLOW_UP,
    ActivityType.CALL,
)
_TYPE_TO_COUNT_KEY = {
    ActivityType.VISIT: "visits",
    ActivityType.MEETING: "meetings",
    ActivityType.FOLLOW_UP: "follow_ups",
    ActivityType.CALL: "calls",
}


class RepMetricsRepository:
    """Aggregate metrics for one rep over a period."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def effort_counts(self, rep_id: uuid.UUID, start: date, end: date) -> dict[str, Any]:
        """Per-type activity counts + total hours logged (effort inputs).

        COMPLAINT is excluded — it does not count toward effort (§5.1).
        """
        stmt = (
            select(
                SalesActivity.type,
                func.count(),
                func.coalesce(func.sum(SalesActivity.duration_minutes), 0),
            )
            .where(
                SalesActivity.rep_user_id == rep_id,
                SalesActivity.type.in_(_EFFORT_TYPES),
                SalesActivity.occurred_at >= start,
                SalesActivity.occurred_at < end,
            )
            .group_by(SalesActivity.type)
        )
        counts: dict[str, Any] = {
            "visits": 0,
            "meetings": 0,
            "follow_ups": 0,
            "calls": 0,
            "hours_logged": 0.0,
        }
        total_minutes = 0
        for activity_type, count, minutes in (await self._session.execute(stmt)).all():
            counts[_TYPE_TO_COUNT_KEY[activity_type]] = int(count)
            total_minutes += int(minutes)
        counts["hours_logged"] = total_minutes / 60
        return counts

    async def lead_outcome_counts(
        self, rep_id: uuid.UUID, start: date, end: date
    ) -> dict[str, Any]:
        """Assigned / progressed / won counts, won-value sum, and avg days to
        close — over leads assigned to ``rep_id`` and created in the window.

        "Progressed" = stage is no longer NEW (leaving NEW always writes a
        transition row), so ``stage != NEW`` captures "≥1 transition" exactly.
        """
        close_days = func.extract("epoch", Lead.won_at - Lead.created_at) / 86400
        stmt = select(
            func.count(),
            func.count().filter(Lead.stage != LeadStage.NEW),
            func.count().filter(Lead.stage == LeadStage.WON),
            func.coalesce(func.sum(Lead.won_value).filter(Lead.stage == LeadStage.WON), 0),
            func.avg(close_days).filter(Lead.stage == LeadStage.WON),
        ).where(
            Lead.assigned_to_user_id == rep_id,
            Lead.created_at >= start,
            Lead.created_at < end,
        )
        assigned, progressed, won, won_value_sum, avg_close = (
            await self._session.execute(stmt)
        ).one()
        return {
            "assigned": int(assigned),
            "progressed": int(progressed),
            "won": int(won),
            "won_value_sum": Decimal(won_value_sum),
            "avg_time_to_close": float(avg_close) if avg_close is not None else None,
        }

    async def lead_effort_points(
        self,
        rep_id: uuid.UUID,
        start: date,
        end: date,
        *,
        activity_weights: dict[str, int],
        time_points_per_hour: int,
    ) -> tuple[float, float]:
        """Return ``(hot_lead_points, all_lead_points)`` — effort points from
        the rep's lead-linked (non-COMPLAINT) activities in the window, split
        by whether the lead's latest score is HOT (§5.2 utilization).
        """
        latest = (
            select(LeadScore.lead_id.label("lead_id"), LeadScore.classification.label("cls"))
            .distinct(LeadScore.lead_id)
            .order_by(LeadScore.lead_id, LeadScore.computed_at.desc())
            .subquery()
        )
        stmt = (
            select(
                SalesActivity.type,
                SalesActivity.duration_minutes,
                latest.c.cls,
            )
            .select_from(SalesActivity)
            .outerjoin(latest, latest.c.lead_id == SalesActivity.lead_id)
            .where(
                SalesActivity.rep_user_id == rep_id,
                SalesActivity.lead_id.is_not(None),
                SalesActivity.type.in_(_EFFORT_TYPES),
                SalesActivity.occurred_at >= start,
                SalesActivity.occurred_at < end,
            )
        )
        hot = 0.0
        total = 0.0
        for activity_type, duration, classification in (await self._session.execute(stmt)).all():
            points = activity_weights[activity_type.value] + (
                (duration or 0) / 60 * time_points_per_hour
            )
            total += points
            if classification == LeadClassification.HOT:
                hot += points
        return hot, total
