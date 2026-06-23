"""Authentication dependencies for FastAPI route handlers.

Provides :func:`get_current_user` — the single way for a route to
require an authenticated caller. Binds ``user_id`` to the structlog
context on success, so every subsequent log line in the request is
correlated to the user.

:func:`require_internal_api_key` is the separate, service-to-service auth
used by the Zoho ingest endpoints: the Integration Layer is not a user, so
it authenticates with the shared ``INTEGRATION_LAYER_API_KEY`` in a header
rather than a JWT.
"""

from __future__ import annotations

import hmac
from typing import Annotated

import structlog
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError, AuthorizationError, ServiceUnavailableError
from app.core.security import decode_token
from app.models.user import User
from app.repositories.user_repo import UserRepository

INTERNAL_API_KEY_HEADER = "X-Internal-API-Key"

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


async def require_internal_api_key(
    x_internal_api_key: Annotated[str | None, Header(alias=INTERNAL_API_KEY_HEADER)] = None,
) -> None:
    """Authenticate a service-to-service caller (the Integration Layer).

    Compares the header against ``INTEGRATION_LAYER_API_KEY`` in constant time
    so the secret can't be inferred from response timing. Raises
    :class:`AuthenticationError` (401) when the header is missing or wrong.
    This is the only auth on the ingest endpoints — no JWT, no user.
    """
    expected = get_settings().integration_layer_api_key
    if not x_internal_api_key or not hmac.compare_digest(x_internal_api_key, expected):
        raise AuthenticationError(
            "Invalid or missing internal API key", code="INVALID_API_KEY"
        )


async def require_ingest_enabled() -> None:
    """Reject ingest writes (503) unless ``ZOHO_INGEST_ENABLED`` is set.

    A belt-and-braces gate on top of the internal API key: ingest is off by
    default so the engines stay deterministic until the IL is switched on.
    """
    if not get_settings().zoho_ingest_enabled:
        raise ServiceUnavailableError(
            "Zoho ingest is disabled on this Backend", code="INGEST_DISABLED"
        )
