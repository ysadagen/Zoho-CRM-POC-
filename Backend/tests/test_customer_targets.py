"""Tests for /api/v1/customers/{id}/targets — CRUD + non-overlap."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

CUSTOMERS_URL = "/api/v1/customers"


async def _customer_id(client: AsyncClient) -> str:
    resp = await client.post(
        CUSTOMERS_URL, json={"company_name": "Tgt Co", "contact_person": "Tgt Person"}
    )
    return resp.json()["id"]


def _targets_url(customer_id: str) -> str:
    return f"{CUSTOMERS_URL}/{customer_id}/targets"


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "period_start": "2026-04-01",
        "period_end": "2026-06-30",
        "target_quantity": "1000",
        "target_revenue": "5000000",
    }
    base.update(overrides)
    return base


async def test_create_target_returns_201(authenticated_client: AsyncClient) -> None:
    cid = await _customer_id(authenticated_client)
    resp = await authenticated_client.post(_targets_url(cid), json=_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["customer_id"] == cid
    assert body["target_quantity"] == "1000.0000"


async def test_create_target_unknown_customer_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    resp = await authenticated_client.post(_targets_url(str(uuid.uuid4())), json=_payload())
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"


async def test_create_target_bad_period_order_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    cid = await _customer_id(authenticated_client)
    resp = await authenticated_client.post(
        _targets_url(cid),
        json=_payload(period_start="2026-06-30", period_end="2026-04-01"),
    )
    assert resp.status_code == 422


async def test_create_overlapping_target_returns_409(authenticated_client: AsyncClient) -> None:
    cid = await _customer_id(authenticated_client)
    await authenticated_client.post(_targets_url(cid), json=_payload())
    # Overlaps the Apr-Jun period.
    resp = await authenticated_client.post(
        _targets_url(cid),
        json=_payload(period_start="2026-05-01", period_end="2026-08-31"),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "OVERLAPPING_TARGET_PERIOD"


async def test_create_adjacent_non_overlapping_target_succeeds(
    authenticated_client: AsyncClient,
) -> None:
    cid = await _customer_id(authenticated_client)
    await authenticated_client.post(_targets_url(cid), json=_payload())
    # Starts exactly where the first ends (half-open → no overlap).
    resp = await authenticated_client.post(
        _targets_url(cid),
        json=_payload(period_start="2026-06-30", period_end="2026-09-30"),
    )
    assert resp.status_code == 201


async def test_list_targets_returns_customer_targets(authenticated_client: AsyncClient) -> None:
    cid = await _customer_id(authenticated_client)
    await authenticated_client.post(_targets_url(cid), json=_payload())
    resp = await authenticated_client.get(_targets_url(cid))
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_update_target_changes_quantity(authenticated_client: AsyncClient) -> None:
    cid = await _customer_id(authenticated_client)
    created = await authenticated_client.post(_targets_url(cid), json=_payload())
    target_id = created.json()["id"]

    resp = await authenticated_client.patch(
        f"{_targets_url(cid)}/{target_id}", json={"target_quantity": "1500"}
    )
    assert resp.status_code == 200
    assert resp.json()["target_quantity"] == "1500.0000"


async def test_update_target_wrong_customer_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    cid = await _customer_id(authenticated_client)
    other = await _customer_id(authenticated_client)
    created = await authenticated_client.post(_targets_url(cid), json=_payload())
    target_id = created.json()["id"]

    resp = await authenticated_client.patch(
        f"{_targets_url(other)}/{target_id}", json={"target_quantity": "1500"}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TARGET_NOT_FOUND"
