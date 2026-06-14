"""Tests for /api/v1/batches — the lot (batch) CRUD + expiry surface (1B).

Phase 1B is the opening-balance model: recording a lot associates existing
item stock with that lot and must NOT change ``items.stock_quantity`` or write
a stock movement. These tests pin that behaviour and the reconciliation rule
(a lot cannot exceed the item's unbatched remainder).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient

ITEMS_URL = "/api/v1/items"
BATCHES_URL = "/api/v1/batches"
MOVEMENTS_URL = "/api/v1/stock-movements"


async def _create_item(client: AsyncClient, *, stock: str = "100", sku: str | None = None) -> str:
    resp = await client.post(
        ITEMS_URL,
        json={
            "sku": sku or f"ITM-{uuid.uuid4().hex[:8]}",
            "name": "Amoxicillin 250mg",
            "type": "FINISHED",
            "category": "Antibiotic",
            "unit_of_measure": "strip",
            "unit_price": "30.00",
            "stock_quantity": stock,
        },
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _payload(item_id: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "item_id": item_id,
        "batch_number": "LOT-001",
        "expiry_date": "2030-01-01",
        "quantity": "40",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Auth wall
# ---------------------------------------------------------------------------


async def test_create_batch_requires_auth_401(client_with_db: AsyncClient) -> None:
    resp = await client_with_db.post(BATCHES_URL, json=_payload(str(uuid.uuid4())))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "MISSING_TOKEN"


async def test_list_batches_requires_auth_401(client_with_db: AsyncClient) -> None:
    resp = await client_with_db.get(BATCHES_URL)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Create — opening balance (no net stock change)
# ---------------------------------------------------------------------------


async def test_create_opening_balance_batch(authenticated_client: AsyncClient) -> None:
    item_id = await _create_item(authenticated_client, stock="100")
    resp = await authenticated_client.post(BATCHES_URL, json=_payload(item_id, quantity="40"))
    assert resp.status_code == 201, resp.text

    body = resp.json()
    assert body["item_id"] == item_id
    assert body["batch_number"] == "LOT-001"
    assert Decimal(str(body["quantity"])) == Decimal("40")
    assert Decimal(str(body["initial_quantity"])) == Decimal("40")
    assert body["batch_status"] == "QUARANTINE"  # default
    assert body["is_expired"] is False


async def test_create_does_not_change_item_stock_or_write_movement(
    authenticated_client: AsyncClient,
) -> None:
    item_id = await _create_item(authenticated_client, stock="100")
    await authenticated_client.post(BATCHES_URL, json=_payload(item_id, quantity="40"))

    # Item stock is unchanged — a lot only *describes* existing stock.
    item = (await authenticated_client.get(f"{ITEMS_URL}/{item_id}")).json()
    assert Decimal(str(item["stock_quantity"])) == Decimal("100")

    # And no ledger movement was written.
    ledger = (await authenticated_client.get(f"{MOVEMENTS_URL}?item_id={item_id}")).json()
    assert ledger["total"] == 0


async def test_create_with_explicit_released_status(authenticated_client: AsyncClient) -> None:
    item_id = await _create_item(authenticated_client, stock="50")
    resp = await authenticated_client.post(
        BATCHES_URL, json=_payload(item_id, quantity="50", batch_status="RELEASED")
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["batch_status"] == "RELEASED"


# ---------------------------------------------------------------------------
# Reconciliation rule: Σ lot qty ≤ item.stock_quantity
# ---------------------------------------------------------------------------


async def test_lot_may_equal_unbatched_remainder(authenticated_client: AsyncClient) -> None:
    item_id = await _create_item(authenticated_client, stock="100")
    first = await authenticated_client.post(
        BATCHES_URL, json=_payload(item_id, batch_number="A", quantity="100")
    )
    assert first.status_code == 201, first.text
    # Now fully batched — any further lot exceeds the remainder.
    second = await authenticated_client.post(
        BATCHES_URL, json=_payload(item_id, batch_number="B", quantity="1")
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "BATCH_EXCEEDS_UNBATCHED_STOCK"


async def test_cumulative_lots_cannot_exceed_stock(authenticated_client: AsyncClient) -> None:
    item_id = await _create_item(authenticated_client, stock="100")
    await authenticated_client.post(
        BATCHES_URL, json=_payload(item_id, batch_number="A", quantity="30")
    )
    await authenticated_client.post(
        BATCHES_URL, json=_payload(item_id, batch_number="B", quantity="30")
    )
    # 30 + 30 batched, 40 unbatched — 50 is too much.
    resp = await authenticated_client.post(
        BATCHES_URL, json=_payload(item_id, batch_number="C", quantity="50")
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BATCH_EXCEEDS_UNBATCHED_STOCK"


# ---------------------------------------------------------------------------
# Validation / not-found
# ---------------------------------------------------------------------------


async def test_duplicate_batch_number_same_item_409(authenticated_client: AsyncClient) -> None:
    item_id = await _create_item(authenticated_client, stock="100")
    await authenticated_client.post(
        BATCHES_URL, json=_payload(item_id, batch_number="DUP", quantity="10")
    )
    resp = await authenticated_client.post(
        BATCHES_URL, json=_payload(item_id, batch_number="DUP", quantity="10")
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DUPLICATE_BATCH"


async def test_same_batch_number_different_item_ok(authenticated_client: AsyncClient) -> None:
    item_a = await _create_item(authenticated_client, stock="100")
    item_b = await _create_item(authenticated_client, stock="100")
    r1 = await authenticated_client.post(
        BATCHES_URL, json=_payload(item_a, batch_number="SHARED", quantity="10")
    )
    r2 = await authenticated_client.post(
        BATCHES_URL, json=_payload(item_b, batch_number="SHARED", quantity="10")
    )
    assert r1.status_code == 201 and r2.status_code == 201, (r1.text, r2.text)


async def test_create_for_unknown_item_404(authenticated_client: AsyncClient) -> None:
    resp = await authenticated_client.post(BATCHES_URL, json=_payload(str(uuid.uuid4())))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ITEM_NOT_FOUND"


async def test_expiry_before_manufacturing_422(authenticated_client: AsyncClient) -> None:
    item_id = await _create_item(authenticated_client, stock="100")
    resp = await authenticated_client.post(
        BATCHES_URL,
        json=_payload(item_id, manufacturing_date="2030-06-01", expiry_date="2029-01-01"),
    )
    assert resp.status_code == 422


async def test_non_positive_quantity_422(authenticated_client: AsyncClient) -> None:
    item_id = await _create_item(authenticated_client, stock="100")
    resp = await authenticated_client.post(BATCHES_URL, json=_payload(item_id, quantity="0"))
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Read / list / filters
# ---------------------------------------------------------------------------


async def test_get_batch_by_id_and_404(authenticated_client: AsyncClient) -> None:
    item_id = await _create_item(authenticated_client, stock="100")
    created = await authenticated_client.post(BATCHES_URL, json=_payload(item_id, quantity="10"))
    batch_id = created.json()["id"]

    got = await authenticated_client.get(f"{BATCHES_URL}/{batch_id}")
    assert got.status_code == 200
    assert got.json()["id"] == batch_id

    missing = await authenticated_client.get(f"{BATCHES_URL}/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "BATCH_NOT_FOUND"


async def test_list_filters_by_item_status_and_expiry(authenticated_client: AsyncClient) -> None:
    item_id = await _create_item(authenticated_client, stock="100")
    await authenticated_client.post(
        BATCHES_URL,
        json=_payload(
            item_id,
            batch_number="EARLY",
            quantity="20",
            expiry_date="2027-01-01",
            batch_status="RELEASED",
        ),
    )
    await authenticated_client.post(
        BATCHES_URL,
        json=_payload(
            item_id,
            batch_number="LATE",
            quantity="20",
            expiry_date="2031-01-01",
            batch_status="QUARANTINE",
        ),
    )

    by_item = (await authenticated_client.get(f"{BATCHES_URL}?item_id={item_id}")).json()
    assert by_item["total"] == 2
    # ordered soonest expiry first
    assert by_item["items"][0]["batch_number"] == "EARLY"

    released = (
        await authenticated_client.get(f"{BATCHES_URL}?item_id={item_id}&status=RELEASED")
    ).json()
    assert released["total"] == 1 and released["items"][0]["batch_number"] == "EARLY"

    expiring = (
        await authenticated_client.get(
            f"{BATCHES_URL}?item_id={item_id}&expiring_before=2028-01-01"
        )
    ).json()
    assert expiring["total"] == 1 and expiring["items"][0]["batch_number"] == "EARLY"


async def test_is_expired_flag_for_past_expiry(authenticated_client: AsyncClient) -> None:
    item_id = await _create_item(authenticated_client, stock="100")
    # An already-expired legacy lot can legitimately be recorded (then written off).
    resp = await authenticated_client.post(
        BATCHES_URL, json=_payload(item_id, quantity="10", expiry_date="2020-01-01")
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["is_expired"] is True
