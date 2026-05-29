"""Authentication dependencies for FastAPI route handlers.

Provides :func:`get_current_user` — the single way for a route to
require an authenticated caller. Binds ``user_id`` to the structlog
context on success, so every subsequent log line in the request is
correlated to the user.
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import decode_token
from app.models.user import User
from app.repositories.user_repo import UserRepository

# ``auto_error=False`` so we raise our own AppError instead of FastAPI's
# generic 403, keeping the error envelope shape consistent.
_bearer_scheme = HTTPBearer(auto_error=False, description="Bearer token from /auth/login")


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the current user from the ``Authorization: Bearer`` header.

    Raises :class:`AuthenticationError` (401) on:
      - missing or non-bearer credentials
      - invalid / expired / malformed token
      - subject UUID not present in the users table
      - user is marked inactive
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Missing bearer token", code="MISSING_TOKEN")

    user_id = decode_token(credentials.credentials)
    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise AuthenticationError("User not found", code="USER_NOT_FOUND")
    if not user.is_active:
        raise AuthenticationError("User account is disabled", code="ACCOUNT_DISABLED")

    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    return user


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require the caller to be an admin user.

    Builds on :func:`get_current_user`, so all the standard auth
    checks (token present, valid, user exists, active, log binding)
    run first. Raises :class:`AuthorizationError` (HTTP 403) when the
    authenticated user is not marked ``is_admin``.

    Phase 1 has no admin-promotion endpoint — the first admin is
    granted by a one-line SQL update (see ``Backend/README.md``).
    """
    if not current_user.is_admin:
        raise AuthorizationError(
            "Admin role required for this resource",
            code="ADMIN_REQUIRED",
        )
    return current_user
