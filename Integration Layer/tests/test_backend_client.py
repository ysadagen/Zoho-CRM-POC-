"""Tests for :class:`BackendClient` — the IL → Backend ingest calls.

``respx`` mocks the Backend; no real Backend is contacted. Verifies the
internal API key header is sent, success bodies parse, and non-2xx responses
map to the narrow ``clients/backend/errors`` hierarchy.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from httpx import Response

from app.clients.backend.client import INTERNAL_API_KEY_HEADER, BackendClient
from app.clients.backend.errors import (
    BackendNotFoundError,
    BackendUnavailableError,
    BackendValidationError,
)
from app.core.config import get_settings

_SETTINGS = get_settings()
_INGEST = f"{_SETTINGS.backend_base_url.rstrip('/')}/api/v1/ingest"


async def test_list_users_returns_items_and_sends_api_key() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        route = mock.get(f"{_INGEST}/users").mock(
            return_value=Response(200, json={"items": [{"id": "u1", "email": "a@b.com"}]})
        )
        users = await BackendClient(_SETTINGS, http_client).list_users()

    assert users == [{"id": "u1", "email": "a@b.com"}]
    assert route.calls.last.request.headers[INTERNAL_API_KEY_HEADER] == _SETTINGS.internal_api_key


async def test_create_lead_returns_body() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        mock.post(f"{_INGEST}/leads").mock(
            return_value=Response(201, json={"id": "L1", "lead_number": "LD-1", "stage": "NEW"})
        )
        result = await BackendClient(_SETTINGS, http_client).create_lead({"contact_name": "X"})

    assert result["id"] == "L1"


async def test_404_maps_to_not_found() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        mock.patch(f"{_INGEST}/leads/L1").mock(return_value=Response(404))
        with pytest.raises(BackendNotFoundError):
            await BackendClient(_SETTINGS, http_client).update_lead("L1", {"stage": "WON"})


async def test_422_maps_to_validation_error() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        mock.post(f"{_INGEST}/activities").mock(return_value=Response(422))
        with pytest.raises(BackendValidationError):
            await BackendClient(_SETTINGS, http_client).create_activity({"type": "CALL"})


async def test_503_maps_to_unavailable() -> None:
    async with httpx.AsyncClient() as http_client, respx.mock as mock:
        mock.get(f"{_INGEST}/users").mock(return_value=Response(503))
        with pytest.raises(BackendUnavailableError):
            await BackendClient(_SETTINGS, http_client).list_users()
