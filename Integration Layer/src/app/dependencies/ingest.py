"""FastAPI providers for the ingest pipeline.

Builds the Backend client and the ingest service for a request, reusing the
same request-scoped ``httpx.AsyncClient`` as the Zoho collaborators.
"""

from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.backend.client import BackendClient
from app.clients.zoho.client import ZohoClient
from app.core.config import get_settings
from app.dependencies.db import get_db
from app.dependencies.zoho import get_zoho_client, get_zoho_http_client
from app.services.ingest_service import IngestService


def get_backend_client(
    http_client: Annotated[httpx.AsyncClient, Depends(get_zoho_http_client)],
) -> BackendClient:
    """Build the Backend ingest client for this request."""
    return BackendClient(get_settings(), http_client)


def get_ingest_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    zoho_client: Annotated[ZohoClient, Depends(get_zoho_client)],
    backend_client: Annotated[BackendClient, Depends(get_backend_client)],
) -> IngestService:
    """Build the ingest orchestrator bound to this request's session."""
    return IngestService(
        session=session,
        settings=get_settings(),
        zoho_client=zoho_client,
        backend_client=backend_client,
    )
