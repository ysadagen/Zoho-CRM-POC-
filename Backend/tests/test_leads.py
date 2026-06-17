"""Tests for /api/v1/leads — CRUD, filters, FK validation, and DB invariants.

Stage-transition behaviour lives in ``test_lead_transitions.py``.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadStage

LEADS_URL = "/api/v1/leads"
CUSTOMERS_URL = "/api/v1/customers"
ITEMS_URL = "/api/v1/items"


def _lead_url(lead_id: str | uuid.UUID) -> str:
    return f"{LEADS_URL}/{lead_id}"


async def _seed_refs(client: AsyncClient) -> tuple[str, str, str]:
    """Create a customer + item; return ``(user_id, customer_id, item_id)``.

    The customer's ``created_by_user_id`` is the authenticated user — a valid
    ``assigned_to_user_id`` for leads without needing the DB session.
    """
    cust = (
        await client.post(
            CUSTOMERS_URL,
            json={"company_name": "Ref Co", "contact_person": "Ref Person"},
        )
    ).json()
    item = (
        await client.post(
            ITEMS_URL,
            json={
                "sku": f"ITM-{uuid.uuid4().hex[:8]}",
                "name": "Ref Item",
                "type": "RAW",
                "category": "Polymer",
                "unit_of_measure": "kg",
                "unit_price": "100.00",
                "standard_cost": "75.00",
            },
        )
    ).json()
    return cust["created_by_user_id"], cust["id"], item["id"]


def _lead_payload(assigned_to_user_id: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "contact_name": "Ravi Kumar",
        "source": "FIELD_VISIT",
        "assigned_to_user_id": assigned_to_user_id,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def test_create_lead_requires_auth_returns_401(client_with_db: AsyncClient) -> None:
    resp = await client_with_db.post(
        LEADS_URL, json=_lead_payload(str(uuid.uuid4()))
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_lead_starts_at_new_with_generated_number(
    authenticated_client: AsyncClient,
) -> None:
    user_id, customer_id, item_id = await _seed_refs(authenticated_client)
    resp = await authenticated_client.post(
        LEADS_URL,
        json=_lead_payload(
            user_id,
            customer_id=customer_id,
            item_id=item_id,
            quantity="50",
            estimated_budget="800000",
            dealer_potential="HIGH",
            required_by_date="2026-09-01",
            state="Odisha",
            district="Jajpur",
        ),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["stage"] == "NEW"
    assert body["lead_number"].startswith("LD-")
    assert body["dealer_potential"] == "HIGH"
    assert body["customer_id"] == customer_id
    assert body["won_at"] is None and body["lost_at"] is None


async def test_create_lead_writes_creation_history_row(
    authenticated_client: AsyncClient,
) -> None:
    user_id, _, _ = await _seed_refs(authenticated_client)
    created = await authenticated_client.post(LEADS_URL, json=_lead_payload(user_id))
    lead_id = created.json()["id"]

    detail = await authenticated_client.get(_lead_url(lead_id))
    assert detail.status_code == 200
    history = detail.json()["stage_history"]
    assert len(history) == 1
    assert history[0]["from_stage"] is None
    assert history[0]["to_stage"] == "NEW"


async def test_create_lead_unknown_assigned_user_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    resp = await authenticated_client.post(LEADS_URL, json=_lead_payload(str(uuid.uuid4())))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "USER_NOT_FOUND"


async def test_create_lead_unknown_customer_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    user_id, _, _ = await _seed_refs(authenticated_client)
    resp = await authenticated_client.post(
        LEADS_URL, json=_lead_payload(user_id, customer_id=str(uuid.uuid4()))
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"


async def test_create_lead_unknown_item_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    user_id, _, _ = await _seed_refs(authenticated_client)
    resp = await authenticated_client.post(
        LEADS_URL, json=_lead_payload(user_id, item_id=str(uuid.uuid4()))
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ITEM_NOT_FOUND"


async def test_create_lead_rejects_non_positive_quantity_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    user_id, _, _ = await _seed_refs(authenticated_client)
    resp = await authenticated_client.post(
        LEADS_URL, json=_lead_payload(user_id, quantity="0")
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# List + filters
# ---------------------------------------------------------------------------


async def test_list_leads_returns_paginated_shape(authenticated_client: AsyncClient) -> None:
    resp = await authenticated_client.get(LEADS_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"items", "total", "limit", "offset"}


async def test_list_leads_filters_by_source_and_assignee(
    authenticated_client: AsyncClient,
) -> None:
    user_id, _, _ = await _seed_refs(authenticated_client)
    await authenticated_client.post(LEADS_URL, json=_lead_payload(user_id, source="WALK_IN"))
    await authenticated_client.post(LEADS_URL, json=_lead_payload(user_id, source="CAMPAIGN"))

    by_source = await authenticated_client.get(LEADS_URL, params={"source": "WALK_IN"})
    assert by_source.json()["total"] == 1
    assert by_source.json()["items"][0]["source"] == "WALK_IN"

    by_assignee = await authenticated_client.get(
        LEADS_URL, params={"assigned_to_user_id": user_id}
    )
    assert by_assignee.json()["total"] == 2


# ---------------------------------------------------------------------------
# Get / Patch / Delete
# ---------------------------------------------------------------------------


async def test_get_lead_not_found_returns_404(authenticated_client: AsyncClient) -> None:
    resp = await authenticated_client.get(_lead_url(uuid.uuid4()))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "LEAD_NOT_FOUND"


async def test_patch_lead_updates_mutable_fields(authenticated_client: AsyncClient) -> None:
    user_id, _, _ = await _seed_refs(authenticated_client)
    created = await authenticated_client.post(LEADS_URL, json=_lead_payload(user_id))
    lead_id = created.json()["id"]

    resp = await authenticated_client.patch(
        _lead_url(lead_id), json={"contact_name": "Ravi K.", "district": "Cuttack"}
    )
    assert resp.status_code == 200
    assert resp.json()["contact_name"] == "Ravi K."
    assert resp.json()["district"] == "Cuttack"
    # Stage untouched by PATCH.
    assert resp.json()["stage"] == "NEW"


async def test_patch_lead_rejects_stage_field_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    """``stage`` is not a PATCH-able field — it must go through /transition."""
    user_id, _, _ = await _seed_refs(authenticated_client)
    created = await authenticated_client.post(LEADS_URL, json=_lead_payload(user_id))
    lead_id = created.json()["id"]

    resp = await authenticated_client.patch(_lead_url(lead_id), json={"stage": "WON"})
    assert resp.status_code == 422


async def test_soft_delete_hides_lead_and_is_idempotent(
    authenticated_client: AsyncClient,
) -> None:
    user_id, _, _ = await _seed_refs(authenticated_client)
    created = await authenticated_client.post(LEADS_URL, json=_lead_payload(user_id))
    lead_id = created.json()["id"]

    first = await authenticated_client.delete(_lead_url(lead_id))
    second = await authenticated_client.delete(_lead_url(lead_id))
    assert first.status_code == 204
    assert second.status_code == 204  # idempotent

    active_only = await authenticated_client.get(LEADS_URL, params={"is_active": True})
    assert all(item["id"] != lead_id for item in active_only.json()["items"])


async def test_delete_unknown_lead_returns_404(authenticated_client: AsyncClient) -> None:
    resp = await authenticated_client.delete(_lead_url(uuid.uuid4()))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DB invariant — the last line of defence (CLAUDE.md §10.3)
# ---------------------------------------------------------------------------


async def test_db_rejects_won_stage_without_terminal_fields(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The won-consistency CHECK forbids stage=WON without won_at + won_value,
    even when written straight to the ORM (bypassing the transition service).
    """
    user_id, _, _ = await _seed_refs(authenticated_client)
    created = await authenticated_client.post(LEADS_URL, json=_lead_payload(user_id))
    lead_id = uuid.UUID(created.json()["id"])

    lead = await db_session.scalar(select(Lead).where(Lead.id == lead_id))
    assert lead is not None
    lead.stage = LeadStage.WON  # but no won_at / won_value

    with pytest.raises(IntegrityError):
        await db_session.flush()
