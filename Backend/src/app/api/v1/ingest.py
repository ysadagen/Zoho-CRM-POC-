"""Internal Zoho-ingest endpoints (Track A).

Called only by the Integration Layer (service-to-service), never the browser.
Authenticated by the shared internal API key and gated by ``ZOHO_INGEST_ENABLED``
— both applied as router-level dependencies, so every route here is protected
uniformly. Handlers stay thin: parse → service → return.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import require_ingest_enabled, require_internal_api_key
from app.schemas.ingest import (
    ActivityIngest,
    ActivityIngestResult,
    IngestUserList,
    IngestUserRead,
    LeadIngestCreate,
    LeadIngestResult,
    LeadIngestUpdate,
)
from app.services.ingest_service import IngestService

router = APIRouter(
    prefix="/ingest",
    tags=["ingest"],
    dependencies=[Depends(require_internal_api_key), Depends(require_ingest_enabled)],
)

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/users", response_model=IngestUserList, summary="List app users for owner resolution")
async def list_users(session: DbSession) -> IngestUserList:
    """Return all app users so the IL can resolve a Zoho owner email → user."""
    users = await IngestService(session).list_users()
    return IngestUserList(items=[IngestUserRead.model_validate(u) for u in users])


@router.post(
    "/leads",
    response_model=LeadIngestResult,
    status_code=status.HTTP_201_CREATED,
    summary="Create a lead mirrored from Zoho",
)
async def create_lead(payload: LeadIngestCreate, session: DbSession) -> LeadIngestResult:
    """Create a Zoho-sourced lead (owner already resolved to a local id)."""
    lead = await IngestService(session).create_lead(payload)
    return LeadIngestResult.model_validate(lead)


@router.patch(
    "/leads/{lead_id}",
    response_model=LeadIngestResult,
    summary="Update an ingested lead (stage / owner / won Deal)",
)
async def update_lead(
    lead_id: uuid.UUID, payload: LeadIngestUpdate, session: DbSession
) -> LeadIngestResult:
    """Apply a mirrored update to an existing lead."""
    lead = await IngestService(session).update_lead(lead_id, payload)
    return LeadIngestResult.model_validate(lead)


@router.post(
    "/activities",
    response_model=ActivityIngestResult,
    status_code=status.HTTP_201_CREATED,
    summary="Create a sales activity mirrored from Zoho",
)
async def create_activity(payload: ActivityIngest, session: DbSession) -> ActivityIngestResult:
    """Create a Zoho-sourced activity (Call/Meeting/Task → effort signal)."""
    activity = await IngestService(session).create_activity(payload)
    return ActivityIngestResult.model_validate(activity)
