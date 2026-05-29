"""Tests for /api/v1/users — the parameterised ``/users/{user_id}`` endpoint."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"

_VALID_PASSWORD = "a-strong-passphrase"


def _user_url(user_id: str | uuid.UUID) -> str:
    return f"/api/v1/users/{user_id}"


async def _register_and_login(client: AsyncClient, email: str) -> tuple[str, str]:
    """Register a user and return ``(access_token, user_id)``.

    The user id now comes back in the login response itself
    (``LoginResponse.user.id``), which is what lets the frontend
    immediately call ``/users/{user_id}`` without a bootstrap round-trip.
    """
    await client.post(REGISTER_URL, json={"email": email, "password": _VALID_PASSWORD})
    login = await client.post(LOGIN_URL, json={"email": email, "password": _VALID_PASSWORD})
    body = login.json()
    return str(body["access_token"]), str(body["user"]["id"])


async def test_user_lookup_without_token_returns_401(client_with_db: AsyncClient) -> None:
    # Any well-formed UUID works — the auth check fires before the id check.
    response = await client_with_db.get(_user_url(uuid.uuid4()))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


async def test_user_lookup_with_invalid_token_returns_401(client_with_db: AsyncClient) -> None:
    response = await client_with_db.get(
        _user_url(uuid.uuid4()),
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


async def test_get_self_returns_user_with_valid_token(client_with_db: AsyncClient) -> None:
    token, user_id = await _register_and_login(client_with_db, "grace@example.com")

    response = await client_with_db.get(
        _user_url(user_id),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "grace@example.com"
    assert body["is_active"] is True
    assert body["id"] == user_id


async def test_get_other_user_returns_404(client_with_db: AsyncClient) -> None:
    """Cross-user reads are blocked.

    Returns **404**, not 403, so an attacker cannot enumerate which
    user ids exist by walking the UUID space. The caller is fully
    authenticated; they just aren't allowed to see this resource.
    """
    token, _ = await _register_and_login(client_with_db, "luna@example.com")

    response = await client_with_db.get(
        _user_url(uuid.uuid4()),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


async def test_get_self_with_token_for_inactive_user_returns_401(
    client_with_db: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Soft-revocation: deactivating a user invalidates their existing token.

    Exercises the ``not user.is_active`` branch in get_current_user.
    """
    email = "jack@example.com"
    token, user_id = await _register_and_login(client_with_db, email)

    user = await db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.is_active = False
    await db_session.commit()

    response = await client_with_db.get(
        _user_url(user_id),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"


async def test_get_self_with_token_for_deleted_user_returns_401(
    client_with_db: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Token resolves to a UUID that no longer exists in the users table.

    Exercises the ``user is None`` branch in get_current_user.
    """
    email = "kate@example.com"
    token, user_id = await _register_and_login(client_with_db, email)

    user = await db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    await db_session.delete(user)
    await db_session.commit()

    response = await client_with_db.get(
        _user_url(user_id),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"
