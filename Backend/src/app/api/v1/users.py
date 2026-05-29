"""User profile endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserRead,
    summary="Return the currently authenticated user",
)
async def read_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    """Return the profile of the calling user.

    Returns 401 if the bearer token is missing, invalid, or refers to a
    user that no longer exists or has been disabled.
    """
    return UserRead.model_validate(current_user)
