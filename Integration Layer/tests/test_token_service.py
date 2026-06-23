"""Tests for :class:`TokenService` — the get-or-refresh OAuth flow.

``respx`` mocks the Zoho token endpoint; no real Zoho is contacted. The
service is exercised against a real (transactional) DB session so the
persistence behaviour is covered end-to-end.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx
import respx
from httpx import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.zoho.endpoints import OAUTH_TOKEN_PATH, accounts_url
from app.clients.zoho.oauth import ZohoOAuthClient
from app.core.config import get_settings
from app.models.zoho_token import ZohoToken
from app.repositories.zoho_token_repo import ZohoTokenRepository
from app.services.token_service import TokenService

_SETTINGS = get_settings()
_TOKEN_URL = accounts_url(_SETTINGS.zoho_accounts_url, OAUTH_TOKEN_PATH)


def _token_response(access_token: str) -> Response:
    return Response(
        200,
        json={
            "access_token": access_token,
            "expires_in": 3600,
            "token_type": "Bearer",
            "api_domain": "https://www.zohoapis.in",
            "scope": "ZohoCRM.users.READ",
        },
    )


async def _build_service(session: AsyncSession, http_client: httpx.AsyncClient) -> TokenService:
    oauth = ZohoOAuthClient(_SETTINGS, http_client)
    return TokenService(session=session, oauth_client=oauth, settings=_SETTINGS)


async def test_force_refresh_persists_token_row(db_session: AsyncSession) -> None:
    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        mock.post(_TOKEN_URL).mock(return_value=_token_response("brand-new-token"))
        service = await _build_service(db_session, http_client)

        token = await service.force_refresh()

    assert token == "brand-new-token"
    stored = await ZohoTokenRepository(db_session).get()
    assert stored is not None
    assert stored.access_token == "brand-new-token"
    # No stored row existed, so the bootstrap refresh token was used + carried.
    assert stored.refresh_token == _SETTINGS.zoho_refresh_token


async def test_get_access_token_returns_cached_when_fresh(
    db_session: AsyncSession,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token(access_token="cached-token", expires_in_seconds=3600)

    async with httpx.AsyncClient() as http_client, respx.mock(assert_all_called=False) as mock:
        route = mock.post(_TOKEN_URL)
        service = await _build_service(db_session, http_client)

        token = await service.get_access_token()

    assert token == "cached-token"
    assert not route.called  # fresh token → no refresh call


async def test_get_access_token_refreshes_when_expired(
    db_session: AsyncSession,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token(
        access_token="stale-token",
        refresh_token="long-lived-refresh",
        expires_in_seconds=-10,
    )

    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        route = mock.post(_TOKEN_URL).mock(return_value=_token_response("refreshed-token"))
        service = await _build_service(db_session, http_client)

        token = await service.get_access_token()

    assert token == "refreshed-token"
    assert route.called
    stored = await ZohoTokenRepository(db_session).get()
    assert stored is not None
    assert stored.access_token == "refreshed-token"
    # The stored refresh token is reused (Zoho does not reissue one).
    assert stored.refresh_token == "long-lived-refresh"
