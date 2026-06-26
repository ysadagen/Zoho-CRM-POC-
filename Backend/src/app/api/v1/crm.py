"""CRM integration endpoints — proxies frontend requests to the Integration Layer."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.clients.integration_layer import IntegrationLayerClient
from app.core.config import Settings, get_settings
from app.dependencies.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/crm", tags=["crm"])

_CurrentUser = Annotated[User, Depends(get_current_user)]
_Settings = Annotated[Settings, Depends(get_settings)]


@router.post("/trigger-ingest", summary="Trigger a Zoho → app ingest cycle")
async def trigger_ingest(current_user: _CurrentUser, settings: _Settings) -> dict[str, Any]:
    """Proxy the ingest-run request to the Integration Layer.

    JWT-protected — only authenticated app users can trigger a sync. The
    Integration Layer is called with its internal API key (never exposed to
    the browser). Returns whatever the IL responds with.
    """
    il = IntegrationLayerClient(settings)
    return await il.trigger_ingest()
