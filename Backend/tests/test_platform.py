"""Tests for cross-cutting platform behaviour — error envelope and probes.

Pinned here because they're not specific to one resource. They're the
contract every other test file relies on (the error envelope) and what
the Frontend leans on heavily (/health, /ready, validation shape).
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient

HEALTH_URL = "/health"
READY_URL = "/ready"


# ---------------------------------------------------------------------------
# Unified error envelope
# ---------------------------------------------------------------------------


async def test_validation_error_returns_unified_envelope(
    authenticated_client: AsyncClient,
) -> None:
    """A Pydantic 422 must return ``{error: {code, message, request_id, details}}``
    so the Frontend has a single parser for all failures.
    """
    response = await authenticated_client.post(
        "/api/v1/items",
        json={"name": "Missing required fields"},
    )
    assert response.status_code == 422
    body = response.json()
    assert "error" in body, body
    err = body["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert isinstance(err["message"], str) and err["message"]
    assert "request_id" in err
    assert isinstance(err.get("details"), list)
    assert err["details"], "details must surface FastAPI's per-field errors"
    first = err["details"][0]
    assert {"loc", "msg", "type"} <= first.keys()


async def test_validation_error_envelope_includes_request_id_header(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post("/api/v1/items", json={"name": "x"})
    assert response.status_code == 422
    # The middleware sets X-Request-ID; the envelope embeds the same value.
    header_rid = response.headers.get("x-request-id")
    body_rid = response.json()["error"]["request_id"]
    assert header_rid is not None
    assert header_rid == body_rid


# ---------------------------------------------------------------------------
# Login response includes the token lifetime
# ---------------------------------------------------------------------------


async def test_login_response_includes_expires_in(
    client_with_db: AsyncClient,
) -> None:
    """The login response must surface ``expires_in`` so the Frontend
    can warn or auto-logout before a token lapses. Re-login is the
    only renewal path — there is no /refresh endpoint by design.
    """
    await client_with_db.post(
        "/api/v1/auth/register",
        json={
            "email": "expiry-user@example.com",
            "full_name": "Expiry User",
            "password": "correct-horse-battery-staple",
        },
    )
    login = await client_with_db.post(
        "/api/v1/auth/login",
        json={
            "email": "expiry-user@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert login.status_code == 200
    body = login.json()
    assert isinstance(body["expires_in"], int)
    assert body["expires_in"] > 0
    assert body["token_type"] == "bearer"


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------


async def test_health_returns_200_without_db(client: AsyncClient) -> None:
    """Liveness must answer even when the DB is unreachable — it's
    answering 'is the Python process up?', not 'is the system healthy?'.
    """
    response = await client.get(HEALTH_URL)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_returns_200_when_db_is_reachable(
    client_with_db: AsyncClient,
) -> None:
    """Readiness pings the DB. With a working test session it must pass."""
    response = await client_with_db.get(READY_URL)
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ready"}


async def test_ready_uses_unified_error_envelope_on_db_failure() -> None:
    """If the DB connection raises, /ready returns 503 in the project
    envelope — not Starlette's default ``{detail: ...}`` shape.

    We override ``get_db`` with a stub that raises, mirroring a real
    outage at the connection layer.
    """
    from httpx import ASGITransport
    from httpx import AsyncClient as _AsyncClient
    from sqlalchemy.exc import OperationalError

    from app.core.database import get_db
    from app.main import app

    class _BrokenSession:
        async def execute(self, *args: object, **kwargs: object) -> None:
            raise OperationalError("ping", {}, BaseException("connection refused"))

    async def _broken_get_db():  # type: ignore[no-untyped-def]
        yield _BrokenSession()

    app.dependency_overrides[get_db] = _broken_get_db
    try:
        transport = ASGITransport(app=app)
        async with _AsyncClient(transport=transport, base_url="http://testserver") as ac:
            response = await ac.get(READY_URL)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "DB_UNAVAILABLE"
    assert "request_id" in body["error"]


# ---------------------------------------------------------------------------
# Pin: every non-2xx still flows through the envelope (smoke check)
# ---------------------------------------------------------------------------


async def test_404_uses_unified_envelope(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.get(f"/api/v1/items/{uuid.uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "ITEM_NOT_FOUND"
    assert "request_id" in body["error"]
