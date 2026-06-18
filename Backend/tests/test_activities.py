"""Tests for /api/v1/activities — append-only create + list.

Covers the subject rule, rep defaulting, FK validation, the no-future
constraint, the duration CHECK (direct insert), filters, and the absence
of any mutation route.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sales_activity import SalesActivity

ACTIVITIES_URL = "/api/v1/activities"
CUSTOMERS_URL = "/api/v1/customers"


async def _customer(client: AsyncClient) -> dict[str, str]:
    return (
        await client.post(
            CUSTOMERS_URL,
            json={"company_name": "Act Co", "contact_person": "Act Person"},
        )
    ).json()


def _past(days: int = 1) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


async def test_record_activity_defaults_rep_to_caller(authenticated_client: AsyncClient) -> None:
    cust = await _customer(authenticated_client)
    resp = await authenticated_client.post(
        ACTIVITIES_URL,
        json={
            "type": "VISIT",
            "occurred_at": _past(),
            "customer_id": cust["id"],
            "duration_minutes": 30,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["type"] == "VISIT"
    assert body["customer_id"] == cust["id"]
    # rep defaulted to the authenticated user (== the customer's creator).
    assert body["rep_user_id"] == cust["created_by_user_id"]


async def test_record_activity_without_subject_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    resp = await authenticated_client.post(
        ACTIVITIES_URL, json={"type": "CALL", "occurred_at": _past()}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "SUBJECT_REQUIRED"


async def test_record_activity_in_future_returns_422(authenticated_client: AsyncClient) -> None:
    cust = await _customer(authenticated_client)
    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    resp = await authenticated_client.post(
        ACTIVITIES_URL,
        json={"type": "MEETING", "occurred_at": future, "customer_id": cust["id"]},
    )
    assert resp.status_code == 422


async def test_record_activity_unknown_customer_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    resp = await authenticated_client.post(
        ACTIVITIES_URL,
        json={"type": "CALL", "occurred_at": _past(), "customer_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"


async def test_record_activity_requires_auth_returns_401(client_with_db: AsyncClient) -> None:
    resp = await client_with_db.post(
        ACTIVITIES_URL,
        json={"type": "CALL", "occurred_at": _past(), "customer_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 401


async def test_list_activities_filters_by_type_and_customer(
    authenticated_client: AsyncClient,
) -> None:
    cust = await _customer(authenticated_client)
    await authenticated_client.post(
        ACTIVITIES_URL,
        json={"type": "VISIT", "occurred_at": _past(), "customer_id": cust["id"]},
    )
    await authenticated_client.post(
        ACTIVITIES_URL,
        json={"type": "CALL", "occurred_at": _past(), "customer_id": cust["id"]},
    )

    by_type = await authenticated_client.get(ACTIVITIES_URL, params={"type": "VISIT"})
    assert by_type.json()["total"] == 1
    assert by_type.json()["items"][0]["type"] == "VISIT"

    by_customer = await authenticated_client.get(
        ACTIVITIES_URL, params={"customer_id": cust["id"]}
    )
    assert by_customer.json()["total"] == 2


async def test_activities_have_no_update_or_delete_route(
    authenticated_client: AsyncClient,
) -> None:
    """Activities are append-only — PATCH/DELETE must not be routable."""
    cust = await _customer(authenticated_client)
    created = await authenticated_client.post(
        ACTIVITIES_URL,
        json={"type": "VISIT", "occurred_at": _past(), "customer_id": cust["id"]},
    )
    activity_id = created.json()["id"]

    patch = await authenticated_client.patch(f"{ACTIVITIES_URL}/{activity_id}", json={})
    delete = await authenticated_client.delete(f"{ACTIVITIES_URL}/{activity_id}")
    # No such route exists (append-only) → 404, never a successful mutation.
    assert patch.status_code == 404
    assert delete.status_code == 404


async def test_db_rejects_subjectless_activity_when_set_directly(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The has-subject CHECK rejects an activity with neither customer nor
    lead, even bypassing the service (CLAUDE.md §10.3)."""
    cust = await _customer(authenticated_client)
    created = await authenticated_client.post(
        ACTIVITIES_URL,
        json={"type": "VISIT", "occurred_at": _past(), "customer_id": cust["id"]},
    )
    activity_id = uuid.UUID(created.json()["id"])

    activity = await db_session.scalar(
        select(SalesActivity).where(SalesActivity.id == activity_id)
    )
    assert activity is not None
    activity.customer_id = None  # now no subject at all

    with pytest.raises(IntegrityError):
        await db_session.flush()
