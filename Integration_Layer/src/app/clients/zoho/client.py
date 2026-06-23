"""ZohoClient — the only place in the codebase that calls the Zoho CRM API.

A thin wrapper over ``httpx.AsyncClient`` that:

* injects the ``Authorization: Zoho-oauthtoken <token>`` header (the token is
  sourced from the token service, never held here),
* retries 5xx and transport failures with exponential backoff + jitter, up to
  ``HTTP_MAX_RETRIES`` (CLAUDE.md §11),
* refreshes the access token once and retries once on a 401,
* honours ``Retry-After`` once on a 429, then raises :class:`ZohoRateLimitError`,
* maps every other Zoho failure to the narrow ``clients/zoho/errors`` hierarchy,
* returns parsed dicts to services — never raw ``httpx.Response`` objects.

It never retries other 4xx. The token service is a collaborator (injected) so
the client itself stays free of persistence concerns.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import httpx

from app.clients.zoho.endpoints import (
    MODULE_CALLS,
    MODULE_DEALS,
    MODULE_EVENTS,
    MODULE_FIELDS,
    MODULE_LEADS,
    MODULE_TASKS,
    USERS_PATH,
    api_url,
    module_path,
)
from app.clients.zoho.errors import (
    ZohoAPIError,
    ZohoAuthError,
    ZohoNotFoundError,
    ZohoRateLimitError,
    ZohoServerError,
)
from app.core.config import Settings
from app.utils.backoff import backoff_delay_seconds

logger = logging.getLogger(__name__)


class AccessTokenProvider(Protocol):
    """The slice of the token service the client depends on.

    Declared as a Protocol so the client is decoupled from the concrete
    service and trivial to substitute in tests.
    """

    async def get_access_token(self) -> str: ...

    async def force_refresh(self) -> str: ...


class ZohoClient:
    """Authenticated, retrying client for the Zoho CRM API."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient,
        token_provider: AccessTokenProvider,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._settings = settings
        self._http = http_client
        self._tokens = token_provider
        self._sleep = sleep

    # Records-per-page on a module GET (Zoho's max is 200). A safety cap on the
    # page loop guards against an unbounded pull; well above any POC volume.
    _PAGE_SIZE = 200
    _MAX_PAGES = 50

    async def get_users(self, *, user_type: str = "AllUsers") -> dict[str, Any]:
        """Read CRM users. ``user_type`` selects the cohort (e.g. ``CurrentUser``)."""
        url = api_url(self._settings.zoho_api_base_url, USERS_PATH)
        return await self._request("GET", url, params={"type": user_type})

    async def get_leads(self) -> list[dict[str, Any]]:
        """Read all Lead records."""
        return await self._get_records(MODULE_LEADS)

    async def get_calls(self) -> list[dict[str, Any]]:
        """Read all Call records (→ CALL activities)."""
        return await self._get_records(MODULE_CALLS)

    async def get_events(self) -> list[dict[str, Any]]:
        """Read all Event records (meetings → MEETING/VISIT activities)."""
        return await self._get_records(MODULE_EVENTS)

    async def get_tasks(self) -> list[dict[str, Any]]:
        """Read all Task records (→ FOLLOW_UP activities)."""
        return await self._get_records(MODULE_TASKS)

    async def get_deals(self) -> list[dict[str, Any]]:
        """Read all Deal records (Closed-Won → lead won_value/won_at)."""
        return await self._get_records(MODULE_DEALS)

    async def _get_records(self, module: str) -> list[dict[str, Any]]:
        """Page through a module's records and return them all.

        Zoho returns ``{"data": [...], "info": {"more_records": bool}}`` (or a
        204 with no body when the module is empty). Pagination follows
        ``more_records`` up to a hard page cap so a pull is always bounded.
        """
        url = api_url(self._settings.zoho_api_base_url, module_path(module))
        fields = MODULE_FIELDS[module]
        records: list[dict[str, Any]] = []
        for page in range(1, self._MAX_PAGES + 1):
            body = await self._request(
                "GET",
                url,
                params={"page": page, "per_page": self._PAGE_SIZE, "fields": fields},
            )
            data = body.get("data")
            if isinstance(data, list):
                records.extend(item for item in data if isinstance(item, dict))
            info = body.get("info")
            more = bool(info.get("more_records")) if isinstance(info, dict) else False
            if not more:
                break
        else:
            logger.warning("zoho_records_page_cap_hit", extra={"module": module})
        return records

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a Zoho API request with auth, retry, and error mapping."""
        token = await self._tokens.get_access_token()
        max_attempts = self._settings.http_max_retries + 1
        base_ms = self._settings.http_backoff_base_ms
        attempt = 1
        token_refreshed = False
        rate_limit_retried = False

        while True:
            try:
                response = await self._http.request(
                    method, url, params=params, headers=self._auth_headers(token)
                )
            except httpx.HTTPError as exc:
                if attempt >= max_attempts:
                    raise ZohoServerError(f"Zoho request failed after retries: {exc}") from exc
                await self._sleep(backoff_delay_seconds(attempt=attempt, base_ms=base_ms))
                attempt += 1
                continue

            status = response.status_code

            if status == httpx.codes.UNAUTHORIZED and not token_refreshed:
                logger.info("zoho_token_refresh_on_401", extra={"url": url})
                token = await self._tokens.force_refresh()
                token_refreshed = True
                continue  # retry once with the new token; not a transient-failure attempt
            if status == httpx.codes.UNAUTHORIZED:
                raise ZohoAuthError("Zoho rejected the access token after refresh", status_code=401)

            if status == httpx.codes.TOO_MANY_REQUESTS:
                retry_after = _parse_retry_after(response)
                if not rate_limit_retried:
                    rate_limit_retried = True
                    delay = (
                        retry_after
                        if retry_after is not None
                        else backoff_delay_seconds(attempt=attempt, base_ms=base_ms)
                    )
                    logger.warning("zoho_rate_limited_retry", extra={"retry_after": retry_after})
                    await self._sleep(delay)
                    continue
                raise ZohoRateLimitError("Zoho rate limit exceeded", retry_after=retry_after)

            if status >= 500:
                if attempt >= max_attempts:
                    raise ZohoServerError("Zoho server error after retries", status_code=status)
                logger.warning(
                    "zoho_server_error_retry",
                    extra={"status_code": status, "attempt": attempt},
                )
                await self._sleep(backoff_delay_seconds(attempt=attempt, base_ms=base_ms))
                attempt += 1
                continue

            if status == httpx.codes.NOT_FOUND:
                raise ZohoNotFoundError("Zoho resource not found", status_code=404)
            if status >= 400:
                raise ZohoAPIError(f"Zoho returned an error ({status})", status_code=status)

            return _parse_body(response)

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Zoho-oauthtoken {token}"}


def _parse_body(response: httpx.Response) -> dict[str, Any]:
    """Return the JSON body as a dict; an empty/no-content response is ``{}``."""
    if response.status_code == httpx.codes.NO_CONTENT or not response.content:
        return {}
    try:
        parsed = response.json()
    except ValueError as exc:
        raise ZohoAPIError("Zoho returned a non-JSON response") from exc
    if not isinstance(parsed, dict):
        raise ZohoAPIError("Zoho returned an unexpected response shape")
    return parsed


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Parse the ``Retry-After`` header as integer seconds, if present and numeric."""
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return float(int(raw))
    except ValueError:
        # HTTP-date form is not used by Zoho; fall back to computed backoff.
        return None
