"""Tests for the internal Zoho-ingest endpoints (Track A).

Covers the service-to-service auth gate, the ingest-disabled gate, and the
upsert behaviour that the effort/efficiency engine depends on: owner
attribution onto the columns the engine aggregates (``assigned_to_user_id`` /
``rep_user_id``), the Zoho creation time landing on ``created_at``, the
stage/history mirror, and a won Deal stamping the terminal fields under the
DB CHECK.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.dependencies.auth import INTERNAL_API_KEY_HEADER
from app.models.lead import Lead, LeadStage, LeadStageHistory
from app.models.sales_activity import ActivityType, SalesActivity
from app.models.user import User


@pytest.fixture
def internal_headers() -> dict[str, str]:
    """The header the Integration Layer sends — the shared internal API key."""
    return {INTERNAL_API_KEY_HEADER: get_settings().integration_layer_api_key}


@pytest.fixture
def ingest_enabled() -> Iterator[None]:
    """Enable ZOHO_INGEST_ENABLED for the test, restoring the prior value after."""
    settings = get_settings()
    original = settings.zoho_ingest_enabled
    settings.zoho_ingest_enabled = True
    try:
        yield
    finally:
        settings.zoho_ingest_enabled = original


async def _make_user(db_session: AsyncSession, *, email: str) -> User:
    user = User(
        email=email,
        full_name="Sales Rep",
        hashed_password=hash_password("irrelevant"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await _make_user(db_session, email="rep.one@example.com")


def _lead_payload(owner_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "contact_name": "Acme Corp",
        "source": "REFERENCE",
        "assigned_to_user_id": owner_id,
    }
    payload.update(overrides)
    return payload


async def test_ingest_requires_internal_api_key(
    client_with_db: AsyncClient, ingest_enabled: None, owner: User
) -> None:
    response = await client_with_db.post("/api/v1/ingest/leads", json=_lead_payload(str(owner.id)))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_API_KEY"


async def test_ingest_disabled_returns_503(
    client_with_db: AsyncClient, internal_headers: dict[str, str]
) -> None:
    # ingest_enabled fixture deliberately not used → flag is its default (false).
    response = await client_with_db.get("/api/v1/ingest/users", headers=internal_headers)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "INGEST_DISABLED"


async def test_ingest_list_users_returns_app_users(
    client_with_db: AsyncClient,
    internal_headers: dict[str, str],
    ingest_enabled: None,
    db_session: AsyncSession,
) -> None:
    await _make_user(db_session, email="a@example.com")
    await _make_user(db_session, email="b@example.com")

    response = await client_with_db.get("/api/v1/ingest/users", headers=internal_headers)

    assert response.status_code == 200
    emails = {u["email"] for u in response.json()["items"]}
    assert {"a@example.com", "b@example.com"} <= emails


async def test_ingest_create_lead_attributes_owner_and_source_created_at(
    client_with_db: AsyncClient,
    internal_headers: dict[str, str],
    ingest_enabled: None,
    db_session: AsyncSession,
    owner: User,
) -> None:
    payload = _lead_payload(
        str(owner.id),
        stage="QUALIFICATION",
        source_created_at="2025-01-15T09:00:00Z",
        state="Odisha",
    )
    response = await client_with_db.post(
        "/api/v1/ingest/leads", json=payload, headers=internal_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["stage"] == "QUALIFICATION"

    lead = await db_session.scalar(select(Lead).where(Lead.id == body["id"]))
    assert lead is not None
    assert lead.assigned_to_user_id == owner.id  # efficiency aggregates on this
    assert lead.created_by_user_id == owner.id  # no human actor → owner is source
    assert lead.created_at == datetime(2025, 1, 15, 9, 0, tzinfo=UTC)
    history = (
        await db_session.scalars(
            select(LeadStageHistory).where(LeadStageHistory.lead_id == lead.id)
        )
    ).all()
    assert [h.to_stage for h in history] == [LeadStage.QUALIFICATION]


async def test_ingest_update_lead_stage_appends_history(
    client_with_db: AsyncClient,
    internal_headers: dict[str, str],
    ingest_enabled: None,
    db_session: AsyncSession,
    owner: User,
) -> None:
    created = await client_with_db.post(
        "/api/v1/ingest/leads", json=_lead_payload(str(owner.id)), headers=internal_headers
    )
    lead_id = created.json()["id"]

    response = await client_with_db.patch(
        f"/api/v1/ingest/leads/{lead_id}",
        json={"stage": "QUALIFICATION"},
        headers=internal_headers,
    )

    assert response.status_code == 200
    assert response.json()["stage"] == "QUALIFICATION"
    history = (
        await db_session.scalars(
            select(LeadStageHistory)
            .where(LeadStageHistory.lead_id == lead_id)
            .order_by(LeadStageHistory.changed_at)
        )
    ).all()
    assert [h.to_stage for h in history] == [LeadStage.NEW, LeadStage.QUALIFICATION]


async def test_ingest_won_deal_stamps_terminal_fields(
    client_with_db: AsyncClient,
    internal_headers: dict[str, str],
    ingest_enabled: None,
    db_session: AsyncSession,
    owner: User,
) -> None:
    created = await client_with_db.post(
        "/api/v1/ingest/leads", json=_lead_payload(str(owner.id)), headers=internal_headers
    )
    lead_id = created.json()["id"]

    response = await client_with_db.patch(
        f"/api/v1/ingest/leads/{lead_id}",
        json={"stage": "WON", "won_value": "50000.00", "won_at": "2025-03-01T12:00:00Z"},
        headers=internal_headers,
    )

    assert response.status_code == 200
    lead = await db_session.scalar(select(Lead).where(Lead.id == lead_id))
    assert lead is not None
    assert lead.stage == LeadStage.WON
    assert lead.won_at == datetime(2025, 3, 1, 12, 0, tzinfo=UTC)
    assert str(lead.won_value) == "50000.00"


async def test_ingest_create_activity_attributes_to_rep(
    client_with_db: AsyncClient,
    internal_headers: dict[str, str],
    ingest_enabled: None,
    db_session: AsyncSession,
    owner: User,
) -> None:
    lead = await client_with_db.post(
        "/api/v1/ingest/leads", json=_lead_payload(str(owner.id)), headers=internal_headers
    )
    lead_id = lead.json()["id"]

    response = await client_with_db.post(
        "/api/v1/ingest/activities",
        json={
            "type": "MEETING",
            "rep_user_id": str(owner.id),
            "lead_id": lead_id,
            "occurred_at": "2025-02-10T10:00:00Z",
            "duration_minutes": 45,
        },
        headers=internal_headers,
    )

    assert response.status_code == 201
    activity = await db_session.scalar(
        select(SalesActivity).where(SalesActivity.id == response.json()["id"])
    )
    assert activity is not None
    assert activity.rep_user_id == owner.id  # effort aggregates on this
    assert activity.type == ActivityType.MEETING


async def test_ingest_activity_without_subject_returns_422(
    client_with_db: AsyncClient,
    internal_headers: dict[str, str],
    ingest_enabled: None,
    owner: User,
) -> None:
    response = await client_with_db.post(
        "/api/v1/ingest/activities",
        json={
            "type": "CALL",
            "rep_user_id": str(owner.id),
            "occurred_at": "2025-02-10T10:00:00Z",
        },
        headers=internal_headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SUBJECT_REQUIRED"
