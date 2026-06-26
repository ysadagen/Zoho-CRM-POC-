"""FastAPI providers for the Track B sync pipeline."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.zoho.client import ZohoClient
from app.core.config import get_settings
from app.dependencies.db import get_db
from app.dependencies.zoho import get_zoho_client
from app.services.sync_service import SyncService


def get_sync_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    zoho_client: Annotated[ZohoClient, Depends(get_zoho_client)],
) -> SyncService:
    """Build the sync service bound to this request's session."""
    return SyncService(
        session=session,
        settings=get_settings(),
        zoho_client=zoho_client,
    )
