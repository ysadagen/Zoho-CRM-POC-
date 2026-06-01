"""Sales-order endpoints.

Four routes, mirroring Phase 7:

- ``POST   /api/v1/sales-orders``           — create DRAFT
- ``GET    /api/v1/sales-orders``           — paginated list
- ``GET    /api/v1/sales-orders/{id}``      — full SO with lines
- ``POST   /api/v1/sales-orders/{id}/ship`` — DRAFT → SHIPPED

No PATCH, no DELETE. Pinned by
``test_no_patch_or_delete_endpoint_for_sales_orders``.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.sales_order import SalesOrderStatus
from app.models.user import User
from app.schemas.sales_order import (
    SalesOrderCreate,
    SalesOrderList,
    SalesOrderRead,
)
from app.services.sales_order_service import SalesOrderService

router = APIRouter(prefix="/sales-orders", tags=["sales-orders"])

_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "",
    response_model=SalesOrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a sales order (DRAFT)",
)
async def create_sales_order(
    payload: SalesOrderCreate,
    session: _Session,
    current_user: _CurrentUser,
) -> SalesOrderRead:
    """Create a DRAFT SO with its line items.

    Validates customer + items are active, rejects duplicate items in
    the payload (409 ``DUPLICATE_LINE_ITEM``), and either uses the
    explicit ``unit_price`` per line or falls back to the item's
    catalog ``unit_price`` (the list price). No stock pre-check —
    that's enforced at ``/ship``.
    """
    so = await SalesOrderService(session).create_so(payload, actor_id=current_user.id)
    return SalesOrderRead.model_validate(so)


@router.get(
    "",
    response_model=SalesOrderList,
    summary="List sales orders (paginated, filterable)",
)
async def list_sales_orders(
    session: _Session,
    current_user: _CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    customer_id: Annotated[uuid.UUID | None, Query()] = None,
    so_status: Annotated[
        SalesOrderStatus | None,
        Query(alias="status", description="Filter by lifecycle status"),
    ] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> SalesOrderList:
    """Paginated SO list, newest first.

    ``date_from`` / ``date_to`` filter on ``order_date``, inclusive on
    both ends. The query-param name ``status`` is aliased to
    ``so_status`` inside the handler to avoid shadowing the ``status``
    import from starlette/fastapi.
    """
    sos, total = await SalesOrderService(session).list_sos(
        limit=limit,
        offset=offset,
        customer_id=customer_id,
        status=so_status,
        date_from=date_from,
        date_to=date_to,
    )
    return SalesOrderList(
        items=[SalesOrderRead.model_validate(s) for s in sos],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{so_id}",
    response_model=SalesOrderRead,
    summary="Return a sales order by id (with line items)",
)
async def get_sales_order(
    so_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> SalesOrderRead:
    """Return one SO. 404 ``SALES_ORDER_NOT_FOUND`` if missing."""
    so = await SalesOrderService(session).get_so(so_id)
    return SalesOrderRead.model_validate(so)


@router.post(
    "/{so_id}/ship",
    response_model=SalesOrderRead,
    summary="Ship a sales order (DRAFT → SHIPPED, posts OUT ledger rows)",
)
async def ship_sales_order(
    so_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> SalesOrderRead:
    """Ship an SO.

    Transactionally: decrements ``items.stock_quantity`` for each line,
    inserts one ``stock_movements`` row per line (OUT, SALE), flips
    status to SHIPPED, stamps ``shipped_date=today``.

    Failure modes:

    - 404 ``SALES_ORDER_NOT_FOUND`` — SO does not exist.
    - 409 ``SO_NOT_DRAFT`` — second ship attempt (idempotency at the
      state boundary).
    - 409 ``INSUFFICIENT_STOCK`` — any line would push stock below
      zero. Entire ship is rolled back (no partial stock or ledger).
    """
    so = await SalesOrderService(session).ship_so(so_id, actor_id=current_user.id)
    return SalesOrderRead.model_validate(so)
