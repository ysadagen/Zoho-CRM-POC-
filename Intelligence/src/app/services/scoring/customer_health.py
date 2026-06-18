"""Engine 3 — Customer health (§6).

Health = performance (CPS) minus churn risk (CRS), min-max normalized to
0-100. CPS and CRS are each five weighted components.

Layers (per §16):

* :func:`compute_customer_health` — pure: raw metrics → ten component scores →
  CPS/CRS → normalized health + band. Tracks ``defaults_applied``.
* :func:`aggregate_health` — the pure CPS/CRS/normalization step, exposed so
  the canonical vector CH-1 can assert the arithmetic against given component
  scores directly.
* :class:`CustomerHealthService` — the orchestrator: gathers metrics via
  repositories, computes live on read, and (for recompute) snapshots.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.customer import Customer
from app.models.sales_activity import ActivityType
from app.models.score_snapshot import CustomerHealthScore, HealthClassification
from app.models.scoring_config import ScoringEngine
from app.repositories.customer_metrics_repo import CustomerMetricsRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.customer_target_repo import CustomerTargetRepository
from app.repositories.score_snapshot_repo import ScoreSnapshotRepository
from app.services.scoring.config_service import ScoringConfigService

logger = logging.getLogger(__name__)

_COMM_GAP_TYPES = (
    ActivityType.VISIT,
    ActivityType.MEETING,
    ActivityType.CALL,
    ActivityType.FOLLOW_UP,
)
_ENGAGEMENT_TYPES = (ActivityType.VISIT, ActivityType.MEETING)


@dataclass(frozen=True)
class CustomerHealthInputs:
    """Resolved raw metrics for one customer, as of the computation date."""

    competitive_risk_level: str
    visit_meeting_count_90d: int = 0
    complaints_90d: int = 0
    dispatch_current_period: Decimal | None = None
    target_quantity: Decimal | None = None
    dso_days: float | None = None
    revenue_last_90d: Decimal = Decimal(0)
    revenue_prior_90d: Decimal | None = None
    realized_margin_pct: float | None = None
    dispatch_prior_90d: Decimal | None = None
    dispatch_last_30d: Decimal = Decimal(0)
    overdue_outstanding: Decimal = Decimal(0)
    total_outstanding: Decimal = Decimal(0)
    comm_gap_days: int | None = None
    activity_gap_days: int | None = None


@dataclass(frozen=True)
class CustomerHealthResult:
    cps: float
    crs: float
    cps_components: dict[str, int]
    crs_components: dict[str, int]
    weight_profile: str
    health_score: float
    classification: str
    defaults_applied: list[str] = field(default_factory=list)


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


# --- CPS components --------------------------------------------------------


def _volume_achievement(inp: CustomerHealthInputs, params: dict[str, Any]) -> tuple[int, bool]:
    if inp.target_quantity is None or inp.target_quantity == 0:
        return int(params["volume_achievement_default"]), True
    dispatch = inp.dispatch_current_period or Decimal(0)
    pct = float(dispatch) / float(inp.target_quantity) * 100
    return int(min(pct, 100)), False


def _payment_discipline(inp: CustomerHealthInputs, params: dict[str, Any]) -> tuple[int, bool]:
    if inp.dso_days is None:
        return int(params["dso_default"]), True
    return _band_score(inp.dso_days, params["dso_bands"], "max_days"), False


def _engagement(inp: CustomerHealthInputs, params: dict[str, Any]) -> int:
    return _band_score(float(inp.visit_meeting_count_90d), params["engagement_bands"], "min_visits")


def _growth_trend(inp: CustomerHealthInputs, params: dict[str, Any]) -> tuple[int, bool]:
    if not inp.revenue_prior_90d:
        return int(params["growth_default"]), True
    pct = float(inp.revenue_last_90d - inp.revenue_prior_90d) / float(inp.revenue_prior_90d) * 100
    return _band_score(pct, params["growth_bands"], "min_pct"), False


def _margin_quality(inp: CustomerHealthInputs, params: dict[str, Any]) -> tuple[int, bool]:
    if inp.realized_margin_pct is None:
        return int(params["margin_default"]), True
    return _band_score(inp.realized_margin_pct, params["margin_bands"], "min_pct"), False


# --- CRS components --------------------------------------------------------


def _volume_decline(inp: CustomerHealthInputs, params: dict[str, Any]) -> tuple[int, bool]:
    avg_monthly_prior = float(inp.dispatch_prior_90d) / 3 if inp.dispatch_prior_90d else 0.0
    if avg_monthly_prior <= 0:
        return 0, True
    decline_pct = max(
        0.0, (avg_monthly_prior - float(inp.dispatch_last_30d)) / avg_monthly_prior * 100
    )
    return _band_score(decline_pct, params["decline_bands"], "min_pct"), False


def _payment_risk(inp: CustomerHealthInputs, params: dict[str, Any]) -> int:
    if not inp.total_outstanding:
        return 0
    ratio = float(inp.overdue_outstanding) / float(inp.total_outstanding) * 100
    return _band_score(ratio, params["payment_risk_bands"], "min_pct")


def _competitive_risk(inp: CustomerHealthInputs, params: dict[str, Any]) -> int:
    return int(params["competitive_scores"][inp.competitive_risk_level])


def _gap_score(days: int | None, bands: list[dict[str, Any]]) -> int:
    if days is None:  # never → open-ended catch-all
        return int(bands[-1]["score"])
    return _band_score(float(days), bands, "max_days")


def _engagement_gap(inp: CustomerHealthInputs, params: dict[str, Any]) -> int:
    comm = _gap_score(inp.comm_gap_days, params["comm_gap_bands"])
    activity = _gap_score(inp.activity_gap_days, params["activity_gap_bands"])
    weights = params["engagement_gap_weights"]
    return round(float(comm * weights["communication"] + activity * weights["activity"]))


def _service_risk(inp: CustomerHealthInputs, params: dict[str, Any]) -> int:
    return _band_score(float(inp.complaints_90d), params["service_risk_bands"], "min_complaints")


def _classify(health: float, params: dict[str, Any]) -> str:
    bands = params["classification"]
    if health >= bands["healthy_min"]:
        return HealthClassification.HEALTHY.value
    if health >= bands["stable_min"]:
        return HealthClassification.STABLE.value
    if health >= bands["at_risk_min"]:
        return HealthClassification.AT_RISK.value
    return HealthClassification.CRITICAL.value


def aggregate_health(
    cps_components: Mapping[str, float],
    crs_components: Mapping[str, float],
    params: dict[str, Any],
    *,
    profile_name: str | None = None,
) -> tuple[float, float, float, str, str]:
    """Combine the ten component scores → ``(cps, crs, health, classification,
    profile)``. The normalization shift ``+ 100·W_R`` maps raw ∈
    [-100·W_R, +100·W_P] onto [0, 100] exactly because the weights sum to 1."""
    profile = profile_name or params["default_profile"]
    profile_weights = params["weight_profiles"][profile]
    w_p, w_r = profile_weights["w_p"], profile_weights["w_r"]

    cps_w = params["cps_weights"]
    crs_w = params["crs_weights"]
    cps = round(sum(cps_w[k] * cps_components[k] for k in cps_w), 2)
    crs = round(sum(crs_w[k] * crs_components[k] for k in crs_w), 2)

    raw = cps * w_p - crs * w_r
    health = round(raw + 100 * w_r, 2)
    return cps, crs, health, _classify(health, params), profile


def compute_customer_health(
    inp: CustomerHealthInputs, params: dict[str, Any]
) -> CustomerHealthResult:
    """Pure customer-health score from raw metrics + config params (§6)."""
    defaults: list[str] = []

    volume, volume_default = _volume_achievement(inp, params)
    if volume_default:
        defaults.append("volume_achievement")
    dso, dso_default = _payment_discipline(inp, params)
    if dso_default:
        defaults.append("payment_discipline")
    growth, growth_default = _growth_trend(inp, params)
    if growth_default:
        defaults.append("growth_trend")
    margin, margin_default = _margin_quality(inp, params)
    if margin_default:
        defaults.append("margin_quality")
    decline, decline_default = _volume_decline(inp, params)
    if decline_default:
        defaults.append("volume_decline")

    cps_components = {
        "volume_achievement": volume,
        "payment_discipline": dso,
        "engagement": _engagement(inp, params),
        "growth_trend": growth,
        "margin_quality": margin,
    }
    crs_components = {
        "volume_decline": decline,
        "payment_risk": _payment_risk(inp, params),
        "competitive_risk": _competitive_risk(inp, params),
        "engagement_gap": _engagement_gap(inp, params),
        "service_risk": _service_risk(inp, params),
    }

    cps, crs, health, classification, profile = aggregate_health(
        cps_components, crs_components, params
    )
    return CustomerHealthResult(
        cps=cps,
        crs=crs,
        cps_components=cps_components,
        crs_components=crs_components,
        weight_profile=profile,
        health_score=health,
        classification=classification,
        defaults_applied=defaults,
    )


class CustomerHealthService:
    """Orchestrates metric-gathering, live scoring, and snapshot persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._configs = ScoringConfigService(session)
        self._customers = CustomerRepository(session)
        self._targets = CustomerTargetRepository(session)
        self._metrics = CustomerMetricsRepository(session)
        self._snapshots = ScoreSnapshotRepository(session)

    async def compute_for_customer(
        self, customer: Customer, params: dict[str, Any], *, today: date
    ) -> CustomerHealthResult:
        """Gather metrics and compute (no persistence) — used by live GET."""
        inputs = await self._gather_inputs(customer, params, today)
        return compute_customer_health(inputs, params)

    async def _gather_inputs(
        self, customer: Customer, params: dict[str, Any], today: date
    ) -> CustomerHealthInputs:
        cid = customer.id
        engagement_window = int(params["engagement_window_days"])
        dso_window = int(params["dso_window_days"])

        target = await self._targets.target_for_date(cid, today)
        target_quantity = target.target_quantity if target is not None else None
        dispatch_current = (
            await self._metrics.dispatch_in_period(cid, target.period_start, target.period_end)
            if target is not None
            else None
        )

        last_comm = await self._metrics.last_activity_date(cid, _COMM_GAP_TYPES)
        last_shipped = await self._metrics.last_shipped_date(cid)

        return CustomerHealthInputs(
            competitive_risk_level=customer.competitive_risk_level.value,
            visit_meeting_count_90d=await self._metrics.activity_count(
                cid, today - timedelta(days=engagement_window), _ENGAGEMENT_TYPES
            ),
            complaints_90d=await self._metrics.activity_count(
                cid, today - timedelta(days=90), (ActivityType.COMPLAINT,)
            ),
            dispatch_current_period=dispatch_current,
            target_quantity=target_quantity,
            dso_days=await self._metrics.dso_days(
                cid, since=today - timedelta(days=dso_window), as_of=today
            ),
            revenue_last_90d=await self._metrics.revenue_in_period(
                cid, today - timedelta(days=90), today
            ),
            revenue_prior_90d=await self._metrics.revenue_in_period(
                cid, today - timedelta(days=180), today - timedelta(days=90)
            ),
            realized_margin_pct=await self._metrics.realized_margin_pct(
                cid, today - timedelta(days=90), today
            ),
            dispatch_prior_90d=await self._metrics.dispatch_in_period(
                cid, today - timedelta(days=120), today - timedelta(days=30)
            ),
            dispatch_last_30d=await self._metrics.dispatch_in_period(
                cid, today - timedelta(days=30), today
            ),
            overdue_outstanding=(await self._metrics.outstanding_totals(cid, today))[1],
            total_outstanding=(await self._metrics.outstanding_totals(cid, today))[0],
            comm_gap_days=(today - last_comm).days if last_comm is not None else None,
            activity_gap_days=(today - last_shipped).days if last_shipped is not None else None,
        )

    async def list_live(
        self, *, today: date | None = None
    ) -> list[tuple[Customer, CustomerHealthResult]]:
        """Live-compute health for every active customer (§9.4)."""
        as_of = today or date.today()
        _, params = await self._configs.load_active_params(ScoringEngine.CUSTOMER_HEALTH)
        customers = await self._customers.list_all_active()
        results = []
        for customer in customers:
            result = await self.compute_for_customer(customer, params, today=as_of)
            results.append((customer, result))
        return results

    async def get_live(
        self, customer_id: uuid.UUID, *, today: date | None = None
    ) -> tuple[Customer, CustomerHealthResult]:
        as_of = today or date.today()
        customer = await self._customers.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found", code="CUSTOMER_NOT_FOUND")
        _, params = await self._configs.load_active_params(ScoringEngine.CUSTOMER_HEALTH)
        result = await self.compute_for_customer(customer, params, today=as_of)
        return customer, result

    async def snapshot_all(self, *, today: date | None = None) -> int:
        """Compute + persist a snapshot for every active customer (recompute)."""
        as_of = today or date.today()
        config_id, params = await self._configs.load_active_params(ScoringEngine.CUSTOMER_HEALTH)
        customers = await self._customers.list_all_active()
        count = 0
        for customer in customers:
            result = await self.compute_for_customer(customer, params, today=as_of)
            self._session.add(
                CustomerHealthScore(
                    customer_id=customer.id,
                    config_id=config_id,
                    cps=Decimal(str(result.cps)),
                    crs=Decimal(str(result.crs)),
                    components={"cps": result.cps_components, "crs": result.crs_components},
                    weight_profile=result.weight_profile,
                    health_score=Decimal(str(result.health_score)),
                    classification=HealthClassification(result.classification),
                    defaults_applied=result.defaults_applied,
                )
            )
            count += 1
        await self._session.commit()
        logger.info("customer_health_snapshotted", extra={"count": count})
        return count

    async def snapshot_history(self, customer_id: uuid.UUID) -> list[CustomerHealthScore]:
        return await self._snapshots.customer_health_history(customer_id)
