"""Read-only data access for the ``users`` table.

The auth dependency resolves the current user by id; the effort & efficiency
engine uses the active-user list as its rep cohort. This service never creates
or mutates users (the Backend owns that).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Read-only repository for :class:`User`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_active(self) -> list[User]:
        """Every active user (unpaginated) — the rep cohort for effort scoring."""
        stmt = select(User).where(User.is_active.is_(True)).order_by(User.email)
        return list((await self._session.execute(stmt)).scalars().all())
