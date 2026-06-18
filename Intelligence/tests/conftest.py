"""Shared pytest fixtures for the Intelligence service.

Schema lifecycle differs from the Backend on purpose: this service does not
*own* the CRM tables, so the test schema is built from ``Base.metadata`` via
``create_all`` (both the CRM read-models it consumes and the scoring tables it
owns), then the v1 scoring configs are seeded — the same active configs the
production migration seeds. Each test runs in a transaction rolled back at the
end (commits inside the code under test become SAVEPOINTs).

This service exposes no auth endpoints, so authenticated clients mint a JWT
directly with the shared secret (the same token the Backend would issue) and
back it with a real ``users`` row.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.models import Base
from app.models.scoring_config import ScoringConfig
from app.models.user import User
from app.services.scoring.default_configs import DEFAULT_PARAMS_V1


def _mint_token(user_id: uuid.UUID) -> str:
    """Issue the same shape of access token the Backend would, for tests."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


@pytest.fixture(scope="session", autouse=True)
def _initialize_test_schema() -> Iterator[None]:
    """Wipe the test DB, ``create_all`` the full schema, seed v1 configs."""
    settings = get_settings()
    test_url = settings.test_database_url

    async def _setup() -> None:
        engine = create_async_engine(test_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
                await conn.execute(text("CREATE SCHEMA public"))
                await conn.run_sync(Base.metadata.create_all)
            async with AsyncSession(engine) as session:
                for scoring_engine, params in DEFAULT_PARAMS_V1.items():
                    session.add(
                        ScoringConfig(
                            engine=scoring_engine,
                            version=1,
                            params=params,
                            is_active=True,
                            description="Seeded v1 defaults (test bootstrap)",
                        )
                    )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(_setup())
    yield


@pytest.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    settings = get_settings()
    engine = create_async_engine(settings.test_database_url, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Transactional session rolled back per test (SAVEPOINT semantics)."""
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
async def client() -> AsyncIterator[AsyncClient]:
    """AsyncClient with no DB wiring — for tests that never touch the database."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
async def client_with_db(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """AsyncClient with :func:`get_db` pointed at the test session."""

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)


async def _make_user(session: AsyncSession, *, is_admin: bool) -> User:
    user = User(
        email=f"{'admin' if is_admin else 'user'}-{uuid.uuid4().hex[:8]}@test.local",
        full_name="Test User",
        hashed_password="x",  # never verified — this service only decodes tokens
        is_admin=is_admin,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def authenticated_client(
    client_with_db: AsyncClient, db_session: AsyncSession
) -> tuple[AsyncClient, User]:
    """``client_with_db`` with a real (non-admin) user logged in.

    Returns ``(client, user)`` so tests can use the user's id for
    ``assigned_to_user_id`` / rep-cohort setup.
    """
    user = await _make_user(db_session, is_admin=False)
    client_with_db.headers["Authorization"] = f"Bearer {_mint_token(user.id)}"
    return client_with_db, user


@pytest.fixture
async def admin_client(
    client_with_db: AsyncClient, db_session: AsyncSession
) -> tuple[AsyncClient, User]:
    """``client_with_db`` with a real admin user logged in. Returns ``(client, user)``."""
    user = await _make_user(db_session, is_admin=True)
    client_with_db.headers["Authorization"] = f"Bearer {_mint_token(user.id)}"
    return client_with_db, user
