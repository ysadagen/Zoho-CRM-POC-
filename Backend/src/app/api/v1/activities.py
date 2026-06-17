"""Sales-activity endpoints — append-only (create + list only).

There is deliberately **no PATCH or DELETE**: activities are immutable
facts. A correction is recorded as a new activity (same rule as stock
adjustments).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.sales_activity import ActivityType
from app.models.user import User
from app.schemas.sales_activity import ActivityCreate, ActivityList, ActivityRead
from app.services.sales_activity_service import SalesActivityService

router = APIRouter(prefix="/activities", tags=["activities"])

_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "",
    response_model=ActivityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a sales activity",
)
async def create_activity(
    payload: ActivityCreate,
    session: _Session,
    current_user: _CurrentUser,
) -> ActivityRead:
    """Record an activity. ``rep_user_id`` defaults to the caller when
    omitted. Returns 422 ``SUBJECT_REQUIRED`` if neither a customer nor a
    lead is referenced, and 404 if any referenced entity does not exist.
    """
    activity = await SalesActivityService(session).create(payload, actor_id=current_user.id)
    return ActivityRead.model_validate(activity)


@router.get(
    "",
    response_model=ActivityList,
    summary="List sales activities with pagination and filters",
)
async def list_activities(
    session: _Session,
    current_user: _CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    type: Annotated[ActivityType | None, Query()] = None,
    rep_user_id: Annotated[uuid.UUID | None, Query()] = None,
    customer_id: Annotated[uuid.UUID | None, Query()] = None,
    lead_id: Annotated[uuid.UUID | None, Query()] = None,
    occurred_from: Annotated[datetime | None, Query()] = None,
    occurred_to: Annotated[datetime | None, Query()] = None,
) -> ActivityList:
    """Return a page of activities, most recent first. Filters compose:
    ``type``, ``rep_user_id``, ``customer_id``, ``lead_id``, and an
    ``occurred_from``/``occurred_to`` window."""
    activities, total = await SalesActivityService(session).list_(
        limit=limit,
        offset=offset,
        type_=type,
        rep_user_id=rep_user_id,
        customer_id=customer_id,
        lead_id=lead_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )
    return ActivityList(
        items=[ActivityRead.model_validate(a) for a in activities],
        total=total,
        limit=limit,
        offset=offset,
    )
