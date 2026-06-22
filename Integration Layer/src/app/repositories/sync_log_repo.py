"""Data-access layer for ``sync_logs`` — the sync/ingest audit ledger."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sync_log import SyncLog, SyncStatus


class SyncLogRepository:
    """Append and read sync/ingest attempt records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, log: SyncLog) -> SyncLog:
        """Persist a sync-log row. Flush so its id/defaults populate."""
        self._session.add(log)
        await self._session.flush()
        return log

    async def list_recent(self, *, limit: int = 50) -> list[SyncLog]:
        """Return the most recent sync-log rows, newest first (status feed)."""
        stmt = select(SyncLog).order_by(SyncLog.created_at.desc()).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_by_status(self, status: SyncStatus) -> int:
        """Count rows in a given status (e.g. how many records were PARKED)."""
        stmt = select(SyncLog).where(SyncLog.status == status)
        return len((await self._session.execute(stmt)).scalars().all())
