"""User-profile endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.dependencies.auth import get_current_user, require_admin
from app.models.user import User
from app.schemas.user import UserList, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])

# Reused dependency aliases keep route signatures readable.
_Session = Annotated[AsyncSession, Depends(get_db)]
_CurrentUser = Annotated[User, Depends(get_current_user)]
_AdminUser = Annotated[User, Depends(require_admin)]


@router.get(
    "",
    response_model=UserList,
    summary="List all users (admin only)",
)
async def list_users(
    session: _Session,
    admin: _AdminUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserList:
    """Return a paginated list of every user in the system.

    Returns 401 if unauthenticated, 403 with ``ADMIN_REQUIRED`` if
    the caller is not an admin. The list deliberately returns 404
    semantics only at the per-record level via ``GET /users/{id}``;
    this endpoint exists specifically *because* admins need to
    enumerate users (e.g. to disable a leaver, audit who created
    what).
    """
    users, total = await UserService(session).list_users(limit=limit, offset=offset)
    return UserList(
        items=[UserRead.model_validate(u) for u in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Return a user by id",
)
async def get_user(
    user_id: uuid.UUID,
    current_user: _CurrentUser,
) -> UserRead:
    """Return the requested user record.

    A regular caller may only fetch **their own** record. Requests
    for any other id return **404** (not 403) so the API does not
    let callers enumerate user ids by probing — admin enumeration
    happens via ``GET /users`` instead.

    Admins are also routed through this rule for consistency; the
    list endpoint is the supported way for admins to inspect any
    user.

    The caller's own user is already loaded by
    :func:`get_current_user` via the JWT, so the happy path needs
    no additional database read.
    """
    if current_user.id != user_id:
        raise NotFoundError("User not found", code="USER_NOT_FOUND")
    return UserRead.model_validate(current_user)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update a user record",
)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    session: _Session,
    current_user: _CurrentUser,
) -> UserRead:
    """Partially update a user.

    Authorization (enforced in the service layer):

    - **Self** may update own ``full_name``.
    - **Admin** may update anyone's ``full_name``, ``is_active``,
      ``is_admin``.
    - **Non-admin probing another user's id** → 404 (consistent with
      ``GET /users/{id}``; prevents id enumeration).
    - **Non-admin trying to set is_active/is_admin** → 403
      ``ADMIN_REQUIRED``.
    """
    user = await UserService(session).update_user(user_id, payload, actor=current_user)
    return UserRead.model_validate(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a user (admin only, soft-delete)",
)
async def deactivate_user(
    user_id: uuid.UUID,
    session: _Session,
    admin: _AdminUser,
) -> None:
    """Soft-delete a user (sets ``is_active=false``).

    Returns 204 on success — including the idempotent case where the
    user was already deactivated. Returns 404 if the user does not
    exist, 409 ``CANNOT_DEACTIVATE_SELF`` if the admin targets their
    own account (lockout guard).

    Hard delete is unsupported: the row is retained so the audit
    trail (``items.created_by_user_id`` etc.) stays valid.
    """
    await UserService(session).deactivate_user(user_id, actor=admin)
