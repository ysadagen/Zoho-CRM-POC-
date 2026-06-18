"""Async SQLAlchemy engine, session factory, and request-scoped session.

Single engine and session factory per process, both lazily constructed and
cached via :func:`functools.lru_cache`. The factory yields an
:class:`AsyncSession` scoped to a single request via the :func:`get_db`
FastAPI dependency. Sessions never outlive the request that created them.

Tests override :func:`get_db` to inject a transactional session that
rolls back per test (see ``tests/conftest.py``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for every ORM model in the Backend.

    All ``models/*.py`` files MUST inherit from this class. Alembic's
    autogenerate uses ``Base.metadata`` as the source of truth for the
    target schema, so every table must be reachable from here.
    """


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Return the cached singleton :class:`AsyncEngine`.

    ``pool_pre_ping`` is on so connections dropped by the DB (restart,
    idle timeout) are detected and recycled transparently instead of
    surfacing as request failures.
    """
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        echo=False,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the cached singleton :class:`async_sessionmaker`."""
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a request-scoped :class:`AsyncSession`.

    The session is closed automatically when the request finishes. On any
    exception, the active transaction is rolled back explicitly so a
    failed request never leaks partial state back into the connection pool.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
