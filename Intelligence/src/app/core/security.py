"""JWT verification for the Intelligence service.

This service never issues tokens — it only **validates** the access tokens
the Backend issues (same ``jwt_secret_key`` / ``jwt_algorithm``). It therefore
needs only :func:`decode_token`; password hashing and token minting live in
the Backend.

Nothing here knows about users, sessions, or HTTP — a thin boundary that can
be unit-tested in isolation.
"""

from __future__ import annotations

import uuid

from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError


def decode_token(token: str) -> uuid.UUID:
    """Validate ``token`` and return the subject UUID.

    Raises :class:`AuthenticationError` on any failure (bad signature,
    expired, malformed subject) — all the same 401 to the client.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired token", code="INVALID_TOKEN") from exc

    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise AuthenticationError("Invalid token subject", code="INVALID_TOKEN")
    try:
        return uuid.UUID(sub)
    except ValueError as exc:
        raise AuthenticationError("Invalid token subject", code="INVALID_TOKEN") from exc
