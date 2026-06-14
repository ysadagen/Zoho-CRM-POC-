"""Customers endpoints — full CRUD (DELETE is admin-only soft-delete)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerList, CustomerRead, CustomerUpdate
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["customers"])

_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]
_AdminUser = Annotated[User, Depends(require_admin)]


@router.post(
    "",
    response_model=CustomerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer",
)
async def create_customer(
    payload: CustomerCreate,
    session: _Session,
    current_user: _CurrentUser,
) -> CustomerRead:
    """Create a customer. Returns 409 if ``customer_code`` or ``gstin`` is taken."""
    customer = await CustomerService(session).create(payload, actor_id=current_user.id)
    return CustomerRead.model_validate(customer)


@router.get(
    "",
    response_model=CustomerList,
    summary="List customers with pagination and filters",
)
async def list_customers(
    session: _Session,
    current_user: _CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=255)] = None,
    is_privileged: Annotated[bool | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> CustomerList:
    """Return a paginated page of customers, newest first.

    ``search`` matches case-insensitively on ``company_name`` and
    ``customer_code``. ``is_privileged`` and ``is_active`` are exact
    filters; omit them to ignore that filter.
    """
    customers, total = await CustomerService(session).list_(
        limit=limit,
        offset=offset,
        search=search,
        is_privileged=is_privileged,
        is_active=is_active,
    )
    return CustomerList(
        items=[CustomerRead.model_validate(c) for c in customers],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{customer_id}",
    response_model=CustomerRead,
    summary="Return a customer by id",
)
async def get_customer(
    customer_id: uuid.UUID,
    session: _Session,
    current_user: _CurrentUser,
) -> CustomerRead:
    """Return one customer. Returns 404 if the id does not exist."""
    customer = await CustomerService(session).get(customer_id)
    return CustomerRead.model_validate(customer)


@router.patch(
    "/{customer_id}",
    response_model=CustomerRead,
    summary="Partially update a customer",
)
async def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    session: _Session,
    current_user: _CurrentUser,
) -> CustomerRead:
    """Apply a partial update. Returns 409 on uniqueness conflicts."""
    customer = await CustomerService(session).update(customer_id, payload, actor_id=current_user.id)
    return CustomerRead.model_validate(customer)


@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a customer (admin only, soft-delete)",
)
async def deactivate_customer(
    customer_id: uuid.UUID,
    session: _Session,
    admin: _AdminUser,
) -> None:
    """Soft-delete a customer (sets ``is_active=false``).

    Returns 204 on success — including the idempotent case where the
    customer was already inactive. Returns 404 if the id does not
    exist. Hard delete is unsupported (sales_orders in Phase 8 will
    reference customers via FK with RESTRICT).
    """
    await CustomerService(session).deactivate(customer_id, actor_id=admin.id)
