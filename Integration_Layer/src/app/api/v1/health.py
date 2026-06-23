"""Health endpoints.

``GET /health`` is liveness — "is this process up?" — and never touches a
dependency. ``GET /health/zoho`` confirms we can authenticate to Zoho by
obtaining a valid access token (refreshing only if the stored one is missing
or near expiry). It deliberately does **not** make a CRM read: Zoho Free has a
finite daily API-credit budget and a probe can fire every few seconds, so
spending a credit per probe would be reckless. A failure to obtain a token is
surfaced as 503 so an orchestrator routes traffic away until Zoho recovers.

Both probes are public, mirroring the Backend's liveness/readiness probes.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from app.clients.zoho.errors import ZohoError
from app.core.exceptions import UpstreamUnavailableError
from app.dependencies.zoho import get_token_service
from app.schemas.health import HealthStatus, ZohoHealthStatus
from app.services.token_service import TokenService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus, summary="Liveness probe")
async def health() -> HealthStatus:
    """Return 200 OK if the process is running. No dependency checks."""
    return HealthStatus(status="ok")


@router.get("/health/zoho", response_model=ZohoHealthStatus, summary="Zoho connectivity probe")
async def health_zoho(
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> ZohoHealthStatus:
    """Return 200 only if a valid Zoho access token can be obtained.

    Raises 503 ``UPSTREAM_UNAVAILABLE`` when Zoho rejects our credentials or is
    unreachable. Credit-safe: at most one token refresh, and only when the
    stored token is missing or near expiry.
    """
    try:
        await token_service.get_access_token()
    except ZohoError as exc:
        logger.warning("zoho_health_check_failed", extra={"error": exc.message})
        raise UpstreamUnavailableError(
            "Could not obtain a Zoho access token", code="ZOHO_UNAVAILABLE"
        ) from exc
    return ZohoHealthStatus(status="ok", zoho="reachable")
