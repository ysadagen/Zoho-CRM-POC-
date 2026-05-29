"""User-profile endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.exceptions import NotFoundError
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Return a user by id",
)
async def get_user(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    """Return the requested user record.

    Phase 1 has no admin role, so a caller can only fetch **their
    own** record. Requests for any other id return **404** (not 403)
    so the API does not let callers enumerate user ids by probing.

    The caller's own user is already loaded by :func:`get_current_user`
    via the JWT, so the happy path needs no additional database read.
    """
    if current_user.id != user_id:
        raise NotFoundError("User not found", code="USER_NOT_FOUND")
    return UserRead.model_validate(current_user)
