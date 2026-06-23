"""Tests for :class:`ZohoClient` — the CRM read path, retries, and error mapping.

All Zoho HTTP is mocked with ``respx``; the token provider is a lightweight
stub (no DB), and sleeps are a no-op so retry paths run instantly.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from httpx import Response

from app.clients.zoho.client import ZohoClient
from app.clients.zoho.endpoints import (
    MODULE_FIELDS,
    MODULE_LEADS,
    USERS_PATH,
    api_url,
    module_path,
)
from app.clients.zoho.errors import (
    ZohoNotFoundError,
    ZohoRateLimitError,
    ZohoServerError,
)
from app.core.config import get_settings

_SETTINGS = get_settings()
_USERS_URL = api_url(_SETTINGS.zoho_api_base_url, USERS_PATH)
_LEADS_URL = api_url(_SETTINGS.zoho_api_base_url, module_path(MODULE_LEADS))


class _StubTokenProvider:
    """Returns a token; ``force_refresh`` swaps to a second one and counts calls."""

    def __init__(self) -> None:
        self.access_token = "access-token-1"
        self.refresh_calls = 0

    async def get_access_token(self) -> str:
        return self.access_token

    async def force_refresh(self) -> str:
        self.refresh_calls += 1
        self.access_token = "access-token-2"
        return self.access_token


async def _no_sleep(_seconds: float) -> None:
    return None


def _make_client(http_client: httpx.AsyncClient, tokens: _StubTokenProvider) -> ZohoClient:
    return ZohoClient(_SETTINGS, http_client, tokens, sleep=_no_sleep)


async def test_get_users_parses_response() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        mock.get(_USERS_URL).mock(
            return_value=Response(200, json={"users": [{"id": "1", "email": "rep@example.com"}]})
        )
        client = _make_client(http_client, _StubTokenProvider())

        result = await client.get_users()

    assert result["users"][0]["email"] == "rep@example.com"


async def test_get_users_refreshes_token_once_on_401_then_succeeds() -> None:
    tokens = _StubTokenProvider()
    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        mock.get(_USERS_URL).mock(
            side_effect=[
                Response(401, json={"code": "INVALID_TOKEN"}),
                Response(200, json={"users": []}),
            ]
        )
        client = _make_client(http_client, tokens)

        result = await client.get_users()

    assert result == {"users": []}
    assert tokens.refresh_calls == 1


async def test_get_leads_paginates_until_no_more_records() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        mock.get(_LEADS_URL).mock(
            side_effect=[
                Response(200, json={"data": [{"id": "ZL1"}], "info": {"more_records": True}}),
                Response(200, json={"data": [{"id": "ZL2"}], "info": {"more_records": False}}),
            ]
        )
        client = _make_client(http_client, _StubTokenProvider())

        leads = await client.get_leads()

    assert [lead["id"] for lead in leads] == ["ZL1", "ZL2"]


async def test_get_leads_sends_required_fields_param() -> None:
    """Zoho's v8 API 400s a module GET with no ``fields`` (REQUIRED_PARAM_MISSING)."""
    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        route = mock.get(_LEADS_URL).mock(
            return_value=Response(200, json={"data": [], "info": {"more_records": False}})
        )
        client = _make_client(http_client, _StubTokenProvider())

        await client.get_leads()

    sent_params = dict(route.calls.last.request.url.params)
    assert sent_params["fields"] == MODULE_FIELDS[MODULE_LEADS]


async def test_get_leads_handles_empty_module() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        mock.get(_LEADS_URL).mock(return_value=Response(204))
        client = _make_client(http_client, _StubTokenProvider())

        assert await client.get_leads() == []


async def test_get_users_404_raises_not_found() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        mock.get(_USERS_URL).mock(return_value=Response(404, json={"code": "RESOURCE_NOT_FOUND"}))
        client = _make_client(http_client, _StubTokenProvider())

        with pytest.raises(ZohoNotFoundError):
            await client.get_users()


async def test_get_users_rate_limited_then_succeeds() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        mock.get(_USERS_URL).mock(
            side_effect=[
                Response(429, headers={"Retry-After": "0"}),
                Response(200, json={"users": []}),
            ]
        )
        client = _make_client(http_client, _StubTokenProvider())

        result = await client.get_users()

    assert result == {"users": []}


async def test_get_users_rate_limited_twice_raises() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        mock.get(_USERS_URL).mock(return_value=Response(429, headers={"Retry-After": "0"}))
        client = _make_client(http_client, _StubTokenProvider())

        with pytest.raises(ZohoRateLimitError):
            await client.get_users()


async def test_get_users_server_error_exhausts_retries_and_raises() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        route = mock.get(_USERS_URL).mock(return_value=Response(503))
        client = _make_client(http_client, _StubTokenProvider())

        with pytest.raises(ZohoServerError):
            await client.get_users()

    # First attempt + HTTP_MAX_RETRIES retries.
    assert route.call_count == _SETTINGS.http_max_retries + 1
