"""Response schemas for the ingest endpoints (Track A)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IngestRunSummary(BaseModel):
    """Outcome counts from a single ingest run.

    ``enabled=False`` means ``ZOHO_INGEST_ENABLED`` is off and the run was a
    no-op — every count is zero and nothing was pulled or written.
    """

    enabled: bool
    leads_created: int = 0
    leads_updated: int = 0
    activities_created: int = 0
    activities_skipped: int = 0
    deals_applied: int = 0
    parked: int = 0
    failed: int = 0


class SyncLogEntry(BaseModel):
    """One sync-log row, surfaced on the status feed."""

    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    direction: str
    entity_type: str | None
    status: str
    operation: str | None
    zoho_id: str | None
    local_id: str | None
    error_code: str | None


class IngestStatus(BaseModel):
    """Recent ingest/sync activity (newest first)."""

    recent: list[SyncLogEntry]
