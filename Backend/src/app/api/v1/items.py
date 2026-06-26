"""Items endpoints — full CRUD (no DELETE per Phase 1 rules)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.integration_layer import IntegrationLayerClient
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.item import ItemType
from app.models.user import User
from app.schemas.item import ItemCreate, ItemCreated, ItemList, ItemRead, ItemStatus, ItemUpdate
from app.services.item_service import ItemService

router = APIRouter(prefix="/items", tags=["items"])

# Reused dependency aliases — Annotated[...] gets verbose at every signature.
_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]
_Settings = Annotated[Settings, Depends(get_settings)]


@router.post(
    "",
    response_model=ItemCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new item",
)
async def create_item(
    payload: ItemCreate,
    session: _Session,
    current_user: _CurrentUser,
    bg: BackgroundTasks,
    settings: _Settings,
) -> ItemCreated:
    """Create an item. Returns 409 if the SKU is already taken.

    The response is **deliberately minimal** — only the fields a
    client needs to confirm creation and navigate (``id``, ``sku``,
    ``name``, ``created_at``). Use ``GET /items/{id}`` to retrieve
    the full record including stock figures, status, and audit fields.
    See ``ItemCreated`` docstring for the rationale.
    """
    item = await ItemService(session).create(payload, actor_id=current_user.id)
    full = ItemRead.model_validate(item)
    il = IntegrationLayerClient(settings)
    bg.add_task(
        il.sync_item,
        id=full.id,
        name=full.name,
        sku=full.sku,
        item_type=full.type.value,
        unit_of_measure=full.unit_of_measure,
        unit_price=full.unit_price,
        reorder_threshold=full.reorder_threshold,
        updated_at=full.updated_at,
    )
    return ItemCreated.model_validate(item)


@router.get(
    "",
    response_model=ItemList,
    summary="List items with pagination and filters",
)
async def list_items(
    session: _Session,
    current_user: _CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    type: Annotated[ItemType | None, Query()] = None,
    category: Annotated[str | None, Query(max_length=64)] = None,
    search: Annotated[str | None, Query(max_length=255)] = None,
    status: Annotated[list[ItemStatus] | None, Query()] = None,
    include_inactive: Annotated[bool, Query()] = False,
) -> ItemList:
    """Return a page of items, newest first.

    Filters compose: ``type``, ``category``, a case-insensitive ``search``
    over SKU and name, and ``status`` (the derived stock-health bucket). The
    ``status`` filter is repeatable — pass it more than once to match any of
    several buckets (e.g. ``?status=LOW_STOCK&status=NO_STOCK`` for everything
    that needs attention). Soft-deleted (inactive) items are excluded unless
    ``include_inactive=true``. ``total`` is the count after filters but before
    pagination so the frontend can render pager controls.
    """
    items, total = await ItemService(session).list_(
        limit=limit,
        offset=offset,
        item_type=type,
        category=category,
        search=search,
        statuses=status,
        include_inactive=include_inactive,
    )
    return ItemList(
        items=[ItemRead.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{item_id}",
    response_model=ItemRead,
    summary="Return an item by id",
)
async def get_item(
    item_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> ItemRead:
    """Return one item. Returns 404 if the id does not exist."""
    item = await ItemService(session).get(item_id)
    return ItemRead.model_validate(item)


@router.patch(
    "/{item_id}",
    response_model=ItemRead,
    summary="Partially update an item",
)
async def update_item(
    item_id: uuid.UUID,
    payload: ItemUpdate,
    session: _Session,
    current_user: _CurrentUser,
    bg: BackgroundTasks,
    settings: _Settings,
) -> ItemRead:
    """Apply a partial update.

    Omitted fields are left untouched. ``sku``, ``type``, and
    ``stock_quantity`` are not patchable — sending them returns 422.
    Stock changes will move to the stock-movement ledger in Phase 6.
    """
    item = await ItemService(session).update(item_id, payload, actor_id=current_user.id)
    read = ItemRead.model_validate(item)
    il = IntegrationLayerClient(settings)
    bg.add_task(
        il.sync_item,
        id=read.id,
        name=read.name,
        sku=read.sku,
        item_type=read.type.value,
        unit_of_measure=read.unit_of_measure,
        unit_price=read.unit_price,
        reorder_threshold=read.reorder_threshold,
        updated_at=read.updated_at,
    )
    return read


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete (deactivate) an item",
)
async def delete_item(
    item_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> None:
    """Deactivate an item (``is_active = false``).

    This is a **soft** delete — the row is never removed, so the audit
    trail (movements, POs, SOs, lots that reference it) stays intact. The
    item drops out of the default list and can't be added to new orders.
    Returns 204; 404 if the id is unknown.
    """
    await ItemService(session).soft_delete(item_id, actor_id=current_user.id)
