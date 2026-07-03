"""Intelligence endpoints — score reads, beat plan, config admin, recompute.

All under ``/intelligence``. Read endpoints require any authenticated user;
the administration endpoints (config versioning, recompute) require admin.
This module grows over Phase 2B; 2B.0 wires the scoring-config admin surface
(§9.5).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_session_factory
from app.core.exceptions import NotFoundError
from app.dependencies.auth import get_current_user, require_admin
from app.models.score_snapshot import CustomerHealthScore, HealthClassification, LeadClassification
from app.models.scoring_config import ScoringEngine
from app.models.user import User
from app.schemas.intelligence import (
    BeatPlanOut,
    CustomerHealthDetailOut,
    CustomerHealthList,
    CustomerHealthOut,
    EffortEfficiencyDetailOut,
    EffortEfficiencyList,
    EffortEfficiencyOut,
    LeadScoreDetailOut,
    LeadScoreList,
    LeadScoreListItem,
    LeadScoreOut,
    RecomputeOut,
    RecomputeRequest,
    ScoringConfigCreate,
    ScoringConfigList,
    ScoringConfigOut,
)
from app.services.scoring.beat_planning import BeatPlanningService
from app.services.scoring.config_service import ScoringConfigService
from app.services.scoring.customer_health import CustomerHealthResult, CustomerHealthService
from app.services.scoring.effort_efficiency import EffortEfficiencyService
from app.services.scoring.lead_scoring import LeadScoringService
from app.services.scoring.recompute_service import RecomputeService

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

logger = logging.getLogger(__name__)

# Snapshots older than this trigger a background recompute on the next list request.
_HEALTH_STALE_HOURS = 8

# One lock per process — prevents concurrent background full-recomputes.
_bg_health_recompute_lock: asyncio.Lock = asyncio.Lock()


async def _bg_full_health_recompute() -> None:
    """Recompute all customer health snapshots asynchronously (stale-while-revalidate)."""
    if _bg_health_recompute_lock.locked():
        return
    async with _bg_health_recompute_lock:
        async with get_session_factory()() as session:
            try:
                await CustomerHealthService(session).snapshot_all()
            except Exception:
                await session.rollback()
                logger.exception("customer_health.bg_recompute.failed")


async def _bg_save_health_snapshot(
    customer_id: uuid.UUID,
    result: CustomerHealthResult,
    config_id: uuid.UUID,
) -> None:
    """Persist a live-computed health score as a snapshot (write-on-read)."""
    async with get_session_factory()() as session:
        try:
            session.add(
                CustomerHealthScore(
                    customer_id=customer_id,
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
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(
                "customer_health.bg_save_snapshot.failed",
                extra={"customer_id": str(customer_id)},
            )

_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]
_AdminUser = Annotated[User, Depends(require_admin)]


@router.get(
    "/lead-scores",
    response_model=LeadScoreList,
    summary="Live score per active lead",
)
async def list_lead_scores(
    session: _Session,
    current_user: _CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    classification: Annotated[LeadClassification | None, Query()] = None,
    assigned_to_user_id: Annotated[uuid.UUID | None, Query()] = None,
) -> LeadScoreList:
    """Live-scored leads, highest score first. Filter by ``classification``
    (HOT/MEDIUM/COLD) and owning rep."""
    computed_at = datetime.now(UTC)
    rows, total, version = await LeadScoringService(session).list_live(
        limit=limit,
        offset=offset,
        classification=classification,
        assigned_to_user_id=assigned_to_user_id,
    )
    return LeadScoreList(
        items=[
            LeadScoreListItem.from_result_and_lead(lead, version, computed_at, result)
            for lead, result in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/lead-scores/{lead_id}",
    response_model=LeadScoreDetailOut,
    summary="Live score + snapshot history for one lead",
)
async def get_lead_score(
    lead_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> LeadScoreDetailOut:
    """Live score with full component breakdown + ``defaults_applied``, plus
    the snapshot history (newest first). 404 if the lead is unknown."""
    computed_at = datetime.now(UTC)
    lead, result, version, history = await LeadScoringService(session).get_live(lead_id)
    base = LeadScoreOut.from_result(lead.id, version, computed_at, result)
    return LeadScoreDetailOut(
        **base.model_dump(),
        history=[LeadScoreOut.from_score(h) for h in history],
    )


@router.get(
    "/customer-health",
    response_model=CustomerHealthList,
    summary="Latest health snapshot per active customer, paginated",
)
async def list_customer_health(
    background_tasks: BackgroundTasks,
    session: _Session,
    current_user: _CurrentUser,
    classification: Annotated[HealthClassification | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CustomerHealthList:
    """Latest persisted health snapshot per active customer (lowest score first).

    Triggers a background recompute when snapshots are absent or older than
    8 hours (stale-while-revalidate), so the table self-populates without a
    scheduler. Filter by ``classification``; paginate with ``limit``/``offset``."""
    service = CustomerHealthService(session)
    rows, total = await service.list_from_snapshots(
        limit=limit,
        offset=offset,
        classification=classification,
    )
    last_at = await service.last_computed_at()
    if last_at is None or (datetime.now(UTC) - last_at) > timedelta(hours=_HEALTH_STALE_HOURS):
        background_tasks.add_task(_bg_full_health_recompute)
    return CustomerHealthList(
        items=[CustomerHealthOut.from_snapshot(score, customer) for score, customer in rows],
        total=total,
        limit=limit,
        offset=offset,
        last_computed_at=last_at,
    )


@router.get(
    "/customer-health/{customer_id}",
    response_model=CustomerHealthDetailOut,
    summary="Live health detail + snapshot trend for one customer",
)
async def get_customer_health(
    customer_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: _Session,
    current_user: _CurrentUser,
) -> CustomerHealthDetailOut:
    """Live CPS/CRS breakdown plus the snapshot history (trend). 404 if the
    customer does not exist. Persists this live result as a snapshot in the
    background (write-on-read), keeping the list view fresh without a scheduler."""
    service = CustomerHealthService(session)
    customer, result, config_id = await service.get_live(customer_id)
    history = await service.snapshot_history(customer_id)
    background_tasks.add_task(_bg_save_health_snapshot, customer.id, result, config_id)
    return CustomerHealthDetailOut.from_result_and_history(
        customer, result, datetime.now(UTC), history
    )


@router.get(
    "/effort-efficiency",
    response_model=EffortEfficiencyList,
    summary="Live effort & efficiency per rep for a period",
)
async def list_effort_efficiency(
    session: _Session,
    current_user: _CurrentUser,
    period_start: Annotated[date | None, Query()] = None,
    period_end: Annotated[date | None, Query()] = None,
) -> EffortEfficiencyList:
    """Live cohort table — per-rep effort, efficiency, components, and
    quadrant. Defaults to the trailing 90 days; pass an explicit
    ``period_start``/``period_end`` to override. Highest effort first."""
    results, start, end = await EffortEfficiencyService(session).compute_cohort(
        period_start=period_start, period_end=period_end
    )
    items = [EffortEfficiencyOut.from_result(r, start, end) for r in results]
    items.sort(key=lambda i: i.effort_score, reverse=True)
    return EffortEfficiencyList(items=items, total=len(items), period_start=start, period_end=end)


@router.get(
    "/effort-efficiency/{user_id}",
    response_model=EffortEfficiencyDetailOut,
    summary="Live effort & efficiency detail + trend for one rep",
)
async def get_effort_efficiency(
    user_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
    period_start: Annotated[date | None, Query()] = None,
    period_end: Annotated[date | None, Query()] = None,
) -> EffortEfficiencyDetailOut:
    """Live effort & efficiency for one rep (computed within the full cohort so
    normalization is correct) plus the snapshot history. 404 if the user is
    not an active rep."""
    service = EffortEfficiencyService(session)
    results, start, end = await service.compute_cohort(
        period_start=period_start, period_end=period_end
    )
    match = next((r for r in results if r.rep_user_id == user_id), None)
    if match is None:
        raise NotFoundError("No effort score for this user", code="EFFORT_SCORE_NOT_FOUND")
    history = await service.snapshot_history(user_id)
    return EffortEfficiencyDetailOut.from_result_and_history(match, start, end, history)


@router.get(
    "/beat-plan",
    response_model=BeatPlanOut,
    summary="Suggested beat + visit-priority ranking for a rep",
)
async def get_beat_plan(
    session: _Session,
    current_user: _CurrentUser,
    rep_user_id: Annotated[uuid.UUID, Query()],
    max_visits: Annotated[int | None, Query(ge=1, le=50)] = None,
) -> BeatPlanOut:
    """Rank the rep's handled customers by Visit Priority Score, cluster by
    district, and suggest a day's beat (top ``max_visits``, default from the
    config). 404 if the rep is unknown."""
    plan, resolved_max = await BeatPlanningService(session).compute_for_rep(
        rep_user_id, max_visits=max_visits
    )
    return BeatPlanOut.from_result(rep_user_id, plan, resolved_max, datetime.now(UTC))


@router.get(
    "/configs",
    response_model=ScoringConfigList,
    summary="List scoring-config versions (admin)",
)
async def list_configs(
    session: _Session,
    current_user: _AdminUser,
    engine: Annotated[ScoringEngine | None, Query()] = None,
) -> ScoringConfigList:
    """List config versions (active flagged). Filter by ``engine``."""
    configs = await ScoringConfigService(session).list_configs(engine=engine)
    return ScoringConfigList(
        items=[ScoringConfigOut.model_validate(c) for c in configs],
        total=len(configs),
    )


@router.post(
    "/configs",
    response_model=ScoringConfigOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create + activate a new scoring-config version (admin)",
)
async def create_config(
    payload: ScoringConfigCreate,
    session: _Session,
    current_user: _AdminUser,
) -> ScoringConfigOut:
    """Create a new version for an engine and activate it (deactivating the
    prior active row). ``params`` is validated against the engine's schema —
    422 ``INVALID_CONFIG_PARAMS`` on violation (weights must sum to 1, bands
    contiguous, no unknown keys)."""
    config = await ScoringConfigService(session).create_and_activate(
        payload.engine,
        payload.params,
        description=payload.description,
        actor_id=current_user.id,
    )
    return ScoringConfigOut.model_validate(config)


@router.post(
    "/recompute",
    response_model=RecomputeOut,
    summary="Recompute + snapshot scores for one or all engines (admin)",
)
async def recompute(
    payload: RecomputeRequest,
    session: _Session,
    current_user: _AdminUser,
) -> RecomputeOut:
    """Synchronously recompute and snapshot every active entity for the given
    ``engine`` (or all four when null). Returns per-engine counts and the
    run's wall-clock duration. Intended for a nightly scheduled call."""
    started = time.perf_counter()
    results = await RecomputeService(session).recompute(payload.engine)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    return RecomputeOut(results=results, duration_ms=duration_ms)
