"""Engine 4 — Beat planning & visit prioritization (§7).

For a given rep: rank their handled customers by Visit Priority Score (VPS),
cluster by district, and suggest a day's beat within visit capacity.

Layers (per §16):

* :func:`compute_beat_plan` — pure: a list of per-customer raw inputs + params
  + ``max_visits`` → the ranked list, district clusters, and the suggested
  beat. Canonical vector BP-1 exercises this.
* :class:`BeatPlanningService` — the orchestrator: resolves the rep's handled
  customers, gathers per-customer metrics, computes live on read, and (for
  recompute) snapshots.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.sales_activity import ActivityType
from app.models.score_snapshot import VisitPriority, VisitPriorityScore
from app.models.scoring_config import ScoringEngine
from app.repositories.customer_metrics_repo import CustomerMetricsRepository
from app.repositories.user_repo import UserRepository
from app.services.scoring.config_service import ScoringConfigService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BeatCustomerInput:
    """Resolved per-customer measures for one rep's beat."""

    customer_id: uuid.UUID
    company_name: str
    district: str | None
    customer_type: str
    revenue_90d: Decimal
    days_since_last_visit: int | None


@dataclass(frozen=True)
class BeatCustomerResult:
    customer_id: uuid.UUID
    company_name: str
    district: str | None
    customer_type: str
    revenue_score: int
    visit_gap_score: int
    customer_type_score: int
    location_density_score: int
    vps: float
    priority: str
    days_since_last_visit: int | None
    revenue_90d: Decimal


@dataclass(frozen=True)
class BeatCluster:
    district: str
    customer_count: int
    lds: float
    cluster_opportunity: bool


@dataclass(frozen=True)
class BeatPlanResult:
    clusters: list[BeatCluster]
    suggested_beat: list[BeatCustomerResult]
    all_customers: list[BeatCustomerResult]


def _band_score(value: float, bands: list[dict[str, Any]], threshold_key: str) -> int:
    ascending = threshold_key.startswith("max")
    for band in bands:
        threshold = band[threshold_key]
        if threshold is None:
            return int(band["score"])
        if ascending and value <= threshold:
            return int(band["score"])
        if not ascending and value >= threshold:
            return int(band["score"])
    return int(bands[-1]["score"])


def _visit_gap_score(days: int | None, params: dict[str, Any]) -> int:
    if days is None:  # never visited → max priority gap
        return int(params["visit_gap_bands"][-1]["score"])
    return _band_score(float(days), params["visit_gap_bands"], "max_days")


def _priority(vps: float, params: dict[str, Any]) -> str:
    bands = params["priority_bands"]
    if vps >= bands["critical_min"]:
        return VisitPriority.CRITICAL.value
    if vps >= bands["high_min"]:
        return VisitPriority.HIGH.value
    if vps >= bands["medium_min"]:
        return VisitPriority.MEDIUM.value
    return VisitPriority.LOW.value


def compute_beat_plan(
    customers: list[BeatCustomerInput], params: dict[str, Any], *, max_visits: int
) -> BeatPlanResult:
    """Pure beat plan: rank by VPS, cluster by district, suggest a beat (§7)."""
    weights = params["weights"]
    type_scores = params["customer_type_scores"]
    total_handled = len(customers)
    district_counts: Counter[str] = Counter(c.district for c in customers if c.district is not None)
    revenue_max = max((c.revenue_90d for c in customers), default=Decimal(0))

    results: list[BeatCustomerResult] = []
    for c in customers:
        revenue_score = (
            round(float(c.revenue_90d) / float(revenue_max) * 100) if revenue_max > 0 else 0
        )
        visit_gap_score = _visit_gap_score(c.days_since_last_visit, params)
        customer_type_score = int(type_scores[c.customer_type])
        lds = (
            district_counts[c.district] / total_handled
            if c.district is not None and total_handled > 0
            else 0.0
        )
        location_density_score = round(lds * 100)

        vps = round(
            weights["revenue"] * revenue_score
            + weights["visit_gap"] * visit_gap_score
            + weights["customer_type"] * customer_type_score
            + weights["location_density"] * location_density_score,
            2,
        )
        results.append(
            BeatCustomerResult(
                customer_id=c.customer_id,
                company_name=c.company_name,
                district=c.district,
                customer_type=c.customer_type,
                revenue_score=revenue_score,
                visit_gap_score=visit_gap_score,
                customer_type_score=customer_type_score,
                location_density_score=location_density_score,
                vps=vps,
                priority=_priority(vps, params),
                days_since_last_visit=c.days_since_last_visit,
                revenue_90d=c.revenue_90d,
            )
        )

    threshold = params["cluster_lds_threshold"]
    clusters = [
        BeatCluster(
            district=district,
            customer_count=count,
            lds=round(count / total_handled, 4) if total_handled > 0 else 0.0,
            cluster_opportunity=(count / total_handled if total_handled else 0) > threshold,
        )
        for district, count in district_counts.most_common()
    ]

    # Rank by VPS desc; tie-break prefers customers in denser clusters
    # (more same-cluster visits per trip), then by name for determinism.
    ranked = sorted(
        results,
        key=lambda r: (
            -r.vps,
            -(district_counts[r.district] if r.district is not None else 0),
            r.company_name,
        ),
    )
    return BeatPlanResult(
        clusters=clusters,
        suggested_beat=ranked[:max_visits],
        all_customers=ranked,
    )


class BeatPlanningService:
    """Orchestrates handled-customer resolution, scoring, and snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._configs = ScoringConfigService(session)
        self._users = UserRepository(session)
        self._metrics = CustomerMetricsRepository(session)

    async def _gather(
        self, rep_user_id: uuid.UUID, params: dict[str, Any], today: date
    ) -> list[BeatCustomerInput]:
        handled_window = int(params["handled_window_days"])
        revenue_window = int(params["revenue_window_days"])
        since = today - timedelta(days=handled_window)
        customers = await self._metrics.handled_customers(rep_user_id, since)
        if not customers:
            return []
        # Two queries for the whole customer list instead of 2 × N per-customer queries.
        customer_ids = [c.id for c in customers]
        revenue_by_cid = await self._metrics.revenue_in_period_bulk(
            customer_ids, today - timedelta(days=revenue_window), today
        )
        last_visit_by_cid = await self._metrics.last_activity_date_bulk(
            customer_ids, (ActivityType.VISIT,)
        )
        return [
            BeatCustomerInput(
                customer_id=customer.id,
                company_name=customer.company_name,
                district=customer.district,
                customer_type=customer.customer_type.value,
                revenue_90d=revenue_by_cid[customer.id],
                days_since_last_visit=(
                    (today - last_visit_by_cid[customer.id]).days
                    if last_visit_by_cid[customer.id] is not None
                    else None
                ),
            )
            for customer in customers
        ]

    async def compute_for_rep(
        self, rep_user_id: uuid.UUID, *, max_visits: int | None = None, today: date | None = None
    ) -> tuple[BeatPlanResult, int]:
        """Live beat plan for a rep (§7.2). 404 if the user is unknown."""
        as_of = today or date.today()
        if await self._users.get_by_id(rep_user_id) is None:
            raise NotFoundError("User not found", code="USER_NOT_FOUND")
        _, params = await self._configs.load_active_params(ScoringEngine.BEAT_PLANNING)
        resolved_max = max_visits if max_visits is not None else int(params["default_max_visits"])
        inputs = await self._gather(rep_user_id, params, as_of)
        return compute_beat_plan(inputs, params, max_visits=resolved_max), resolved_max

    async def snapshot_all(self, *, today: date | None = None) -> int:
        """Compute + persist VPS snapshots for every rep's handled customers."""
        as_of = today or date.today()
        config_id, params = await self._configs.load_active_params(ScoringEngine.BEAT_PLANNING)
        max_visits = int(params["default_max_visits"])
        reps = await self._users.list_active()
        count = 0
        for rep in reps:
            inputs = await self._gather(rep.id, params, as_of)
            plan = compute_beat_plan(inputs, params, max_visits=max_visits)
            for c in plan.all_customers:
                self._session.add(
                    VisitPriorityScore(
                        customer_id=c.customer_id,
                        rep_user_id=rep.id,
                        config_id=config_id,
                        revenue_score=c.revenue_score,
                        visit_gap_score=c.visit_gap_score,
                        customer_type_score=c.customer_type_score,
                        location_density_score=c.location_density_score,
                        vps=Decimal(str(c.vps)),
                        priority=VisitPriority(c.priority),
                    )
                )
                count += 1
        await self._session.commit()
        logger.info("beat_planning_snapshotted", extra={"count": count})
        return count
