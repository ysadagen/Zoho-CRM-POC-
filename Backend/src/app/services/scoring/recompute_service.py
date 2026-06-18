"""Recompute orchestrator (§8).

Re-scores and snapshots every active entity for one engine (or all four),
using each engine's active config. Synchronous and idempotent in effect — it
appends a fresh snapshot per entity, never mutates prior rows (snapshots are
append-only). A scheduled job (Windows Task Scheduler / cron hitting
``POST /intelligence/recompute`` — no new infra) calls this nightly so the
cohort engines accumulate trend history; lead scores additionally reconcile
cohort drift here (Decision D-9).
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scoring_config import ScoringEngine
from app.services.scoring.beat_planning import BeatPlanningService
from app.services.scoring.customer_health import CustomerHealthService
from app.services.scoring.effort_efficiency import EffortEfficiencyService
from app.services.scoring.lead_scoring import LeadScoringService

logger = logging.getLogger(__name__)


class RecomputeService:
    """Runs the snapshot sweep for one or all scoring engines."""

    def __init__(self, session: AsyncSession) -> None:
        self._lead = LeadScoringService(session)
        self._health = CustomerHealthService(session)
        self._effort = EffortEfficiencyService(session)
        self._beat = BeatPlanningService(session)

    async def recompute(self, engine: ScoringEngine | None) -> dict[str, int]:
        """Recompute ``engine`` (or all engines when ``None``).

        Returns ``{engine_value: entities_scored}`` for every engine run.
        Each engine commits its own sweep, so a partial failure leaves earlier
        engines' snapshots persisted (and is surfaced to the caller).
        """
        results: dict[str, int] = {}

        if engine in (None, ScoringEngine.LEAD_SCORING):
            results[ScoringEngine.LEAD_SCORING.value] = await self._lead.recompute_all()
        if engine in (None, ScoringEngine.CUSTOMER_HEALTH):
            results[ScoringEngine.CUSTOMER_HEALTH.value] = await self._health.snapshot_all()
        if engine in (None, ScoringEngine.EFFORT_EFFICIENCY):
            results[ScoringEngine.EFFORT_EFFICIENCY.value] = await self._effort.snapshot_all()
        if engine in (None, ScoringEngine.BEAT_PLANNING):
            results[ScoringEngine.BEAT_PLANNING.value] = await self._beat.snapshot_all()

        logger.info(
            "intelligence_recomputed",
            extra={"engine": engine.value if engine else "ALL", "results": results},
        )
        return results
