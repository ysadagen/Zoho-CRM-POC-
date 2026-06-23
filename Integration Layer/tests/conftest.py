"""Shared pytest fixtures for the Integration Layer test suite.

Schema lifecycle mirrors the Backend:

* **Session-scoped** (``_initialize_test_schema``): wipe the test DB's
  ``public`` schema and run ``alembic upgrade head`` against it. This is the
  SAME migration chain a production deploy applies, so the suite proves the
  migrations are correct end-to-end (CLAUDE.md §10: migrations are mandatory).
* **Function-scoped** (``test_engine`` + ``db_session``): each test gets a
  connection wrapped in an outer transaction; any ``session.commit()`` in the
  code under test becomes a SAVEPOINT (``join_transaction_mode=
  "create_savepoint"``) unwound by the final rollback, so tests never leak
  state even though the schema persists across the session.

No Zoho HTTP is ever made for real — tests mock it with ``respx``.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.dependencies.db import get_db
from app.main import app
from app.models.zoho_token import ZohoToken

_SERVICE_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Yield an :class:`AsyncClient` bound to the app via ASGI (no DB)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture(scope="session", autouse=True)
def _initialize_test_schema() -> Iterator[None]:
    """Wipe the test DB and run ``alembic upgrade head`` once per session.

    Wipes ``public`` first so a half-failed prior run cannot leak table or
    ENUM state. Alembic is invoked as a subprocess via ``python -m alembic``
    using the running interpreter (``sys.executable``) — robust against the
    Application-Control block on ``uv run`` documented in CLAUDE.md §17, and
    keeping its own ``asyncio.run`` clear of pytest-asyncio's loop. The URL is
    passed via ``-x url=...`` so the dev DB is never touched.
    """
    settings = get_settings()
    test_url = settings.test_database_url

    async def _wipe() -> None:
        engine = create_async_engine(test_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
                await conn.execute(text("CREATE SCHEMA public"))
        finally:
            await engine.dispose()

    asyncio.run(_wipe())

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-x", f"url={test_url}", "upgrade", "head"],
        cwd=str(_SERVICE_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "alembic upgrade head failed during test bootstrap:\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    yield


@pytest.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """Yield a per-test engine bound to the test DB (function-scoped on purpose).

    pytest-asyncio creates a fresh event loop per test; a session-scoped
    asyncpg engine ends up with futures attached to the wrong loop on the
    second test. ``NullPool`` means no connection is pooled between checkouts,
    giving leak-free teardown inside each test's own loop.
    """
    settings = get_settings()
    engine = create_async_engine(settings.test_database_url, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yield a transactional :class:`AsyncSession` that rolls back per test."""
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture
async def client_with_db(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Like :func:`client`, but with :func:`get_db` pointed at the test session."""

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def seed_token(db_session: AsyncSession) -> Callable[..., Awaitable[ZohoToken]]:
    """Return a helper that stages and flushes a :class:`ZohoToken` row.

    The row is flushed (not committed) so the repository's ``SELECT`` sees it
    under the same SAVEPOINT (the session is ``autoflush=False``); it is rolled
    back at teardown. ``expires_in_seconds`` controls validity: a large
    positive value is "fresh", a negative value is "expired".
    """

    async def _seed(
        *,
        access_token: str = "stored-access-token",
        refresh_token: str = "stored-refresh-token",
        expires_in_seconds: int = 3600,
    ) -> ZohoToken:
        token = ZohoToken(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            scope="ZohoCRM.users.READ",
            api_domain="https://www.zohoapis.in",
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
        )
        db_session.add(token)
        await db_session.flush()
        return token

    return _seed
