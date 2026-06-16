"""Tests for /api/v1/stock-movements — the append-only audit ledger."""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient

ITEMS_URL = "/api/v1/items"
MOVEMENTS_URL = "/api/v1/stock-movements"
ADJUSTMENTS_URL = "/api/v1/stock-movements/adjustments"


async def _create_item_with_stock(
    client: AsyncClient,
    *,
    stock: str = "100",
    sku: str | None = None,
) -> str:
    response = await client.post(
        ITEMS_URL,
        json={
            "sku": sku or f"ITM-{uuid.uuid4().hex[:8]}",
            "name": "Test Item",
            "type": "RAW",
            "category": "Polymer",
            "unit_of_measure": "kg",
            "unit_price": "10.00",
            "stock_quantity": stock,
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _adjustment_payload(item_id: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "item_id": item_id,
        "direction": "OUT",
        "quantity": "10",
        "remarks": "QC reject — line B",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Auth wall
# ---------------------------------------------------------------------------


async def test_list_movements_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.get(MOVEMENTS_URL)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


async def test_create_adjustment_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.post(
        ADJUSTMENTS_URL,
        json=_adjustment_payload(str(uuid.uuid4())),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


# ---------------------------------------------------------------------------
# Append-only API contract
# ---------------------------------------------------------------------------


async def test_no_patch_or_delete_endpoint_for_movements(
    authenticated_client: AsyncClient,
) -> None:
    """The ledger is append-only — there is no API path that mutates
    or deletes a movement row, ever. Pinning this in tests so
    nobody accidentally adds a PATCH/DELETE later."""
    fake_id = uuid.uuid4()
    patch_resp = await authenticated_client.patch(
        f"{MOVEMENTS_URL}/{fake_id}", json={"quantity": "1"}
    )
    delete_resp = await authenticated_client.delete(f"{MOVEMENTS_URL}/{fake_id}")
    # FastAPI returns 405 Method Not Allowed when the path exists but
    # the method isn't registered, 404 when the path doesn't exist.
    # Either is acceptable proof the write isn't exposed.
    assert patch_resp.status_code in (404, 405)
    assert delete_resp.status_code in (404, 405)


# ---------------------------------------------------------------------------
# Adjustment write — input validation
# ---------------------------------------------------------------------------


async def test_create_adjustment_with_unknown_item_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(
        ADJUSTMENTS_URL,
        json=_adjustment_payload(str(uuid.uuid4())),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ITEM_NOT_FOUND"


async def test_create_adjustment_with_zero_quantity_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    item_id = await _create_item_with_stock(authenticated_client)
    response = await authenticated_client.post(
        ADJUSTMENTS_URL, json=_adjustment_payload(item_id, quantity="0")
    )
    assert response.status_code == 422


async def test_create_adjustment_with_negative_quantity_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    item_id = await _create_item_with_stock(authenticated_client)
    response = await authenticated_client.post(
        ADJUSTMENTS_URL, json=_adjustment_payload(item_id, quantity="-5")
    )
    assert response.status_code == 422


async def test_create_adjustment_missing_remarks_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    """``remarks`` is the accountability gate — required, non-empty."""
    item_id = await _create_item_with_stock(authenticated_client)
    response = await authenticated_client.post(
        ADJUSTMENTS_URL,
        json={
            "item_id": item_id,
            "direction": "OUT",
            "quantity": "5",
            # remarks deliberately omitted
        },
    )
    assert response.status_code == 422


async def test_create_adjustment_with_blank_remarks_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    """``str_strip_whitespace`` makes whitespace-only remarks effectively empty."""
    item_id = await _create_item_with_stock(authenticated_client)
    response = await authenticated_client.post(
        ADJUSTMENTS_URL, json=_adjustment_payload(item_id, remarks="   ")
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Adjustment write — behaviour and balance correctness
# ---------------------------------------------------------------------------


async def test_create_adjustment_in_increases_stock_and_records_row(
    authenticated_client: AsyncClient,
) -> None:
    item_id = await _create_item_with_stock(authenticated_client, stock="50")

    response = await authenticated_client.post(
        ADJUSTMENTS_URL,
        json=_adjustment_payload(
            item_id,
            direction="IN",
            quantity="25",
            remarks="Recount correction",
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["item_id"] == item_id
    assert body["direction"] == "IN"
    assert body["reason"] == "ADJUSTMENT"
    # Numeric comparisons via Decimal — robust to trailing-zero precision
    # differences across columns (items.stock_quantity is Numeric(20,4),
    # stock_movements.stock_* is Numeric(14,3)).
    assert Decimal(body["quantity"]) == Decimal("25")
    assert Decimal(body["stock_before"]) == Decimal("50")
    assert Decimal(body["stock_after"]) == Decimal("75")
    assert Decimal(body["signed_quantity"]) == Decimal("25")
    assert body["reference_type"] is None
    assert body["reference_id"] is None
    assert body["remarks"] == "Recount correction"

    # Item's denormalized stock is updated atomically.
    item_resp = await authenticated_client.get(f"{ITEMS_URL}/{item_id}")
    assert Decimal(item_resp.json()["stock_quantity"]) == Decimal("75")


async def test_create_adjustment_out_decreases_stock_and_records_row(
    authenticated_client: AsyncClient,
) -> None:
    item_id = await _create_item_with_stock(authenticated_client, stock="100")

    response = await authenticated_client.post(
        ADJUSTMENTS_URL,
        json=_adjustment_payload(item_id, direction="OUT", quantity="40"),
    )

    assert response.status_code == 201
    body = response.json()
    assert Decimal(body["stock_before"]) == Decimal("100")
    assert Decimal(body["stock_after"]) == Decimal("60")
    assert Decimal(body["signed_quantity"]) == Decimal("-40")

    item_resp = await authenticated_client.get(f"{ITEMS_URL}/{item_id}")
    assert Decimal(item_resp.json()["stock_quantity"]) == Decimal("60")


async def test_create_adjustment_out_insufficient_stock_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    """The headline invariant — OUT cannot push stock below zero."""
    item_id = await _create_item_with_stock(authenticated_client, stock="20")

    response = await authenticated_client.post(
        ADJUSTMENTS_URL,
        json=_adjustment_payload(item_id, direction="OUT", quantity="21"),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_STOCK"

    # Stock unchanged after the failed attempt.
    item_resp = await authenticated_client.get(f"{ITEMS_URL}/{item_id}")
    assert Decimal(item_resp.json()["stock_quantity"]) == Decimal("20")


async def test_create_adjustment_records_actor_user_id(
    authenticated_client: AsyncClient,
) -> None:
    item_id = await _create_item_with_stock(authenticated_client)
    response = await authenticated_client.post(
        ADJUSTMENTS_URL, json=_adjustment_payload(item_id, direction="IN", quantity="5")
    )
    body = response.json()
    assert uuid.UUID(body["created_by_user_id"])


async def test_sequential_adjustments_chain_balances_correctly(
    authenticated_client: AsyncClient,
) -> None:
    """Each ledger row's ``stock_before`` equals the previous row's
    ``stock_after``. This is the audit-trail invariant."""
    item_id = await _create_item_with_stock(authenticated_client, stock="100")

    first = await authenticated_client.post(
        ADJUSTMENTS_URL,
        json=_adjustment_payload(item_id, direction="IN", quantity="50", remarks="receive"),
    )
    second = await authenticated_client.post(
        ADJUSTMENTS_URL,
        json=_adjustment_payload(item_id, direction="OUT", quantity="20", remarks="QC"),
    )
    third = await authenticated_client.post(
        ADJUSTMENTS_URL,
        json=_adjustment_payload(item_id, direction="OUT", quantity="30", remarks="ship"),
    )

    a = first.json()
    b = second.json()
    c = third.json()
    assert Decimal(a["stock_before"]) == Decimal("100")
    assert Decimal(a["stock_after"]) == Decimal("150")
    assert Decimal(b["stock_before"]) == Decimal("150")
    assert Decimal(b["stock_after"]) == Decimal("130")
    assert Decimal(c["stock_before"]) == Decimal("130")
    assert Decimal(c["stock_after"]) == Decimal("100")


# ---------------------------------------------------------------------------
# List filters
# ---------------------------------------------------------------------------


async def test_list_movements_returns_paginated_shape(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.get(MOVEMENTS_URL)
    assert response.status_code == 200
    body = response.json()
    assert {"items", "total", "limit", "offset"} <= body.keys()
    assert body["limit"] == 25
    assert body["offset"] == 0


async def test_list_movements_filter_by_item_id(
    authenticated_client: AsyncClient,
) -> None:
    item_a = await _create_item_with_stock(authenticated_client, sku="ITM-A")
    item_b = await _create_item_with_stock(authenticated_client, sku="ITM-B")
    await authenticated_client.post(
        ADJUSTMENTS_URL, json=_adjustment_payload(item_a, direction="IN", quantity="5")
    )
    await authenticated_client.post(
        ADJUSTMENTS_URL, json=_adjustment_payload(item_b, direction="IN", quantity="7")
    )

    response = await authenticated_client.get(MOVEMENTS_URL, params={"item_id": item_a})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["item_id"] == item_a


async def test_list_movements_filter_by_direction(
    authenticated_client: AsyncClient,
) -> None:
    item_id = await _create_item_with_stock(authenticated_client, stock="100")
    await authenticated_client.post(
        ADJUSTMENTS_URL, json=_adjustment_payload(item_id, direction="IN", quantity="5")
    )
    await authenticated_client.post(
        ADJUSTMENTS_URL, json=_adjustment_payload(item_id, direction="OUT", quantity="3")
    )

    in_resp = await authenticated_client.get(MOVEMENTS_URL, params={"direction": "IN"})
    out_resp = await authenticated_client.get(MOVEMENTS_URL, params={"direction": "OUT"})

    assert in_resp.json()["total"] == 1
    assert in_resp.json()["items"][0]["direction"] == "IN"
    assert out_resp.json()["total"] == 1
    assert out_resp.json()["items"][0]["direction"] == "OUT"


async def test_list_movements_filter_by_reason(
    authenticated_client: AsyncClient,
) -> None:
    """All Phase 6 writes are ADJUSTMENT — filter pins the field works."""
    item_id = await _create_item_with_stock(authenticated_client)
    await authenticated_client.post(
        ADJUSTMENTS_URL, json=_adjustment_payload(item_id, direction="IN", quantity="5")
    )

    by_adj = await authenticated_client.get(MOVEMENTS_URL, params={"reason": "ADJUSTMENT"})
    by_sale = await authenticated_client.get(MOVEMENTS_URL, params={"reason": "SALE"})

    assert by_adj.json()["total"] == 1
    assert by_sale.json()["total"] == 0


async def test_list_movements_filter_by_date_range(
    authenticated_client: AsyncClient,
) -> None:
    """Both bounds inclusive at the day level."""
    item_id = await _create_item_with_stock(authenticated_client)
    create_resp = await authenticated_client.post(
        ADJUSTMENTS_URL, json=_adjustment_payload(item_id, direction="IN", quantity="5")
    )
    created_at = create_resp.json()["created_at"]
    # Extract the date portion (YYYY-MM-DD).
    on_date = created_at[:10]

    # Filter on the exact day — should include the row.
    inside = await authenticated_client.get(
        MOVEMENTS_URL, params={"date_from": on_date, "date_to": on_date}
    )
    # Filter on an earlier day — should exclude the row.
    outside = await authenticated_client.get(
        MOVEMENTS_URL, params={"date_from": "2000-01-01", "date_to": "2000-01-02"}
    )

    assert inside.json()["total"] >= 1
    assert outside.json()["total"] == 0


# ---------------------------------------------------------------------------
# Adjustment targeting a specific lot (#8)
# ---------------------------------------------------------------------------

BATCHES_URL = "/api/v1/batches"


async def _lot(client: AsyncClient, item_id: str, *, qty: str, batch_number: str = "LOT-1") -> str:
    resp = await client.post(
        BATCHES_URL,
        json={
            "item_id": item_id,
            "batch_number": batch_number,
            "expiry_date": "2035-01-01",
            "quantity": qty,
        },
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


async def _lot_qty(client: AsyncClient, lot_id: str) -> Decimal:
    return Decimal(str((await client.get(f"{BATCHES_URL}/{lot_id}")).json()["quantity"]))


async def test_adjustment_out_with_batch_decrements_lot_and_item(
    authenticated_client: AsyncClient,
) -> None:
    item_id = await _create_item_with_stock(authenticated_client, stock="100")
    lot_id = await _lot(authenticated_client, item_id, qty="100")

    resp = await authenticated_client.post(
        ADJUSTMENTS_URL,
        json=_adjustment_payload(item_id, direction="OUT", quantity="30", batch_id=lot_id),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["batch_id"] == lot_id
    assert await _lot_qty(authenticated_client, lot_id) == Decimal("70")
    item = (await authenticated_client.get(f"{ITEMS_URL}/{item_id}")).json()
    assert Decimal(str(item["stock_quantity"])) == Decimal("70")


async def test_adjustment_in_with_batch_increments_lot_and_item(
    authenticated_client: AsyncClient,
) -> None:
    item_id = await _create_item_with_stock(authenticated_client, stock="100")
    lot_id = await _lot(authenticated_client, item_id, qty="100")

    resp = await authenticated_client.post(
        ADJUSTMENTS_URL,
        json=_adjustment_payload(item_id, direction="IN", quantity="20", batch_id=lot_id),
    )
    assert resp.status_code == 201, resp.text
    assert await _lot_qty(authenticated_client, lot_id) == Decimal("120")
    item = (await authenticated_client.get(f"{ITEMS_URL}/{item_id}")).json()
    assert Decimal(str(item["stock_quantity"])) == Decimal("120")


async def test_adjustment_batch_for_wrong_item_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    item_a = await _create_item_with_stock(authenticated_client, stock="100", sku="ITM-A8")
    item_b = await _create_item_with_stock(authenticated_client, stock="100", sku="ITM-B8")
    lot_b = await _lot(authenticated_client, item_b, qty="100")

    resp = await authenticated_client.post(
        ADJUSTMENTS_URL,
        json=_adjustment_payload(item_a, direction="OUT", quantity="10", batch_id=lot_b),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "BATCH_ITEM_MISMATCH"


async def test_adjustment_out_with_batch_insufficient_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    """The lot has less than the OUT amount → 409, nothing changes (even though
    the item aggregate would have been sufficient)."""
    item_id = await _create_item_with_stock(authenticated_client, stock="100")
    lot_id = await _lot(authenticated_client, item_id, qty="20")

    resp = await authenticated_client.post(
        ADJUSTMENTS_URL,
        json=_adjustment_payload(item_id, direction="OUT", quantity="50", batch_id=lot_id),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INSUFFICIENT_STOCK"

    assert await _lot_qty(authenticated_client, lot_id) == Decimal("20")
    item = (await authenticated_client.get(f"{ITEMS_URL}/{item_id}")).json()
    assert Decimal(str(item["stock_quantity"])) == Decimal("100")
