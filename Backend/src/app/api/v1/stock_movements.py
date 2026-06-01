"""Stock-movement endpoints — the append-only ledger.

Deliberately exposes **only two routes**:

- ``GET /api/v1/stock-movements`` — read the ledger with filters.
- ``POST /api/v1/stock-movements/adjustments`` — record a manual
  adjustment (the only direct write path). PURCHASE and SALE
  movements arrive internally via Phase 7/8 services calling
  ``StockMovementService.record_movement``.

There is no ``PATCH``, no ``DELETE``, no ``PUT``, no plain ``POST
/stock-movements`` — the ledger is append-only as a property of the
API surface, not just convention. Tests pin this.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.stock_movement import MovementDirection, MovementReason
from app.models.user import User
from app.schemas.stock_movement import (
    AdjustmentCreate,
    StockMovementList,
    StockMovementRead,
)
from app.services.stock_movement_service import StockMovementService

router = APIRouter(prefix="/stock-movements", tags=["stock-movements"])

_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get(
    "",
    response_model=StockMovementList,
    summary="List stock movements (paginated, filterable)",
)
async def list_movements(
    session: _Session,
    current_user: _CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    item_id: Annotated[uuid.UUID | None, Query()] = None,
    direction: Annotated[MovementDirection | None, Query()] = None,
    reason: Annotated[MovementReason | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> StockMovementList:
    """Read-only ledger query. Newest first.

    Filters compose: ``item_id``, ``direction``, ``reason``, plus
    inclusive ``date_from`` / ``date_to`` (both interpreted in UTC).
    """
    movements, total = await StockMovementService(session).list_(
        limit=limit,
        offset=offset,
        item_id=item_id,
        direction=direction,
        reason=reason,
        date_from=date_from,
        date_to=date_to,
    )
    return StockMovementList(
        items=[StockMovementRead.model_validate(m) for m in movements],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/adjustments",
    response_model=StockMovementRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a manual stock adjustment (the only direct write path)",
)
async def create_adjustment(
    payload: AdjustmentCreate,
    session: _Session,
    current_user: _CurrentUser,
) -> StockMovementRead:
    """Record a manual stock adjustment.

    Required ``remarks`` is the accountability gate — every
    adjustment must carry an operator-supplied reason. Returns
    409 ``INSUFFICIENT_STOCK`` if an OUT adjustment would push
    stock below zero, 404 ``ITEM_NOT_FOUND`` for an unknown item.
    """
    movement = await StockMovementService(session).record_adjustment(
        payload, actor_id=current_user.id
    )
    return StockMovementRead.model_validate(movement)
