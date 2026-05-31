"""Data-access layer for the users table.

All SQL touching ``users`` is here. The service layer composes this
repository; routes never use it directly. Methods take primitives
(strings, UUIDs) in and return ORM model instances out — translation to
schemas happens at the API boundary.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Repository for :class:`User`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_(self, *, limit: int, offset: int) -> tuple[list[User], int]:
        """Return ``(users_page, total_count)`` ordered newest first.

        ``total`` is the full count of rows, ignoring ``limit``/``offset``,
        so callers can render pager controls.
        """
        base = select(User)
        count_stmt = select(func.count()).select_from(base.subquery())
        page_stmt = base.order_by(User.created_at.desc()).limit(limit).offset(offset)

        total = (await self._session.execute(count_stmt)).scalar_one()
        page = list((await self._session.execute(page_stmt)).scalars().all())
        return page, int(total)

    async def create(
        self,
        *,
        email: str,
        full_name: str,
        hashed_password: str,
    ) -> User:
        """Insert a new user and return the persisted row.

        ``flush`` (not ``commit``) so the caller controls transaction
        boundaries. ``refresh`` populates server-side defaults
        (``id``, ``created_at``, ``updated_at``) on the returned object.
        """
        user = User(email=email, full_name=full_name, hashed_password=hashed_password)
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user
