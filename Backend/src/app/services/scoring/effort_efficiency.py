"""Engine 2 — Effort & efficiency (§5).

Effort = input invested; efficiency = output per input. Scored per sales rep
over a period, **cohort-relative** (normalized within all active reps in the
period), so the pure function takes the whole cohort at once.

Layers (per §16):

* :func:`compute_effort_efficiency` — pure: a list of per-rep raw inputs +
  params → a list of per-rep results, with all cohort normalization done
  internally. This is what the canonical vector EE-1 and the cohort-edge tests
  exercise.
* :class:`EffortEfficiencyService` — the orchestrator: gathers per-rep raw
  inputs via repositories, computes live on read, and (for recompute)
  snapshots.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.score_snapshot import EffortEfficiencyScore, EffortQuadrant
from app.models.scoring_config import ScoringEngine
from app.repositories.rep_metrics_repo import RepMetricsRepository
from app.repositories.score_snapshot_repo import ScoreSnapshotRepository
from app.repositories.user_repo import UserRepository
from app.services.scoring.config_service import ScoringConfigService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RepEffortInputs:
    """Raw per-rep measures over the period (pre-normalization)."""

    rep_user_id: uuid.UUID
    rep_email: str
    visits: int = 0
    meetings: int = 0
    follow_ups: int = 0
    calls: int = 0
    hours_logged: float = 0.0
    assigned_leads: int = 0
    leads_progressed: int = 0
    leads_won: int = 0
    won_value_sum: Decimal = Decimal(0)
    avg_time_to_close: float | None = None
    hot_lead_effort_points: float = 0.0
    all_lead_effort_points: float = 0.0


@dataclass(frozen=True)
class RepEffortResult:
    rep_user_id: uuid.UUID
    rep_email: str
    activity_counts: dict[str, float]
    effort_raw: float
    effort_score: float
    efficiency_components: dict[str, float]
    efficiency_score: float
    efficiency_band: str
    quadrant: str


def _effort_raw(rep: RepEffortInputs, params: dict[str, Any]) -> float:
    w = params["activity_weights"]
    return float(
        rep.visits * w["VISIT"]
        + rep.meetings * w["MEETING"]
        + rep.follow_ups * w["FOLLOW_UP"]
        + rep.calls * w["CALL"]
        + rep.hours_logged * params["time_points_per_hour"]
    )


def _band(efficiency: float, params: dict[str, Any]) -> str:
    bands = params["efficiency_bands"]
    if efficiency >= bands["highly_efficient_min"]:
        return "highly efficient"
    if efficiency >= bands["efficient_min"]:
        return "efficient"
    if efficiency >= bands["needs_improvement_min"]:
        return "needs improvement"
    return "inefficient"


def _quadrant(effort: float, efficiency: float, params: dict[str, Any]) -> str:
    thresholds = params["quadrant_thresholds"]
    high_effort = effort >= thresholds["effort"]
    high_efficiency = efficiency >= thresholds["efficiency"]
    if high_effort and high_efficiency:
        return EffortQuadrant.HIGH_EFFORT_HIGH_EFFICIENCY.value
    if high_effort:
        return EffortQuadrant.HIGH_EFFORT_LOW_EFFICIENCY.value
    if high_efficiency:
        return EffortQuadrant.LOW_EFFORT_HIGH_EFFICIENCY.value
    return EffortQuadrant.LOW_EFFORT_LOW_EFFICIENCY.value


def compute_effort_efficiency(
    cohort: list[RepEffortInputs], params: dict[str, Any]
) -> list[RepEffortResult]:
    """Pure cohort-relative effort & efficiency scoring (§5)."""
    raws = [_effort_raw(rep, params) for rep in cohort]
    effort_max = max(raws, default=0.0)

    # Revenue efficiency: won_value per effort point, then normalized.
    rev_raws = [
        (float(rep.won_value_sum) / raw if raw > 0 and rep.leads_won > 0 else 0.0)
        for rep, raw in zip(cohort, raws, strict=True)
    ]
    rev_max = max(rev_raws, default=0.0)

    # Time-to-close: inverted min-max over reps that have closed a deal.
    close_values = [rep.avg_time_to_close for rep in cohort if rep.avg_time_to_close is not None]
    close_min = min(close_values) if close_values else None
    close_max = max(close_values) if close_values else None

    weights = params["efficiency_weights"]
    results: list[RepEffortResult] = []
    for rep, raw, rev_raw in zip(cohort, raws, rev_raws, strict=True):
        effort_score = round(raw / effort_max * 100, 2) if effort_max > 0 else 0.0

        stage_change = (
            round(rep.leads_progressed / rep.assigned_leads * 100, 2)
            if rep.assigned_leads > 0
            else 0.0
        )
        won_rate = (
            round(rep.leads_won / rep.assigned_leads * 100, 2) if rep.assigned_leads > 0 else 0.0
        )
        revenue_efficiency = round(rev_raw / rev_max * 100, 2) if rev_max > 0 else 0.0
        if rep.avg_time_to_close is None or close_min is None or close_max is None:
            time_to_close = 0.0
        elif close_max == close_min:
            time_to_close = 100.0
        else:
            time_to_close = round(
                (close_max - rep.avg_time_to_close) / (close_max - close_min) * 100, 2
            )
        utilization = (
            round(rep.hot_lead_effort_points / rep.all_lead_effort_points * 100, 2)
            if rep.all_lead_effort_points > 0
            else 0.0
        )

        components = {
            "stage_change_rate": stage_change,
            "won_rate": won_rate,
            "revenue_efficiency": revenue_efficiency,
            "time_to_close": time_to_close,
            "lead_score_utilization": utilization,
        }
        efficiency = round(sum(weights[k] * components[k] for k in weights), 2)

        results.append(
            RepEffortResult(
                rep_user_id=rep.rep_user_id,
                rep_email=rep.rep_email,
                activity_counts={
                    "visits": rep.visits,
                    "meetings": rep.meetings,
                    "follow_ups": rep.follow_ups,
                    "calls": rep.calls,
                    "hours_logged": round(rep.hours_logged, 2),
                },
                effort_raw=round(raw, 4),
                effort_score=effort_score,
                efficiency_components=components,
                efficiency_score=efficiency,
                efficiency_band=_band(efficiency, params),
                quadrant=_quadrant(effort_score, efficiency, params),
            )
        )
    return results


class EffortEfficiencyService:
    """Orchestrates per-rep gathering, cohort scoring, and snapshot persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._configs = ScoringConfigService(session)
        self._users = UserRepository(session)
        self._metrics = RepMetricsRepository(session)
        self._snapshots = ScoreSnapshotRepository(session)

    def _default_period(self, params: dict[str, Any]) -> tuple[date, date]:
        end = date.today()
        start = end - timedelta(days=int(params["period_days_default"]))
        return start, end

    async def _gather_cohort(
        self, params: dict[str, Any], start: date, end: date
    ) -> list[RepEffortInputs]:
        reps = await self._users.list_active()
        cohort: list[RepEffortInputs] = []
        for rep in reps:
            counts = await self._metrics.effort_counts(rep.id, start, end)
            leads = await self._metrics.lead_outcome_counts(rep.id, start, end)
            hot_points, all_points = await self._metrics.lead_effort_points(
                rep.id,
                start,
                end,
                activity_weights=params["activity_weights"],
                time_points_per_hour=params["time_points_per_hour"],
            )
            cohort.append(
                RepEffortInputs(
                    rep_user_id=rep.id,
                    rep_email=rep.email,
                    visits=counts["visits"],
                    meetings=counts["meetings"],
                    follow_ups=counts["follow_ups"],
                    calls=counts["calls"],
                    hours_logged=counts["hours_logged"],
                    assigned_leads=leads["assigned"],
                    leads_progressed=leads["progressed"],
                    leads_won=leads["won"],
                    won_value_sum=leads["won_value_sum"],
                    avg_time_to_close=leads["avg_time_to_close"],
                    hot_lead_effort_points=hot_points,
                    all_lead_effort_points=all_points,
                )
            )
        return cohort

    async def compute_cohort(
        self, *, period_start: date | None = None, period_end: date | None = None
    ) -> tuple[list[RepEffortResult], date, date]:
        """Live cohort table (§9.4)."""
        _, params = await self._configs.load_active_params(ScoringEngine.EFFORT_EFFICIENCY)
        if period_start is None or period_end is None:
            start, end = self._default_period(params)
        else:
            start, end = period_start, period_end
        cohort = await self._gather_cohort(params, start, end)
        return compute_effort_efficiency(cohort, params), start, end

    async def snapshot_all(
        self, *, period_start: date | None = None, period_end: date | None = None
    ) -> int:
        config_id, params = await self._configs.load_active_params(ScoringEngine.EFFORT_EFFICIENCY)
        if period_start is None or period_end is None:
            start, end = self._default_period(params)
        else:
            start, end = period_start, period_end
        cohort = await self._gather_cohort(params, start, end)
        results = compute_effort_efficiency(cohort, params)
        for result in results:
            self._session.add(
                EffortEfficiencyScore(
                    rep_user_id=result.rep_user_id,
                    config_id=config_id,
                    period_start=start,
                    period_end=end,
                    effort_raw=Decimal(str(result.effort_raw)),
                    effort_score=Decimal(str(result.effort_score)),
                    efficiency_components=result.efficiency_components,
                    efficiency_score=Decimal(str(result.efficiency_score)),
                    quadrant=EffortQuadrant(result.quadrant),
                )
            )
        await self._session.commit()
        logger.info("effort_efficiency_snapshotted", extra={"count": len(results)})
        return len(results)

    async def snapshot_history(self, rep_user_id: uuid.UUID) -> list[EffortEfficiencyScore]:
        return await self._snapshots.effort_efficiency_history(rep_user_id)
