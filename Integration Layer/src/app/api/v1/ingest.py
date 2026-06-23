"""Ingest endpoints (Track A — Zoho → app).

Driven by a scheduled trigger or an internal call, never the frontend. Both
routes require the internal API key. ``POST /ingest/run`` performs a full
idempotent pull cycle (a no-op when ``ZOHO_INGEST_ENABLED`` is off);
``GET /ingest/status`` returns the recent sync-log feed.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies.auth import require_internal_api_key
from app.dependencies.ingest import get_ingest_service
from app.schemas.ingest import IngestRunSummary, IngestStatus
from app.services.ingest_service import IngestService

router = APIRouter(
    prefix="/ingest",
    tags=["ingest"],
    dependencies=[Depends(require_internal_api_key)],
)

IngestSvc = Annotated[IngestService, Depends(get_ingest_service)]


@router.post("/run", response_model=IngestRunSummary, summary="Run a Zoho → app ingest cycle")
async def run_ingest(service: IngestSvc) -> IngestRunSummary:
    """Pull Zoho leads/activities/deals and write them to the Backend."""
    return await service.run()


@router.get("/status", response_model=IngestStatus, summary="Recent ingest/sync activity")
async def ingest_status(service: IngestSvc) -> IngestStatus:
    """Return the most recent sync-log rows (newest first)."""
    return await service.status()
