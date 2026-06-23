"""Zoho OAuth client — the refresh-token grant.

Exchanges a long-lived refresh token for a short-lived access token against
the data-centre accounts server. This is deliberately separate from
:class:`~app.clients.zoho.client.ZohoClient` (which calls the CRM API and
needs an access token): the OAuth call needs only the client credentials, so
splitting it avoids a circular dependency with the token service.

Note Zoho returns **HTTP 200 with an ``error`` field** for OAuth failures
(e.g. ``invalid_client``), so the body is inspected even on a 2xx status.
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel, Field

from app.clients.zoho.endpoints import OAUTH_TOKEN_PATH, accounts_url
from app.clients.zoho.errors import ZohoAuthError, ZohoServerError
from app.core.config import Settings

logger = logging.getLogger(__name__)


class ZohoTokenResponse(BaseModel):
    """Parsed success response from the Zoho token endpoint."""

    access_token: str
    # Zoho's refresh-token grant does not return a new refresh token.
    expires_in: int = Field(gt=0)
    token_type: str = "Bearer"
    scope: str | None = None
    api_domain: str | None = None


class ZohoOAuthClient:
    """Thin client for the Zoho OAuth token endpoint.

    Stateless: it holds only configuration and a shared ``httpx.AsyncClient``.
    Persistence of the resulting token is the token service's job.
    """

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http_client

    async def refresh(self, refresh_token: str) -> ZohoTokenResponse:
        """Exchange ``refresh_token`` for a fresh access token.

        Raises :class:`ZohoAuthError` when Zoho rejects the credentials/token
        and :class:`ZohoServerError` on a 5xx or a transport failure.
        """
        url = accounts_url(self._settings.zoho_accounts_url, OAUTH_TOKEN_PATH)
        form = {
            "refresh_token": refresh_token,
            "client_id": self._settings.zoho_client_id,
            "client_secret": self._settings.zoho_client_secret,
            "grant_type": "refresh_token",
        }
        try:
            response = await self._http.post(url, data=form)
        except httpx.HTTPError as exc:
            raise ZohoServerError(f"Zoho token endpoint unreachable: {exc}") from exc

        if response.status_code >= 500:
            raise ZohoServerError(
                "Zoho token endpoint returned a server error",
                status_code=response.status_code,
            )

        body = _safe_json(response)
        # OAuth failures arrive as 200 + {"error": "..."} OR as a 4xx.
        if "error" in body:
            raise ZohoAuthError(
                f"Zoho token refresh failed: {body['error']}",
                status_code=response.status_code,
                zoho_code=str(body["error"]),
            )
        if response.status_code >= 400:
            raise ZohoAuthError("Zoho token refresh failed", status_code=response.status_code)

        token = ZohoTokenResponse.model_validate(body)
        logger.info("zoho_token_refreshed", extra={"expires_in": token.expires_in})
        return token


def _safe_json(response: httpx.Response) -> dict[str, object]:
    """Return the JSON body as a dict, or an ``error`` marker if unparseable."""
    try:
        parsed = response.json()
    except ValueError:
        return {"error": "non_json_response"}
    if not isinstance(parsed, dict):
        return {"error": "unexpected_response_shape"}
    return parsed
