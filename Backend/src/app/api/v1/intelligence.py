"""Intelligence endpoints — score reads, beat plan, config admin, recompute.

All under ``/intelligence``. Read endpoints require any authenticated user;
the administration endpoints (config versioning, recompute) require admin.
This module grows over Phase 2B; 2B.0 wires the scoring-config admin surface
(§9.5).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.dependencies.auth import get_current_user, require_admin
from app.models.score_snapshot import HealthClassification, LeadClassification
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
    ScoringConfigCreate,
    ScoringConfigList,
    ScoringConfigOut,
)
from app.services.scoring.beat_planning import BeatPlanningService
from app.services.scoring.config_service import ScoringConfigService
from app.services.scoring.customer_health import CustomerHealthService
from app.services.scoring.effort_efficiency import EffortEfficiencyService
from app.services.scoring.lead_scoring import LeadScoringService

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]
_AdminUser = Annotated[User, Depends(require_admin)]


@router.get(
    "/lead-scores",
    response_model=LeadScoreList,
    summary="Latest score per active lead",
)
async def list_lead_scores(
    session: _Session,
    current_user: _CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    classification: Annotated[LeadClassification | None, Query()] = None,
    assigned_to_user_id: Annotated[uuid.UUID | None, Query()] = None,
) -> LeadScoreList:
    """Latest score per active lead, highest score first. Filter by
    ``classification`` (HOT/MEDIUM/COLD) and owning rep."""
    rows, total = await LeadScoringService(session).list_latest(
        limit=limit,
        offset=offset,
        classification=classification,
        assigned_to_user_id=assigned_to_user_id,
    )
    return LeadScoreList(
        items=[LeadScoreListItem.from_score_and_lead(score, lead) for score, lead in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/lead-scores/{lead_id}",
    response_model=LeadScoreDetailOut,
    summary="Latest score + history for one lead",
)
async def get_lead_score(
    lead_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> LeadScoreDetailOut:
    """Latest score, its full component breakdown + ``defaults_applied``, and
    the full snapshot history (newest first). 404 if the lead was never
    scored."""
    latest, history = await LeadScoringService(session).get_detail(lead_id)
    base = LeadScoreOut.from_score(latest)
    return LeadScoreDetailOut(
        **base.model_dump(),
        history=[LeadScoreOut.from_score(h) for h in history],
    )


@router.get(
    "/customer-health",
    response_model=CustomerHealthList,
    summary="Live health for all active customers",
)
async def list_customer_health(
    session: _Session,
    current_user: _CurrentUser,
    classification: Annotated[HealthClassification | None, Query()] = None,
) -> CustomerHealthList:
    """Live-compute health for every active customer, lowest health first
    (most at-risk on top). Filter by ``classification``."""
    computed_at = datetime.now(UTC)
    rows = await CustomerHealthService(session).list_live()
    items = [
        CustomerHealthOut.from_result(customer, result, computed_at) for customer, result in rows
    ]
    if classification is not None:
        items = [i for i in items if i.classification == classification]
    items.sort(key=lambda i: i.health_score)
    return CustomerHealthList(items=items, total=len(items))


@router.get(
    "/customer-health/{customer_id}",
    response_model=CustomerHealthDetailOut,
    summary="Live health detail + snapshot trend for one customer",
)
async def get_customer_health(
    customer_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> CustomerHealthDetailOut:
    """Live CPS/CRS breakdown plus the snapshot history (trend). 404 if the
    customer does not exist."""
    service = CustomerHealthService(session)
    customer, result = await service.get_live(customer_id)
    history = await service.snapshot_history(customer_id)
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
