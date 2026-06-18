"""Intelligence endpoints — score reads, beat plan, config admin, recompute.

All under ``/intelligence``. Read endpoints require any authenticated user;
the administration endpoints (config versioning, recompute) require admin.
This module grows over Phase 2B; 2B.0 wires the scoring-config admin surface
(§9.5).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import require_admin
from app.models.scoring_config import ScoringEngine
from app.models.user import User
from app.schemas.intelligence import (
    ScoringConfigCreate,
    ScoringConfigList,
    ScoringConfigOut,
)
from app.services.scoring.config_service import ScoringConfigService

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

_Session = Annotated[AsyncSession, Depends(get_db)]
_AdminUser = Annotated[User, Depends(require_admin)]


@router.get(
    "/configs",
    response_model=ScoringConfigList,
    summary="List scoring-config versions (admin)",
)
async def list_configs(
    session: _Session,
    current_user: _AdminUser,
    engine: Annotated[ScoringEngine | None, Query()] = None,
) -> ScoringConfigList:
    """List config versions (active flagged). Filter by ``engine``."""
    configs = await ScoringConfigService(session).list_configs(engine=engine)
    return ScoringConfigList(
        items=[ScoringConfigOut.model_validate(c) for c in configs],
        total=len(configs),
    )


@router.post(
    "/configs",
    response_model=ScoringConfigOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create + activate a new scoring-config version (admin)",
)
async def create_config(
    payload: ScoringConfigCreate,
    session: _Session,
    current_user: _AdminUser,
) -> ScoringConfigOut:
    """Create a new version for an engine and activate it (deactivating the
    prior active row). ``params`` is validated against the engine's schema —
    422 ``INVALID_CONFIG_PARAMS`` on violation (weights must sum to 1, bands
    contiguous, no unknown keys)."""
    config = await ScoringConfigService(session).create_and_activate(
        payload.engine,
        payload.params,
        description=payload.description,
        actor_id=current_user.id,
    )
    return ScoringConfigOut.model_validate(config)
