"""Tests for POST /api/v1/crm/trigger-ingest.

The endpoint is a JWT-protected proxy: it accepts an authenticated request
from the frontend, calls the Integration Layer's ingest/run endpoint with the
internal API key, and returns the IL's response. The IL call is mocked with
respx so no real network traffic occurs.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

CRM_TRIGGER_URL = "/api/v1/crm/trigger-ingest"


async def test_trigger_ingest_requires_auth(client_with_db: AsyncClient) -> None:
    response = await client_with_db.post(CRM_TRIGGER_URL)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


async def test_trigger_ingest_returns_il_response_on_success(
    authenticated_client: AsyncClient,
) -> None:
    """A successful IL call returns the ingest summary to the caller."""
    il_response = {
        "ok": True,
        "enabled": True,
        "leads_created": 3,
        "leads_updated": 1,
        "activities_created": 5,
        "deals_applied": 1,
        "parked": 0,
        "failed": 0,
    }

    with patch(
        "app.clients.integration_layer.IntegrationLayerClient.trigger_ingest",
        new_callable=AsyncMock,
        return_value=il_response,
    ):
        response = await authenticated_client.post(CRM_TRIGGER_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["leads_created"] == 3


async def test_trigger_ingest_returns_non_ok_when_il_fails(
    authenticated_client: AsyncClient,
) -> None:
    """When the IL returns a non-2xx, trigger_ingest returns ok=False; endpoint still 200."""
    il_response = {"ok": False, "status": 503, "detail": "IL unavailable"}

    with patch(
        "app.clients.integration_layer.IntegrationLayerClient.trigger_ingest",
        new_callable=AsyncMock,
        return_value=il_response,
    ):
        response = await authenticated_client.post(CRM_TRIGGER_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False


async def test_trigger_ingest_returns_error_on_network_failure(
    authenticated_client: AsyncClient,
) -> None:
    """A network error to the IL still returns a safe dict (never raises to the caller)."""
    il_response = {"ok": False, "error": "connection refused"}

    with patch(
        "app.clients.integration_layer.IntegrationLayerClient.trigger_ingest",
        new_callable=AsyncMock,
        return_value=il_response,
    ):
        response = await authenticated_client.post(CRM_TRIGGER_URL)

    assert response.status_code == 200
    assert response.json()["ok"] is False
