"""Tests for /api/v1/users — the parameterised ``/users/{user_id}`` endpoint."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
USERS_URL = "/api/v1/users"

_VALID_PASSWORD = "a-strong-passphrase"


def _user_url(user_id: str | uuid.UUID) -> str:
    return f"/api/v1/users/{user_id}"


async def _register_and_login(
    client: AsyncClient,
    email: str,
    *,
    full_name: str = "Test User",
) -> tuple[str, str]:
    """Register a user and return ``(access_token, user_id)``.

    The user id now comes back in the login response itself
    (``LoginResponse.user.id``), which is what lets the frontend
    immediately call ``/users/{user_id}`` without a bootstrap round-trip.
    """
    await client.post(
        REGISTER_URL,
        json={"email": email, "full_name": full_name, "password": _VALID_PASSWORD},
    )
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


# ---------------------------------------------------------------------------
# GET /api/v1/users — admin-only list endpoint
# ---------------------------------------------------------------------------


async def test_list_users_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.get(USERS_URL)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


async def test_list_users_as_non_admin_returns_403(
    authenticated_client: AsyncClient,
) -> None:
    """Regular authenticated users cannot enumerate the user list.

    This is the authorization wall — distinct from the auth wall.
    Anonymous → 401, authenticated-but-not-admin → 403.
    """
    response = await authenticated_client.get(USERS_URL)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_REQUIRED"


async def test_list_users_as_admin_returns_paginated_users(
    admin_authenticated_client: AsyncClient,
) -> None:
    """Happy path. Verifies envelope shape and the no-PII-leak invariant."""
    response = await admin_authenticated_client.get(USERS_URL)

    assert response.status_code == 200
    body = response.json()

    # Envelope shape per CLAUDE.md §6.
    assert {"items", "total", "limit", "offset"} <= body.keys()
    assert body["limit"] == 25
    assert body["offset"] == 0
    assert body["total"] >= 1  # the admin fixture user itself

    for user in body["items"]:
        # Sensitive fields must never leak.
        assert "hashed_password" not in user
        assert "password" not in user
        # Role bit visible so the frontend can gate UI.
        assert "is_admin" in user
        assert "is_active" in user


async def test_list_users_respects_pagination_params(
    admin_authenticated_client: AsyncClient,
) -> None:
    """``limit`` caps page size; ``total`` reflects all matching rows."""
    # Register an extra user so we have at least two rows. Register
    # is unauthenticated, so the bearer header on the admin client is
    # simply ignored by the endpoint.
    await admin_authenticated_client.post(
        REGISTER_URL,
        json={
            "email": "extra-user@example.com",
            "full_name": "Extra User",
            "password": _VALID_PASSWORD,
        },
    )

    response = await admin_authenticated_client.get(
        USERS_URL,
        params={"limit": 1, "offset": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert len(body["items"]) == 1
    assert body["total"] >= 2


async def test_register_creates_non_admin_user_by_default(
    client_with_db: AsyncClient,
) -> None:
    """New registrations must default to ``is_admin=False``.

    Closes the ``first-user-wins`` footgun explicitly — admin is
    only ever granted out-of-band (SQL in Phase 1).
    """
    response = await client_with_db.post(
        REGISTER_URL,
        json={
            "email": "fresh-non-admin@example.com",
            "full_name": "Fresh Non-Admin",
            "password": _VALID_PASSWORD,
        },
    )

    assert response.status_code == 201
    assert response.json()["is_admin"] is False


async def test_register_returns_full_name_in_response(
    client_with_db: AsyncClient,
) -> None:
    """``full_name`` round-trips: sent in payload, returned in response body."""
    response = await client_with_db.post(
        REGISTER_URL,
        json={
            "email": "named@example.com",
            "full_name": "Properly Named",
            "password": _VALID_PASSWORD,
        },
    )
    assert response.status_code == 201
    assert response.json()["full_name"] == "Properly Named"


# ---------------------------------------------------------------------------
# PATCH /api/v1/users/{user_id} — role-aware partial update
# ---------------------------------------------------------------------------


async def test_patch_user_self_updates_full_name(client_with_db: AsyncClient) -> None:
    token, user_id = await _register_and_login(
        client_with_db, "selfedit@example.com", full_name="Original Name"
    )

    response = await client_with_db.patch(
        _user_url(user_id),
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Renamed Self"},
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Renamed Self"


async def test_patch_user_other_as_non_admin_returns_404(
    client_with_db: AsyncClient,
) -> None:
    """Enumeration prevention: same shape as ``GET /users/{other_id}``."""
    token, _ = await _register_and_login(client_with_db, "snooper@example.com")

    response = await client_with_db.patch(
        _user_url(uuid.uuid4()),
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Hacked"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


async def test_patch_user_is_admin_as_non_admin_returns_403(
    client_with_db: AsyncClient,
) -> None:
    """Non-admin must not be able to self-promote via PATCH."""
    token, user_id = await _register_and_login(client_with_db, "wannabe@example.com")

    response = await client_with_db.patch(
        _user_url(user_id),
        headers={"Authorization": f"Bearer {token}"},
        json={"is_admin": True},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_REQUIRED"


async def test_patch_user_other_as_admin_updates_full_name(
    admin_authenticated_client: AsyncClient,
) -> None:
    register_resp = await admin_authenticated_client.post(
        REGISTER_URL,
        json={
            "email": "target@example.com",
            "full_name": "Target User",
            "password": _VALID_PASSWORD,
        },
    )
    target_id = register_resp.json()["id"]

    response = await admin_authenticated_client.patch(
        _user_url(target_id),
        json={"full_name": "Renamed by Admin"},
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Renamed by Admin"


async def test_patch_user_promote_as_admin_succeeds(
    admin_authenticated_client: AsyncClient,
) -> None:
    register_resp = await admin_authenticated_client.post(
        REGISTER_URL,
        json={
            "email": "promote-me@example.com",
            "full_name": "Future Admin",
            "password": _VALID_PASSWORD,
        },
    )
    target_id = register_resp.json()["id"]

    response = await admin_authenticated_client.patch(
        _user_url(target_id),
        json={"is_admin": True},
    )

    assert response.status_code == 200
    assert response.json()["is_admin"] is True


async def test_patch_user_is_active_as_admin_deactivates(
    admin_authenticated_client: AsyncClient,
) -> None:
    register_resp = await admin_authenticated_client.post(
        REGISTER_URL,
        json={
            "email": "to-deactivate@example.com",
            "full_name": "Leaving User",
            "password": _VALID_PASSWORD,
        },
    )
    target_id = register_resp.json()["id"]

    response = await admin_authenticated_client.patch(
        _user_url(target_id),
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_patch_user_not_found_as_admin_returns_404(
    admin_authenticated_client: AsyncClient,
) -> None:
    response = await admin_authenticated_client.patch(
        _user_url(uuid.uuid4()),
        json={"full_name": "Phantom"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


# ---------------------------------------------------------------------------
# DELETE /api/v1/users/{user_id} — admin-only soft delete
# ---------------------------------------------------------------------------


async def test_delete_user_as_non_admin_returns_403(
    client_with_db: AsyncClient,
) -> None:
    token, _ = await _register_and_login(client_with_db, "regular@example.com")

    response = await client_with_db.delete(
        _user_url(uuid.uuid4()),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_REQUIRED"


async def test_delete_user_as_admin_returns_204_and_deactivates(
    admin_authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Soft-delete: row is retained (audit trail), ``is_active`` flips to false."""
    register_resp = await admin_authenticated_client.post(
        REGISTER_URL,
        json={
            "email": "soft-delete@example.com",
            "full_name": "Soft Delete Target",
            "password": _VALID_PASSWORD,
        },
    )
    target_id = uuid.UUID(register_resp.json()["id"])

    response = await admin_authenticated_client.delete(_user_url(target_id))

    assert response.status_code == 204
    assert response.content == b""

    # Row still exists (hard delete is unsupported) but is_active is False.
    user = await db_session.scalar(select(User).where(User.id == target_id))
    assert user is not None
    assert user.is_active is False


async def test_delete_user_self_as_admin_returns_409(
    admin_authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Admin cannot lock themselves out by deactivating their own account."""
    admin = await db_session.scalar(select(User).where(User.email == "admin-fixture@example.com"))
    assert admin is not None

    response = await admin_authenticated_client.delete(_user_url(admin.id))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CANNOT_DEACTIVATE_SELF"


async def test_delete_user_not_found_as_admin_returns_404(
    admin_authenticated_client: AsyncClient,
) -> None:
    response = await admin_authenticated_client.delete(_user_url(uuid.uuid4()))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"
