"""Items endpoints — full CRUD (no DELETE per Phase 1 rules)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.item import ItemType
from app.models.user import User
from app.schemas.bulk_upload import BulkUploadResult
from app.schemas.item import ItemCreate, ItemCreated, ItemList, ItemRead, ItemUpdate
from app.services.bulk_upload_service import BulkUploadService
from app.services.item_service import ItemService

router = APIRouter(prefix="/items", tags=["items"])

# Reused dependency aliases — Annotated[...] gets verbose at every signature.
_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]


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
) -> ItemCreated:
    """Create an item. Returns 409 if the SKU is already taken.

    The response is **deliberately minimal** — only the fields a
    client needs to confirm creation and navigate (``id``, ``sku``,
    ``name``, ``created_at``). Use ``GET /items/{id}`` to retrieve
    the full record including stock figures, status, and audit fields.
    See ``ItemCreated`` docstring for the rationale.
    """
    item = await ItemService(session).create(payload, actor_id=current_user.id)
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
) -> ItemList:
    """Return a page of items, newest first.

    Filters compose: ``type``, ``category``, and a case-insensitive
    ``search`` over SKU and name. ``total`` is the count after filters
    but before pagination so the frontend can render pager controls.
    """
    items, total = await ItemService(session).list_(
        limit=limit,
        offset=offset,
        item_type=type,
        category=category,
        search=search,
    )
    return ItemList(
        items=[ItemRead.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/bulk-upload",
    response_model=BulkUploadResult,
    summary="Bulk-create items from a CSV or XLSX file",
)
async def bulk_upload_items(
    session: _Session,
    current_user: _CurrentUser,
    file: Annotated[UploadFile, File()],
) -> BulkUploadResult:
    """Bulk-create items from an uploaded CSV or ``.xlsx`` file.

    Each row is validated and created independently — a row failure does
    not abort the batch. The response is always ``200`` with a per-row
    report (see :class:`BulkUploadResult`). Structural problems with the
    request itself (unsupported file type, empty file, missing required
    columns, or too many rows) are rejected as ``422`` with the standard
    error envelope instead of a row result. Row numbers are 1-based and
    include the header row (row 1), matching what a spreadsheet shows.
    """
    content = await file.read()
    return await BulkUploadService(session).process_file(
        filename=file.filename or "", content=content, actor_id=current_user.id
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
) -> ItemRead:
    """Apply a partial update.

    Omitted fields are left untouched. ``sku``, ``type``, and
    ``stock_quantity`` are not patchable — sending them returns 422.
    Stock changes will move to the stock-movement ledger in Phase 6.
    """
    item = await ItemService(session).update(item_id, payload, actor_id=current_user.id)
    return ItemRead.model_validate(item)
