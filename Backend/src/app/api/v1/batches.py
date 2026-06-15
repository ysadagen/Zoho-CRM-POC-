"""Batch (lot) endpoints.

- ``POST /api/v1/batches`` — record an opening-balance lot for existing
  item stock (no net stock change; see :class:`BatchService`).
- ``GET /api/v1/batches`` — list lots, filterable by item / status / expiry.
- ``GET /api/v1/batches/{id}`` — one lot.

New stock entering inventory is the PO-receive flow (Phase 1C), not a
direct write here.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.batch import BatchStatus
from app.models.user import User
from app.schemas.batch import BatchCreate, BatchList, BatchRead, BatchStatusChange
from app.services.batch_service import BatchService

router = APIRouter(prefix="/batches", tags=["batches"])

_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "",
    response_model=BatchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a stock lot (opening balance)",
)
async def create_batch(
    payload: BatchCreate,
    session: _Session,
    current_user: _CurrentUser,
) -> BatchRead:
    """Record a lot for existing item stock.

    Does not change ``items.stock_quantity`` — it associates stock the item
    already has with a lot. Returns ``404 ITEM_NOT_FOUND`` for an unknown
    item, ``409 DUPLICATE_BATCH`` for a repeated ``(item, batch_number)``,
    and ``409 BATCH_EXCEEDS_UNBATCHED_STOCK`` if the quantity exceeds the
    item's unbatched remainder.
    """
    batch = await BatchService(session).create(payload, actor_id=current_user.id)
    return BatchRead.model_validate(batch)


@router.get(
    "",
    response_model=BatchList,
    summary="List lots (paginated, filterable)",
)
async def list_batches(
    session: _Session,
    current_user: _CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    item_id: Annotated[uuid.UUID | None, Query()] = None,
    status_filter: Annotated[BatchStatus | None, Query(alias="status")] = None,
    expiring_before: Annotated[date | None, Query()] = None,
) -> BatchList:
    """List lots, soonest expiry first.

    Filters compose: ``item_id``, ``status``, and ``expiring_before``
    (lots with ``expiry_date <= expiring_before`` — drives expiry reports).
    """
    batches, total = await BatchService(session).list_(
        limit=limit,
        offset=offset,
        item_id=item_id,
        status=status_filter,
        expiring_before=expiring_before,
    )
    return BatchList(
        items=[BatchRead.model_validate(b) for b in batches],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{batch_id}",
    response_model=BatchRead,
    summary="Return a lot by id",
)
async def get_batch(
    batch_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> BatchRead:
    """Return one lot. Returns ``404 BATCH_NOT_FOUND`` if the id is unknown."""
    return BatchRead.model_validate(await BatchService(session).get(batch_id))


@router.post(
    "/{batch_id}/status",
    response_model=BatchRead,
    summary="Change a lot's QC status (release / reject / recall)",
)
async def change_batch_status(
    batch_id: uuid.UUID,
    payload: BatchStatusChange,
    session: _Session,
    current_user: _CurrentUser,
) -> BatchRead:
    """Transition a lot's QC status.

    Legal moves: QUARANTINE → RELEASED / REJECTED, RELEASED → RECALLED.
    Returns ``404 BATCH_NOT_FOUND`` for an unknown lot, ``409
    INVALID_BATCH_TRANSITION`` for an illegal move. REJECTED / RECALLED lots
    stop being shippable.
    """
    batch = await BatchService(session).change_status(
        batch_id, payload.status, actor_id=current_user.id
    )
    return BatchRead.model_validate(batch)
