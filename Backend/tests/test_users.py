"""Tests for /api/v1/users — the protected /me endpoint."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/users/me"

_VALID_PASSWORD = "a-strong-passphrase"


async def _register_and_login(client: AsyncClient, email: str) -> str:
    """Register a user and return their bearer access token."""
    await client.post(REGISTER_URL, json={"email": email, "password": _VALID_PASSWORD})
    login = await client.post(LOGIN_URL, json={"email": email, "password": _VALID_PASSWORD})
    return str(login.json()["access_token"])


async def test_me_without_token_returns_401(client_with_db: AsyncClient) -> None:
    response = await client_with_db.get(ME_URL)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


async def test_me_with_invalid_token_returns_401(client_with_db: AsyncClient) -> None:
    response = await client_with_db.get(
        ME_URL,
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


async def test_me_returns_current_user_with_valid_token(client_with_db: AsyncClient) -> None:
    token = await _register_and_login(client_with_db, "grace@example.com")

    me_resp = await client_with_db.get(
        ME_URL,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_resp.status_code == 200
    body = me_resp.json()
    assert body["email"] == "grace@example.com"
    assert body["is_active"] is True
    assert "id" in body


async def test_me_with_token_for_inactive_user_returns_401(
    client_with_db: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Soft-revocation: deactivating a user invalidates their existing token.

    Exercises the ``not user.is_active`` branch in get_current_user.
    This is the property that makes the "JWT carries only sub, lookup
    fresh on each request" design pay off — a token for a disabled
    user must stop working on the very next request.
    """
    email = "jack@example.com"
    token = await _register_and_login(client_with_db, email)

    user = await db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.is_active = False
    await db_session.commit()

    response = await client_with_db.get(
        ME_URL,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"


async def test_me_with_token_for_deleted_user_returns_401(
    client_with_db: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Token resolves to a UUID that no longer exists in the users table.

    Exercises the ``user is None`` branch in get_current_user. A
    deleted user's old tokens must not authenticate against a stale id.
    """
    email = "kate@example.com"
    token = await _register_and_login(client_with_db, email)

    user = await db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    await db_session.delete(user)
    await db_session.commit()

    response = await client_with_db.get(
        ME_URL,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"
