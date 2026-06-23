"""Tests for the health endpoints.

``/health`` is a pure liveness probe. ``/health/zoho`` proves Zoho
authentication works by obtaining an access token — credit-safe (no CRM read),
and never hitting real Zoho (``respx`` mocks the OAuth endpoint).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import respx
from httpx import AsyncClient, Response

from app.clients.zoho.endpoints import OAUTH_TOKEN_PATH, accounts_url
from app.core.config import get_settings
from app.models.zoho_token import ZohoToken

_TOKEN_URL = accounts_url(get_settings().zoho_accounts_url, OAUTH_TOKEN_PATH)


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_zoho_with_fresh_stored_token_does_not_call_zoho(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token(expires_in_seconds=3600)

    with respx.mock(assert_all_called=False) as mock:
        token_route = mock.post(_TOKEN_URL)
        response = await client_with_db.get("/health/zoho")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "zoho": "reachable"}
    assert not token_route.called  # a valid stored token spends no API credit


async def test_health_zoho_refreshes_when_no_token_stored(
    client_with_db: AsyncClient,
) -> None:
    with respx.mock as mock:
        mock.post(_TOKEN_URL).mock(
            return_value=Response(
                200,
                json={
                    "access_token": "fresh-access-token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                    "api_domain": "https://www.zohoapis.in",
                    "scope": "ZohoCRM.users.READ",
                },
            )
        )
        response = await client_with_db.get("/health/zoho")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "zoho": "reachable"}


async def test_health_zoho_returns_503_when_refresh_rejected(
    client_with_db: AsyncClient,
) -> None:
    # Zoho signals OAuth failure as HTTP 200 + an ``error`` field.
    with respx.mock as mock:
        mock.post(_TOKEN_URL).mock(return_value=Response(200, json={"error": "invalid_client"}))
        response = await client_with_db.get("/health/zoho")

    assert response.status_code == 503
    body = response.json()["error"]
    assert body["code"] == "ZOHO_UNAVAILABLE"
    assert body["request_id"] is not None
