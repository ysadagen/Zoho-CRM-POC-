"""BackendClient — calls the Inventory Backend's internal ingest endpoints.

The IL's second (and only inbound-data) outbound integration: it writes
Zoho-sourced records into the Backend via its API, never touching
``inventory_db`` directly. Authenticated with the shared internal API key
(the Backend validates it as ``INTEGRATION_LAYER_API_KEY``).

Returns parsed dicts to the ingest service and maps non-2xx responses to the
``clients/backend/errors`` hierarchy. A single attempt per call: the Backend
is an internal, reliable dependency, and a failed ingest write is recorded in
``sync_logs`` for re-drive rather than retried inline.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.clients.backend.errors import (
    BackendError,
    BackendNotFoundError,
    BackendUnavailableError,
    BackendValidationError,
)
from app.core.config import Settings

logger = logging.getLogger(__name__)

INTERNAL_API_KEY_HEADER = "X-Internal-API-Key"
_INGEST_PREFIX = "/api/v1/ingest"


class BackendClient:
    """Thin client for the Backend ingest API."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http_client
        self._base = f"{settings.backend_base_url.rstrip('/')}{_INGEST_PREFIX}"

    async def list_users(self) -> list[dict[str, Any]]:
        """Return the Backend's users for owner-email resolution."""
        body = await self._request("GET", "/users")
        items = body.get("items", [])
        return items if isinstance(items, list) else []

    async def create_lead(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a lead; returns ``{id, lead_number, stage}``."""
        return await self._request("POST", "/leads", json=payload)

    async def update_lead(self, lead_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update an existing lead; returns ``{id, lead_number, stage}``."""
        return await self._request("PATCH", f"/leads/{lead_id}", json=payload)

    async def create_activity(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a sales activity; returns ``{id}``."""
        return await self._request("POST", "/activities", json=payload)

    async def _request(
        self, method: str, path: str, *, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{self._base}{path}"
        headers = {INTERNAL_API_KEY_HEADER: self._settings.internal_api_key}
        try:
            response = await self._http.request(method, url, json=json, headers=headers)
        except httpx.HTTPError as exc:
            raise BackendUnavailableError(f"Backend unreachable: {exc}") from exc

        if response.status_code >= 500 or response.status_code == httpx.codes.SERVICE_UNAVAILABLE:
            raise BackendUnavailableError(
                "Backend ingest unavailable", status_code=response.status_code
            )
        if response.status_code == httpx.codes.NOT_FOUND:
            raise BackendNotFoundError("Backend reported a missing reference", status_code=404)
        if response.status_code == httpx.codes.UNPROCESSABLE_ENTITY:
            raise BackendValidationError("Backend rejected the payload", status_code=422)
        if response.status_code >= 400:
            raise BackendError(
                f"Backend returned an error ({response.status_code})",
                status_code=response.status_code,
            )
        return _parse_body(response)


def _parse_body(response: httpx.Response) -> dict[str, Any]:
    """Return the JSON body as a dict; an empty/no-content response is ``{}``."""
    if response.status_code == httpx.codes.NO_CONTENT or not response.content:
        return {}
    try:
        parsed = response.json()
    except ValueError as exc:
        raise BackendError("Backend returned a non-JSON response") from exc
    if not isinstance(parsed, dict):
        raise BackendError("Backend returned an unexpected response shape")
    return parsed
