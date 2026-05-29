"""Tests for the database wiring.

No models exist yet, so these tests validate only the plumbing: the
``db_session`` fixture hands back a real :class:`AsyncSession`, and that
session can talk to the test database.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def test_db_session_yields_async_session(db_session: AsyncSession) -> None:
    assert isinstance(db_session, AsyncSession)


async def test_db_session_can_execute_select_1(db_session: AsyncSession) -> None:
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1
