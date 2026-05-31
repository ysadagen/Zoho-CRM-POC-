"""Endpoints for vendor-item pricing terms.

Nested under vendors: ``/api/v1/vendors/{vendor_id}/terms/...``
The path segment is ``terms`` (not ``items``) to avoid colliding with
the global ``/items`` namespace and to accurately name the resource.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.vendor_item_term import (
    VendorItemTermCreate,
    VendorItemTermList,
    VendorItemTermRead,
    VendorItemTermUpdate,
)
from app.services.vendor_item_term_service import VendorItemTermService

router = APIRouter(
    prefix="/vendors/{vendor_id}/terms",
    tags=["vendor-terms"],
)

_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "",
    response_model=VendorItemTermRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a pricing term for a vendor + item",
)
async def create_term(
    vendor_id: uuid.UUID,
    payload: VendorItemTermCreate,
    session: _Session,
    current_user: _CurrentUser,
) -> VendorItemTermRead:
    """Create a new pricing term.

    Returns 404 ``VENDOR_NOT_FOUND`` / ``ITEM_NOT_FOUND`` if either
    referenced row is missing. Returns 409 ``OVERLAPPING_TERMS`` if an
    active term already covers any part of the requested date range
    for the same (vendor, item).
    """
    term = await VendorItemTermService(session).create(vendor_id, payload, actor_id=current_user.id)
    return VendorItemTermRead.model_validate(term)


@router.get(
    "",
    response_model=VendorItemTermList,
    summary="List pricing terms for a vendor (paginated)",
)
async def list_terms(
    vendor_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    item_id: Annotated[uuid.UUID | None, Query()] = None,
    active_only: Annotated[bool, Query()] = False,
) -> VendorItemTermList:
    """Return paginated terms for this vendor, newest ``effective_from`` first.

    Filters: ``item_id`` (exact), ``active_only`` (only ``is_active=true``
    rows). Default returns both active and historical rows so the UI
    can render full price history.
    """
    terms, total = await VendorItemTermService(session).list_(
        vendor_id,
        limit=limit,
        offset=offset,
        item_id=item_id,
        active_only=active_only,
    )
    return VendorItemTermList(
        items=[VendorItemTermRead.model_validate(t) for t in terms],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{term_id}",
    response_model=VendorItemTermRead,
    summary="Return a pricing term by id",
)
async def get_term(
    vendor_id: uuid.UUID,
    term_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> VendorItemTermRead:
    """Return one term. Returns 404 if the term doesn't exist **or**
    belongs to a different vendor (cross-vendor probing prevention)."""
    term = await VendorItemTermService(session).get(vendor_id, term_id)
    return VendorItemTermRead.model_validate(term)


@router.patch(
    "/{term_id}",
    response_model=VendorItemTermRead,
    summary="Partially update a pricing term",
)
async def update_term(
    vendor_id: uuid.UUID,
    term_id: uuid.UUID,
    payload: VendorItemTermUpdate,
    session: _Session,
    current_user: _CurrentUser,
) -> VendorItemTermRead:
    """Apply a partial update.

    Re-checks the overlap invariant against the *post-update* date
    range. Returns 409 if the resulting range would overlap with
    another active term, 422 if the resulting dates are out of order.
    """
    term = await VendorItemTermService(session).update(
        vendor_id, term_id, payload, actor_id=current_user.id
    )
    return VendorItemTermRead.model_validate(term)


@router.delete(
    "/{term_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a pricing term (soft-delete)",
)
async def deactivate_term(
    vendor_id: uuid.UUID,
    term_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> None:
    """Soft-delete a term (``is_active=false``).

    Any authenticated user — pricing isn't an admin-only boundary.
    Idempotent on already-inactive rows. Hard delete is unsupported
    so the audit trail of past prices remains intact.
    """
    await VendorItemTermService(session).deactivate(vendor_id, term_id, actor_id=current_user.id)
