"""FastAPI providers for the Zoho collaborators.

Wires the per-request ``httpx.AsyncClient`` and builds the OAuth client, token
service, and Zoho API client from it. One HTTP client is created per request
and closed cleanly on teardown — appropriate for this service's low call
volume (3 Zoho users, periodic ingest); connection pooling via an app-lifespan
client can be introduced later if volume grows, without touching callers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.zoho.client import ZohoClient
from app.clients.zoho.oauth import ZohoOAuthClient
from app.core.config import Settings, get_settings
from app.dependencies.db import get_db
from app.services.token_service import TokenService


async def get_zoho_http_client() -> AsyncIterator[httpx.AsyncClient]:
    """Yield a request-scoped ``httpx.AsyncClient`` with the configured timeout."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http_client:
        yield http_client


def get_oauth_client(
    http_client: Annotated[httpx.AsyncClient, Depends(get_zoho_http_client)],
) -> ZohoOAuthClient:
    """Build the Zoho OAuth client for this request."""
    return ZohoOAuthClient(get_settings(), http_client)


def get_token_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    oauth_client: Annotated[ZohoOAuthClient, Depends(get_oauth_client)],
) -> TokenService:
    """Build the token service bound to this request's DB session."""
    settings: Settings = get_settings()
    return TokenService(session=session, oauth_client=oauth_client, settings=settings)


def get_zoho_client(
    http_client: Annotated[httpx.AsyncClient, Depends(get_zoho_http_client)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> ZohoClient:
    """Build the Zoho CRM API client for this request."""
    return ZohoClient(get_settings(), http_client, token_service)
