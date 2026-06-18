"""Data-access layer for ``scoring_configs``.

All SQL touching scoring configs lives here. The service composes these to
validate, version, and activation-swap configs in one transaction.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scoring_config import ScoringConfig, ScoringEngine


class ScoringConfigRepository:
    """Repository for :class:`ScoringConfig`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, config_id: uuid.UUID) -> ScoringConfig | None:
        stmt = select(ScoringConfig).where(ScoringConfig.id == config_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_active(self, engine: ScoringEngine) -> ScoringConfig | None:
        """Return the single active config for ``engine`` (or None)."""
        stmt = select(ScoringConfig).where(
            ScoringConfig.engine == engine,
            ScoringConfig.is_active.is_(True),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_(self, *, engine: ScoringEngine | None = None) -> list[ScoringConfig]:
        """Return config versions, newest engine/version first."""
        stmt: Select[tuple[ScoringConfig]] = select(ScoringConfig)
        if engine is not None:
            stmt = stmt.where(ScoringConfig.engine == engine)
        stmt = stmt.order_by(ScoringConfig.engine, ScoringConfig.version.desc())
        return list((await self._session.execute(stmt)).scalars().all())

    async def max_version(self, engine: ScoringEngine) -> int:
        """Highest existing version for ``engine`` (0 if none exist)."""
        stmt = select(func.coalesce(func.max(ScoringConfig.version), 0)).where(
            ScoringConfig.engine == engine
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def deactivate_active(self, engine: ScoringEngine) -> None:
        """Clear the active flag on the current active config for ``engine``.

        A no-op when none is active. Done before inserting the new active row
        so the one-active-per-engine partial unique index never trips.
        """
        active = await self.get_active(engine)
        if active is not None:
            active.is_active = False
            await self._session.flush()

    async def add(self, config: ScoringConfig) -> ScoringConfig:
        self._session.add(config)
        await self._session.flush()
        await self._session.refresh(config)
        return config
