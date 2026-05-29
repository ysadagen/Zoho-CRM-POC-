"""Tests for /api/v1/auth — register and login."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"

_VALID_PASSWORD = "a-strong-passphrase"


async def test_register_returns_201_with_user_payload(client_with_db: AsyncClient) -> None:
    response = await client_with_db.post(
        REGISTER_URL,
        json={"email": "alice@example.com", "password": _VALID_PASSWORD},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["is_active"] is True
    assert "id" in body
    assert "created_at" in body
    # Sensitive fields must NEVER leak across the API boundary.
    assert "hashed_password" not in body
    assert "password" not in body


async def test_register_duplicate_email_returns_409(client_with_db: AsyncClient) -> None:
    payload = {"email": "bob@example.com", "password": _VALID_PASSWORD}
    first = await client_with_db.post(REGISTER_URL, json=payload)
    assert first.status_code == 201

    second = await client_with_db.post(REGISTER_URL, json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


async def test_register_short_password_returns_422(client_with_db: AsyncClient) -> None:
    # "short12" is 7 chars — one under the policy minimum of 8 — so this
    # pins the exact boundary. Bumping the policy = update this literal.
    response = await client_with_db.post(
        REGISTER_URL,
        json={"email": "carol@example.com", "password": "short12"},
    )
    assert response.status_code == 422


async def test_register_password_at_minimum_length_succeeds(
    client_with_db: AsyncClient,
) -> None:
    # 8 chars — exactly the policy minimum. Pairs with the 7-char test
    # above to pin both sides of the boundary.
    response = await client_with_db.post(
        REGISTER_URL,
        json={"email": "harry@example.com", "password": "abcd1234"},
    )
    assert response.status_code == 201


async def test_register_invalid_email_format_returns_422(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.post(
        REGISTER_URL,
        json={"email": "not-an-email", "password": _VALID_PASSWORD},
    )
    assert response.status_code == 422


async def test_email_uniqueness_is_case_insensitive(client_with_db: AsyncClient) -> None:
    await client_with_db.post(
        REGISTER_URL,
        json={"email": "Frank@example.com", "password": _VALID_PASSWORD},
    )
    response = await client_with_db.post(
        REGISTER_URL,
        json={"email": "frank@example.com", "password": _VALID_PASSWORD},
    )
    assert response.status_code == 409


async def test_login_returns_token_for_valid_credentials(client_with_db: AsyncClient) -> None:
    payload = {"email": "dave@example.com", "password": _VALID_PASSWORD}
    register_resp = await client_with_db.post(REGISTER_URL, json=payload)
    assert register_resp.status_code == 201

    login_resp = await client_with_db.post(LOGIN_URL, json=payload)

    assert login_resp.status_code == 200
    body = login_resp.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    # A real JWT is many dozens of characters; this is a cheap sanity check.
    assert len(body["access_token"]) > 20


async def test_login_returns_401_for_wrong_password(client_with_db: AsyncClient) -> None:
    await client_with_db.post(
        REGISTER_URL,
        json={"email": "eve@example.com", "password": _VALID_PASSWORD},
    )

    response = await client_with_db.post(
        LOGIN_URL,
        json={"email": "eve@example.com", "password": "wrong-passphrase-here"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_returns_401_for_unknown_email(client_with_db: AsyncClient) -> None:
    """Same error code as wrong-password — must not leak which emails are registered."""
    response = await client_with_db.post(
        LOGIN_URL,
        json={"email": "ghost@example.com", "password": _VALID_PASSWORD},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_returns_401_for_inactive_user(
    client_with_db: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Inactive users authenticate correctly but cannot obtain a token.

    Exercises the ``user.is_active is False`` branch in
    ``UserService.authenticate``. Deactivation in this test happens
    via the same transactional session the client uses, so the
    state change is visible to the next request and rolled back at
    teardown.
    """
    email = "henry@example.com"
    await client_with_db.post(
        REGISTER_URL,
        json={"email": email, "password": _VALID_PASSWORD},
    )

    user = await db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.is_active = False
    await db_session.commit()

    response = await client_with_db.post(
        LOGIN_URL,
        json={"email": email, "password": _VALID_PASSWORD},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"
