"""Tests for POST /api/v1/leads/{id}/transition — the lead state machine.

Covers the full legal path, every illegal move (409), terminal-state field
rules (422), and the append-only history trail.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient

LEADS_URL = "/api/v1/leads"
CUSTOMERS_URL = "/api/v1/customers"


def _lead_url(lead_id: str | uuid.UUID) -> str:
    return f"{LEADS_URL}/{lead_id}"


async def _user_id(client: AsyncClient) -> str:
    cust = (
        await client.post(
            CUSTOMERS_URL,
            json={"company_name": "Ref Co", "contact_person": "Ref Person"},
        )
    ).json()
    return cust["created_by_user_id"]


async def _new_lead(client: AsyncClient) -> str:
    user_id = await _user_id(client)
    created = await client.post(
        LEADS_URL,
        json={
            "contact_name": "Lead Person",
            "source": "FIELD_VISIT",
            "assigned_to_user_id": user_id,
        },
    )
    return created.json()["id"]


async def _transition(client: AsyncClient, lead_id: str, **body: object) -> AsyncClient:
    return await client.post(f"{_lead_url(lead_id)}/transition", json=body)


# ---------------------------------------------------------------------------
# Legal path
# ---------------------------------------------------------------------------


async def test_full_legal_path_to_won(authenticated_client: AsyncClient) -> None:
    lead_id = await _new_lead(authenticated_client)

    r1 = await _transition(authenticated_client, lead_id, to_stage="QUALIFICATION")
    assert r1.status_code == 200 and r1.json()["stage"] == "QUALIFICATION"

    r2 = await _transition(authenticated_client, lead_id, to_stage="NEGOTIATION")
    assert r2.status_code == 200 and r2.json()["stage"] == "NEGOTIATION"

    r3 = await _transition(
        authenticated_client, lead_id, to_stage="WON", won_value="950000"
    )
    assert r3.status_code == 200
    body = r3.json()
    assert body["stage"] == "WON"
    assert body["won_value"] == "950000.00"
    assert body["won_at"] is not None

    # History now holds: NEW (creation) + 3 transitions, newest first.
    detail = await authenticated_client.get(_lead_url(lead_id))
    history = detail.json()["stage_history"]
    assert [h["to_stage"] for h in history] == ["WON", "NEGOTIATION", "QUALIFICATION", "NEW"]
    assert history[0]["from_stage"] == "NEGOTIATION"


async def test_transition_to_lost_sets_reason(authenticated_client: AsyncClient) -> None:
    lead_id = await _new_lead(authenticated_client)
    resp = await _transition(
        authenticated_client, lead_id, to_stage="LOST", lost_reason="Budget cut"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["stage"] == "LOST"
    assert body["lost_reason"] == "Budget cut"
    assert body["lost_at"] is not None


# ---------------------------------------------------------------------------
# Illegal transitions → 409
# ---------------------------------------------------------------------------


async def test_skip_stage_is_rejected(authenticated_client: AsyncClient) -> None:
    """NEW → NEGOTIATION skips QUALIFICATION — not allowed."""
    lead_id = await _new_lead(authenticated_client)
    resp = await _transition(authenticated_client, lead_id, to_stage="NEGOTIATION")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVALID_STAGE_TRANSITION"


async def test_new_directly_to_won_is_rejected(authenticated_client: AsyncClient) -> None:
    lead_id = await _new_lead(authenticated_client)
    resp = await _transition(
        authenticated_client, lead_id, to_stage="WON", won_value="100"
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVALID_STAGE_TRANSITION"


async def test_transition_from_terminal_is_rejected(authenticated_client: AsyncClient) -> None:
    lead_id = await _new_lead(authenticated_client)
    await _transition(authenticated_client, lead_id, to_stage="LOST", lost_reason="Gone")
    # LOST is terminal — any further move is rejected.
    resp = await _transition(authenticated_client, lead_id, to_stage="QUALIFICATION")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVALID_STAGE_TRANSITION"


# ---------------------------------------------------------------------------
# Terminal-field rules → 422
# ---------------------------------------------------------------------------


async def test_won_without_value_returns_422(authenticated_client: AsyncClient) -> None:
    lead_id = await _new_lead(authenticated_client)
    await _transition(authenticated_client, lead_id, to_stage="QUALIFICATION")
    await _transition(authenticated_client, lead_id, to_stage="NEGOTIATION")
    resp = await _transition(authenticated_client, lead_id, to_stage="WON")
    assert resp.status_code == 422


async def test_lost_without_reason_returns_422(authenticated_client: AsyncClient) -> None:
    lead_id = await _new_lead(authenticated_client)
    resp = await _transition(authenticated_client, lead_id, to_stage="LOST")
    assert resp.status_code == 422


async def test_won_value_on_non_won_transition_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    lead_id = await _new_lead(authenticated_client)
    resp = await _transition(
        authenticated_client, lead_id, to_stage="QUALIFICATION", won_value="100"
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------


async def test_transition_unknown_lead_returns_404(authenticated_client: AsyncClient) -> None:
    resp = await _transition(authenticated_client, str(uuid.uuid4()), to_stage="QUALIFICATION")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "LEAD_NOT_FOUND"
