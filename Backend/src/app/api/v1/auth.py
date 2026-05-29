"""Authentication endpoints: register + login."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.user import Token, UserCreate, UserLogin, UserRead
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    """Create a new user. Returns 409 if the email is already registered."""
    user = await UserService(session).register(payload)
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=Token,
    summary="Exchange email + password for an access token",
)
async def login(
    payload: UserLogin,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Authenticate and return a bearer JWT.

    Returns 401 on invalid credentials or a disabled account. The same
    code (``INVALID_CREDENTIALS``) is returned for both unknown email
    and wrong password to avoid leaking which emails are registered.
    """
    return await UserService(session).authenticate(payload)
