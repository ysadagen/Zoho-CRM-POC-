"""Data-access layer for ``idempotency_keys`` (Track B push deduplication)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.idempotency_key import IdempotencyKey


class IdempotencyRepository:
    """Store and retrieve idempotency records within their TTL."""

    def __init__(self, session: AsyncSession, *, ttl_hours: int = 24) -> None:
        self._session = session
        self._ttl_hours = ttl_hours

    async def get(self, key: str) -> IdempotencyKey | None:
        """Return the record for ``key`` if it exists and is within the TTL."""
        cutoff = datetime.now(UTC) - timedelta(hours=self._ttl_hours)
        stmt = select(IdempotencyKey).where(
            IdempotencyKey.key == key,
            IdempotencyKey.created_at >= cutoff,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def save(
        self,
        *,
        key: str,
        request_hash: str,
        response_body: dict[str, Any] | None,
        status_code: int,
    ) -> None:
        """Persist a new idempotency record (flush only; caller commits)."""
        self._session.add(
            IdempotencyKey(
                key=key,
                request_hash=request_hash,
                response_body=response_body,
                status_code=status_code,
            )
        )
        await self._session.flush()
