"""Shared pytest fixtures for the Backend test suite."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Yield an :class:`AsyncClient` bound to the FastAPI app via ASGI.

    Use this fixture for tests that do NOT touch the database. No
    transaction is opened, no DB connection is created — keeps the test
    fast and free of infrastructure dependencies.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """Yield a per-test engine bound to :data:`Settings.test_database_url`.

    **Function-scoped on purpose.** pytest-asyncio creates a fresh event
    loop per test; a session-scoped asyncpg engine ends up with futures
    attached to the wrong loop on the second test and the suite blows
    up with ``got Future ... attached to a different loop``.

    ``poolclass=NullPool`` means no connections are pooled between
    checkouts — each connection opens and closes cleanly inside the
    test's own loop. The cost is negligible for the test suite and gives
    the suite robust, leak-free teardown.

    The schema is rebuilt from ``Base.metadata`` at setup and dropped at
    teardown. When models grow, this is the place to switch to running
    Alembic against the test DB instead of ``create_all``.
    """
    settings = get_settings()
    engine = create_async_engine(settings.test_database_url, poolclass=NullPool)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yield a transactional :class:`AsyncSession` that rolls back per test.

    The outer transaction wraps the entire test; any session-level commit
    issued by the code under test becomes a SAVEPOINT inside the outer
    transaction (via ``join_transaction_mode="create_savepoint"``) and is
    unwound by the final ``transaction.rollback()``. Tests therefore
    never leak state between each other.
    """
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
    """Like :func:`client`, but with :func:`get_db` pointed at the test session.

    Use this fixture only for tests that exercise an endpoint touching
    the database. Reverts the dependency override on teardown so other
    tests are unaffected.
    """

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
async def authenticated_client(client_with_db: AsyncClient) -> AsyncClient:
    """``client_with_db`` with a pre-registered user logged in.

    Use this for tests that don't exercise the auth flow itself but
    need a valid bearer token to call protected endpoints. Tests that
    test registration or login specifically should keep using
    ``client_with_db`` and drive the flow themselves.

    The bearer header is set directly on the client's default headers
    so individual calls don't have to thread it through every request.
    """
    email = "fixture-runner@example.com"
    password = "fixture-passphrase"

    await client_with_db.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    login = await client_with_db.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login.json()["access_token"]
    client_with_db.headers["Authorization"] = f"Bearer {token}"
    return client_with_db
