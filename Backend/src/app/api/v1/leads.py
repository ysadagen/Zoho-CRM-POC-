"""Leads endpoints — CRUD plus the stage-transition action.

Stage is changed **only** via ``POST /leads/{id}/transition`` — ``PATCH``
deliberately cannot touch it, so the state machine and the append-only
history trail can't be bypassed. Every read carries the lead's latest score
(``latest_score`` summary; the detail view adds the full breakdown).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.lead import Lead, LeadSource, LeadStage
from app.models.score_snapshot import LeadScore
from app.models.user import User
from app.schemas.intelligence import LeadScoreOut
from app.schemas.lead import (
    LeadCreate,
    LeadDetailRead,
    LeadList,
    LeadRead,
    LeadScoreSummary,
    LeadStageHistoryRead,
    LeadUpdate,
    StageTransitionRequest,
)
from app.services.lead_service import LeadService

router = APIRouter(prefix="/leads", tags=["leads"])

_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]


def _summary(score: LeadScore | None) -> LeadScoreSummary | None:
    if score is None:
        return None
    return LeadScoreSummary(
        total_score=float(score.total_score),
        classification=score.classification,
        computed_at=score.computed_at,
    )


def _read_with_score(lead: Lead, score: LeadScore | None) -> LeadRead:
    read = LeadRead.model_validate(lead)
    read.latest_score = _summary(score)
    return read


@router.post(
    "",
    response_model=LeadRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new lead",
)
async def create_lead(
    payload: LeadCreate,
    session: _Session,
    current_user: _CurrentUser,
) -> LeadRead:
    """Create a lead (always at stage NEW), record its creation in the stage
    history, and compute its initial score. Returns 404 if the assigned user,
    customer, or item does not exist."""
    service = LeadService(session)
    lead = await service.create(payload, actor_id=current_user.id)
    return _read_with_score(lead, await service.latest_score(lead.id))


@router.get(
    "",
    response_model=LeadList,
    summary="List leads with pagination and filters",
)
async def list_leads(
    session: _Session,
    current_user: _CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    stage: Annotated[LeadStage | None, Query()] = None,
    source: Annotated[LeadSource | None, Query()] = None,
    assigned_to_user_id: Annotated[uuid.UUID | None, Query()] = None,
    state: Annotated[str | None, Query(max_length=120)] = None,
    district: Annotated[str | None, Query(max_length=120)] = None,
    created_from: Annotated[date | None, Query()] = None,
    created_to: Annotated[date | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> LeadList:
    """Return a page of leads, newest first, each with its latest score.

    Filters compose: ``stage``, ``source``, ``assigned_to_user_id``,
    ``state``, ``district``, a ``created_from``/``created_to`` date window,
    and ``is_active``. (Filtering by lead *classification* lives on
    ``GET /intelligence/lead-scores``.)
    """
    service = LeadService(session)
    leads, total = await service.list_(
        limit=limit,
        offset=offset,
        stage=stage,
        source=source,
        assigned_to_user_id=assigned_to_user_id,
        state=state,
        district=district,
        created_from=created_from,
        created_to=created_to,
        is_active=is_active,
    )
    scores = await service.latest_scores_map([lead.id for lead in leads])
    return LeadList(
        items=[_read_with_score(lead, scores.get(lead.id)) for lead in leads],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{lead_id}",
    response_model=LeadDetailRead,
    summary="Return a lead by id with its stage history and score",
)
async def get_lead(
    lead_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> LeadDetailRead:
    """Return one lead, its full stage history (newest first), and the latest
    score (summary + full component breakdown). 404 if the id does not exist."""
    service = LeadService(session)
    lead, history = await service.get_with_history(lead_id)
    score = await service.latest_score(lead_id)
    base = _read_with_score(lead, score)
    return LeadDetailRead(
        **base.model_dump(),
        stage_history=[LeadStageHistoryRead.model_validate(h) for h in history],
        score=LeadScoreOut.from_score(score) if score is not None else None,
    )


@router.patch(
    "/{lead_id}",
    response_model=LeadRead,
    summary="Partially update a lead (not its stage)",
)
async def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    session: _Session,
    current_user: _CurrentUser,
) -> LeadRead:
    """Apply a partial update. ``stage`` is not a field — use the transition
    endpoint. Recomputes the score if a scoring input changed. 404 if the lead
    or any referenced entity does not exist."""
    service = LeadService(session)
    lead = await service.update(lead_id, payload, actor_id=current_user.id)
    return _read_with_score(lead, await service.latest_score(lead.id))


@router.post(
    "/{lead_id}/transition",
    response_model=LeadRead,
    summary="Move a lead to a new stage",
)
async def transition_lead(
    lead_id: uuid.UUID,
    payload: StageTransitionRequest,
    session: _Session,
    current_user: _CurrentUser,
) -> LeadRead:
    """Transition a lead's stage along the legal state machine, then recompute
    its score.

    Returns 409 ``INVALID_STAGE_TRANSITION`` if the move isn't allowed,
    422 if WON is missing ``won_value`` or LOST is missing ``lost_reason``.
    """
    service = LeadService(session)
    lead = await service.transition(lead_id, payload, actor_id=current_user.id)
    return _read_with_score(lead, await service.latest_score(lead.id))


@router.delete(
    "/{lead_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a lead (soft-delete)",
)
async def deactivate_lead(
    lead_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> None:
    """Soft-delete a lead (``is_active = false``). Idempotent; 404 if the id
    does not exist. History is preserved."""
    await LeadService(session).soft_delete(lead_id, actor_id=current_user.id)
