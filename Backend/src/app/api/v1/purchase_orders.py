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

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.integration_layer import IntegrationLayerClient
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.purchase_order import PurchaseOrderStatus
from app.models.user import User
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderList,
    PurchaseOrderRead,
    PurchaseOrderReceive,
)
from app.services.purchase_order_service import PurchaseOrderService

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])

_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]
_Settings = Annotated[Settings, Depends(get_settings)]


def _enqueue_po_sync(
    bg: BackgroundTasks, il: IntegrationLayerClient, read: PurchaseOrderRead
) -> None:
    bg.add_task(
        il.sync_purchase_order,
        id=read.id,
        po_number=read.po_number,
        vendor_id=read.vendor_id,
        order_date=read.order_date.isoformat(),
        status=read.status.value,
        notes=read.notes,
        items=[
            {
                "item_id": str(line.item_id),
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
            }
            for line in read.items
        ],
        updated_at=read.updated_at,
    )


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
    bg: BackgroundTasks,
    settings: _Settings,
) -> PurchaseOrderRead:
    """Create a DRAFT PO with its line items.

    Validates vendor + items are active, rejects duplicate items in the
    payload (409 ``DUPLICATE_LINE_ITEM``), and either uses the
    explicit ``unit_price`` per line or falls back to the most recent
    active ``vendor_item_term`` (rate * (1 - discount/100)). 422
    ``PRICE_UNAVAILABLE`` if both are missing.
    """
    po = await PurchaseOrderService(session).create_po(payload, actor_id=current_user.id)
    read = PurchaseOrderRead.model_validate(po)
    _enqueue_po_sync(bg, IntegrationLayerClient(settings), read)
    return read


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
    payload: PurchaseOrderReceive,
    session: _Session,
    current_user: _CurrentUser,
    bg: BackgroundTasks,
    settings: _Settings,
) -> PurchaseOrderRead:
    """Receive a PO, recording a lot per line.

    The body supplies one batch entry per PO line (operator-supplied
    ``batch_number`` + ``expiry_date``, matched by ``item_id``).
    Transactionally: creates a ``batches`` row per line, increments
    ``items.stock_quantity``, inserts one ``stock_movements`` row per
    line (IN, PURCHASE, with ``batch_id`` set), flips status to RECEIVED,
    stamps ``received_date=today``.

    Errors: 409 ``PO_NOT_DRAFT`` if already received (idempotency at the
    state boundary — prevents double-counting), 404
    ``PURCHASE_ORDER_NOT_FOUND`` if missing, 422 ``RECEIVE_LINES_MISMATCH``
    if the batch entries don't cover exactly the PO's lines, 409
    ``DUPLICATE_BATCH`` if a lot number already exists for its item.
    """
    po = await PurchaseOrderService(session).receive_po(po_id, payload, actor_id=current_user.id)
    read = PurchaseOrderRead.model_validate(po)
    _enqueue_po_sync(bg, IntegrationLayerClient(settings), read)
    return read
