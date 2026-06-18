"""Pydantic schemas for the intelligence layer (§9.6).

This module grows over Phase 2B: 2B.0 adds the scoring-config admin shapes;
later slices append the per-engine score read shapes and the recompute
envelope. Every ``*Create`` forbids extra keys so a typo'd param key surfaces
as a validation error rather than silently dropping.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.scoring_config import ScoringEngine

__all__ = [
    "ScoringConfigCreate",
    "ScoringConfigList",
    "ScoringConfigOut",
]


class ScoringConfigOut(BaseModel):
    """A scoring config version as returned to admins."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    engine: ScoringEngine
    version: int
    is_active: bool
    description: str | None
    params: dict[str, Any]
    created_at: datetime


class ScoringConfigList(BaseModel):
    """Envelope for ``GET /intelligence/configs`` (not paginated — few rows)."""

    items: list[ScoringConfigOut]
    total: int


class ScoringConfigCreate(BaseModel):
    """Create a new config version for an engine and activate it.

    ``version`` is assigned server-side (max existing + 1); ``params`` is
    validated against the engine's shape in the service (422 on violation).
    """

    model_config = ConfigDict(extra="forbid")

    engine: ScoringEngine
    params: dict[str, Any]
    description: str | None = None
