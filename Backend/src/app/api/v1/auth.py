"""Authentication endpoints: register + login."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.user import LoginResponse, UserCreate, UserLogin, UserRead
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])

_Session = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    payload: UserCreate,
    session: _Session,
) -> UserRead:
    """Create a new user. Returns 409 if the email is already registered."""
    user = await UserService(session).register(payload)
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Exchange email + password for an access token",
)
async def login(
    payload: UserLogin,
    session: _Session,
) -> LoginResponse:
    """Authenticate and return a bearer JWT plus the user profile.

    Returns 401 on invalid credentials or a disabled account. The same
    code (``INVALID_CREDENTIALS``) is returned for both unknown email
    and wrong password to avoid leaking which emails are registered.

    The ``user`` field lets the frontend skip a follow-up profile
    lookup — without it the client would need to call
    ``GET /users/{user_id}`` immediately after login just to learn
    its own id. ``expires_in`` (seconds) is included so the client
    can show "session expires in N minutes" and prompt re-login
    before a 401 surprises an in-flight submit.
    """
    user, token = await UserService(session).authenticate(payload)
    return LoginResponse(**token.model_dump(), user=UserRead.model_validate(user))
