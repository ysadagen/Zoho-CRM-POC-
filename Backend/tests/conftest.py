"""Shared pytest fixtures for the Backend test suite.

Schema lifecycle:

* **Session-scoped** (``_initialize_test_schema``): wipe the test DB's
  ``public`` schema and run ``alembic upgrade head`` against it. This
  is the SAME migration chain a production deploy would apply, so the
  test suite proves the migrations are correct end-to-end. CLAUDE.md
  §10 requires "migrations are mandatory" — running them in the test
  bootstrap is what makes that promise real.
* **Function-scoped** (``test_engine`` + ``db_session``): each test
  gets its own connection wrapped in an outer transaction; any
  ``session.commit()`` inside the code under test becomes a SAVEPOINT
  (via ``join_transaction_mode="create_savepoint"``) and is unwound
  by the final rollback. The shared schema persists between tests
  because data isolation is handled by the rollback, not by tearing
  the schema down each time.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.models.user import User

_BACKEND_DIR = Path(__file__).resolve().parent.parent


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


@pytest.fixture(scope="session", autouse=True)
def _initialize_test_schema() -> Iterator[None]:
    """Wipe the test DB and run ``alembic upgrade head`` once per session.

    Wipes ``public`` first so a previous half-failed run can't leak
    table or ENUM state into the next session. Then invokes Alembic
    as a subprocess (so its own ``asyncio.run`` inside ``env.py``
    can't collide with pytest-asyncio's loop). The URL is passed via
    ``-x url=...`` so the dev DB is never touched.

    Alembic is invoked via ``python -m alembic`` using the current
    interpreter (``sys.executable``) rather than ``uv run`` — the latter
    is blocked by local Application Control on some dev machines, and
    using the running interpreter guarantees the same venv regardless.
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
        cwd=str(_BACKEND_DIR),
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
    """Yield a per-test engine bound to :data:`Settings.test_database_url`.

    **Function-scoped on purpose.** pytest-asyncio creates a fresh event
    loop per test; a session-scoped asyncpg engine ends up with futures
    attached to the wrong loop on the second test and the suite blows
    up with ``got Future ... attached to a different loop``.

    ``poolclass=NullPool`` means no connections are pooled between
    checkouts — each connection opens and closes cleanly inside the
    test's own loop. The cost is negligible for the test suite and gives
    the suite robust, leak-free teardown.

    The schema itself is created once per session by
    :func:`_initialize_test_schema`; this fixture just hands out a
    fresh engine pointed at the already-migrated DB.
    """
    settings = get_settings()
    engine = create_async_engine(settings.test_database_url, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yield a transactional :class:`AsyncSession` that rolls back per test.

    The outer transaction wraps the entire test; any session-level commit
    issued by the code under test becomes a SAVEPOINT inside the outer
    transaction (via ``join_transaction_mode="create_savepoint"``) and is
    unwound by the final ``transaction.rollback()``. Tests therefore
    never leak state between each other even though the schema persists
    for the whole session.
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
        json={"email": email, "full_name": "Fixture Runner", "password": password},
    )
    login = await client_with_db.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login.json()["access_token"]
    client_with_db.headers["Authorization"] = f"Bearer {token}"
    return client_with_db


@pytest.fixture
async def admin_authenticated_client(
    client_with_db: AsyncClient,
    db_session: AsyncSession,
) -> AsyncClient:
    """``client_with_db`` with a pre-registered **admin** user logged in.

    Phase 1 has no admin-promotion endpoint — the bootstrap is SQL,
    not API. This fixture simulates that bootstrap by registering a
    user, flipping ``is_admin`` directly on the ORM, then logging in.
    The promotion happens against the same SAVEPOINT the request will
    use, so the change is visible to the next API call and rolled
    back at teardown.
    """
    email = "admin-fixture@example.com"
    password = "admin-fixture-passphrase"

    await client_with_db.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Admin Fixture", "password": password},
    )

    user = await db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.is_admin = True
    await db_session.commit()

    login = await client_with_db.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login.json()["access_token"]
    client_with_db.headers["Authorization"] = f"Bearer {token}"
    return client_with_db
