"""Password hashing and JWT issue/verify primitives.

Password hashing uses **Argon2id** via ``pwdlib``. Argon2id is the
IETF RFC 9106 and OWASP 2024 #1 recommendation for password storage:
memory-hard (GPU/ASIC-resistant), and free of bcrypt's 72-byte input
limit and its silent-truncation footgun.

``pwdlib`` is the actively-maintained, typed successor to ``passlib``.
It supports algorithm migration (``verify_and_update``) so if we ever
swap algorithms the existing hashes can be upgraded on next successful
login without a forced password reset.

Nothing in here knows about users, sessions, or HTTP. This module
deliberately stays a thin boundary so it can be unit-tested in
isolation and swapped without touching any other layer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

# Single shared instance reused across calls. Argon2id is the only
# configured hasher — appropriate for greenfield projects with no
# legacy bcrypt hashes to verify. Adding a BcryptHasher to the tuple
# later would enable transparent rehash-on-login migration without
# breaking existing users.
_password_hash = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    """Hash ``password`` and return the encoded string for storage."""
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time compare ``plain_password`` against the stored hash.

    Returns ``False`` on any inability to verify (malformed stored
    hash, unknown algorithm prefix, etc.) so a caller never has to
    differentiate "wrong password" from "weird input".
    """
    return _password_hash.verify(plain_password, hashed_password)


def create_access_token(subject: uuid.UUID) -> tuple[str, int]:
    """Issue a signed access token for ``subject``.

    Returns ``(token, expires_in_seconds)`` so the caller can build a
    response without re-reading settings or recomputing the lifetime.

    Payload is intentionally minimal — ``sub``, ``iat``, ``exp``. Any
    per-user data (email, role, flags) is looked up fresh on each
    request, so revoking or disabling a user takes effect immediately.
    """
    settings = get_settings()
    expires_in = settings.access_token_expire_minutes * 60
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_in


def decode_token(token: str) -> uuid.UUID:
    """Validate ``token`` and return the subject UUID.

    Raises :class:`AuthenticationError` on any failure (bad signature,
    expired, malformed subject). Callers should not differentiate
    among these — they're all the same response to the client (401).
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
