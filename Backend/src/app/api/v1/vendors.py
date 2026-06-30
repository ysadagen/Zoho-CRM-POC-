"""Vendors endpoints — full CRUD (DELETE is admin-only soft-delete)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.integration_layer import IntegrationLayerClient
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.user import User
from app.schemas.vendor import VendorCreate, VendorList, VendorRead, VendorUpdate
from app.services.vendor_service import VendorService

router = APIRouter(prefix="/vendors", tags=["vendors"])

_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]
_AdminUser = Annotated[User, Depends(require_admin)]
_Settings = Annotated[Settings, Depends(get_settings)]


def _enqueue_vendor_sync(
    bg: BackgroundTasks, il: IntegrationLayerClient, read: VendorRead
) -> None:
    bg.add_task(
        il.sync_vendor,
        id=read.id,
        vendor_name=read.vendor_name,
        contact_person=read.contact_person,
        vendor_code=read.vendor_code,
        email=str(read.email) if read.email else None,
        phone=read.phone,
        address=read.address,
        gstin=read.gstin,
        notes=read.notes,
        updated_at=read.updated_at,
    )


@router.post(
    "",
    response_model=VendorRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new vendor",
)
async def create_vendor(
    payload: VendorCreate,
    session: _Session,
    current_user: _CurrentUser,
    bg: BackgroundTasks,
    settings: _Settings,
) -> VendorRead:
    """Create a vendor. Returns 409 if ``vendor_code`` or ``gstin`` is taken."""
    vendor = await VendorService(session).create(payload, actor_id=current_user.id)
    read = VendorRead.model_validate(vendor)
    _enqueue_vendor_sync(bg, IntegrationLayerClient(settings), read)
    return read


@router.get(
    "",
    response_model=VendorList,
    summary="List vendors with pagination and filters",
)
async def list_vendors(
    session: _Session,
    current_user: _CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=255)] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> VendorList:
    """Return a paginated page of vendors, newest first.

    ``search`` matches case-insensitively on ``vendor_name`` and
    ``vendor_code``. ``is_active`` is an exact filter; omit to ignore.
    """
    vendors, total = await VendorService(session).list_(
        limit=limit,
        offset=offset,
        search=search,
        is_active=is_active,
    )
    return VendorList(
        items=[VendorRead.model_validate(v) for v in vendors],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{vendor_id}",
    response_model=VendorRead,
    summary="Return a vendor by id",
)
async def get_vendor(
    vendor_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> VendorRead:
    """Return one vendor. Returns 404 if the id does not exist."""
    vendor = await VendorService(session).get(vendor_id)
    return VendorRead.model_validate(vendor)


@router.patch(
    "/{vendor_id}",
    response_model=VendorRead,
    summary="Partially update a vendor",
)
async def update_vendor(
    vendor_id: uuid.UUID,
    payload: VendorUpdate,
    session: _Session,
    current_user: _CurrentUser,
    bg: BackgroundTasks,
    settings: _Settings,
) -> VendorRead:
    """Apply a partial update. Returns 409 on uniqueness conflicts."""
    vendor = await VendorService(session).update(vendor_id, payload, actor_id=current_user.id)
    read = VendorRead.model_validate(vendor)
    _enqueue_vendor_sync(bg, IntegrationLayerClient(settings), read)
    return read


@router.delete(
    "/{vendor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a vendor (admin only, soft-delete)",
)
async def deactivate_vendor(
    vendor_id: uuid.UUID,
    session: _Session,
    admin: _AdminUser,
) -> None:
    """Soft-delete a vendor (sets ``is_active=false``).

    Returns 204 on success — including the idempotent case where the
    vendor was already inactive. Returns 404 if the id does not exist.
    Hard delete is unsupported (purchase_orders in Phase 7 and
    vendor_item_terms will reference vendors via FK with RESTRICT).
    """
    await VendorService(session).deactivate(vendor_id, actor_id=admin.id)
