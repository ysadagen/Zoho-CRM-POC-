"""Customer-target endpoints — nested under ``/customers/{customer_id}``."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.customer_target import (
    CustomerTargetCreate,
    CustomerTargetRead,
    CustomerTargetUpdate,
)
from app.services.customer_target_service import CustomerTargetService

router = APIRouter(prefix="/customers", tags=["customer-targets"])

_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get(
    "/{customer_id}/targets",
    response_model=list[CustomerTargetRead],
    summary="List a customer's targets",
)
async def list_targets(
    customer_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> list[CustomerTargetRead]:
    """Return a customer's targets (most recent period first). 404 if the
    customer does not exist."""
    targets = await CustomerTargetService(session).list_for_customer(customer_id)
    return [CustomerTargetRead.model_validate(t) for t in targets]


@router.post(
    "/{customer_id}/targets",
    response_model=CustomerTargetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a target for a customer",
)
async def create_target(
    customer_id: uuid.UUID,
    payload: CustomerTargetCreate,
    session: _Session,
    current_user: _CurrentUser,
) -> CustomerTargetRead:
    """Create a target. 404 if the customer is unknown; 422 if
    ``period_end <= period_start``; 409 ``OVERLAPPING_TARGET_PERIOD`` if the
    period overlaps an existing one."""
    target = await CustomerTargetService(session).create(
        customer_id, payload, actor_id=current_user.id
    )
    return CustomerTargetRead.model_validate(target)


@router.patch(
    "/{customer_id}/targets/{target_id}",
    response_model=CustomerTargetRead,
    summary="Update a customer's target",
)
async def update_target(
    customer_id: uuid.UUID,
    target_id: uuid.UUID,
    payload: CustomerTargetUpdate,
    session: _Session,
    current_user: _CurrentUser,
) -> CustomerTargetRead:
    """Apply a partial update. 404 if the target doesn't exist or belongs to
    a different customer; 422 on bad period order; 409 on overlap."""
    target = await CustomerTargetService(session).update(
        customer_id, target_id, payload, actor_id=current_user.id
    )
    return CustomerTargetRead.model_validate(target)
