"""Purchase-order endpoints.

Exactly four routes per the Phase 7 spec:

- ``POST   /api/v1/purchase-orders``              — create DRAFT
- ``GET    /api/v1/purchase-orders``              — paginated list
- ``GET    /api/v1/purchase-orders/{id}``         — full PO with lines
- ``POST   /api/v1/purchase-orders/{id}/receive`` — DRAFT → RECEIVED

No PATCH, no DELETE. Pinned by
``test_no_patch_or_delete_endpoint_for_purchase_orders``.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.purchase_order import PurchaseOrderStatus
from app.models.user import User
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderList,
    PurchaseOrderRead,
)
from app.services.purchase_order_service import PurchaseOrderService

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])

_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "",
    response_model=PurchaseOrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a purchase order (DRAFT)",
)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    session: _Session,
    current_user: _CurrentUser,
) -> PurchaseOrderRead:
    """Create a DRAFT PO with its line items.

    Validates vendor + items are active, rejects duplicate items in the
    payload (409 ``DUPLICATE_LINE_ITEM``), and either uses the
    explicit ``unit_price`` per line or falls back to the most recent
    active ``vendor_item_term`` (rate * (1 - discount/100)). 422
    ``PRICE_UNAVAILABLE`` if both are missing.
    """
    po = await PurchaseOrderService(session).create_po(payload, actor_id=current_user.id)
    return PurchaseOrderRead.model_validate(po)


@router.get(
    "",
    response_model=PurchaseOrderList,
    summary="List purchase orders (paginated, filterable)",
)
async def list_purchase_orders(
    session: _Session,
    current_user: _CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    vendor_id: Annotated[uuid.UUID | None, Query()] = None,
    po_status: Annotated[
        PurchaseOrderStatus | None,
        Query(alias="status", description="Filter by lifecycle status"),
    ] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> PurchaseOrderList:
    """Paginated PO list, newest first.

    ``date_from`` / ``date_to`` filter on ``order_date``, inclusive on
    both ends. The query-param name ``status`` (aliased to ``po_status``
    inside the handler) avoids shadowing the ``status`` import from
    starlette/fastapi.
    """
    pos, total = await PurchaseOrderService(session).list_pos(
        limit=limit,
        offset=offset,
        vendor_id=vendor_id,
        status=po_status,
        date_from=date_from,
        date_to=date_to,
    )
    return PurchaseOrderList(
        items=[PurchaseOrderRead.model_validate(p) for p in pos],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{po_id}",
    response_model=PurchaseOrderRead,
    summary="Return a purchase order by id (with line items)",
)
async def get_purchase_order(
    po_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> PurchaseOrderRead:
    """Return one PO. 404 ``PURCHASE_ORDER_NOT_FOUND`` if missing."""
    po = await PurchaseOrderService(session).get_po(po_id)
    return PurchaseOrderRead.model_validate(po)


@router.post(
    "/{po_id}/receive",
    response_model=PurchaseOrderRead,
    summary="Receive a purchase order (DRAFT → RECEIVED, posts ledger rows)",
)
async def receive_purchase_order(
    po_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> PurchaseOrderRead:
    """Receive a PO.

    Transactionally: increments ``items.stock_quantity`` for each
    line, inserts one ``stock_movements`` row per line (IN, PURCHASE),
    flips status to RECEIVED, stamps ``received_date=today``.

    Returns 409 ``PO_NOT_DRAFT`` if the PO has already been received
    (idempotency at the state boundary — prevents double-counting
    stock), 404 ``PURCHASE_ORDER_NOT_FOUND`` if the PO does not exist.
    """
    po = await PurchaseOrderService(session).receive_po(po_id, actor_id=current_user.id)
    return PurchaseOrderRead.model_validate(po)
