"""Tests for /api/v1/purchase-orders — Phase 7.

The headline test in this file is
``test_receive_po_increases_stock_and_records_ledger`` — it pins the
core promise of Phase 7: receiving a PO is **transactional** (stock
rises, ledger row written, status flips) and **idempotent at the
state boundary** (second receive returns 409, not a silent no-op).
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item
from app.models.vendor import Vendor

PURCHASE_ORDERS_URL = "/api/v1/purchase-orders"
VENDORS_URL = "/api/v1/vendors"
ITEMS_URL = "/api/v1/items"
STOCK_MOVEMENTS_URL = "/api/v1/stock-movements"

# Format pinned by the service's po_number generator: PO-YYYYMM-NNNNNN.
PO_NUMBER_RE = re.compile(r"^PO-\d{6}-\d{6}$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_vendor(client: AsyncClient) -> str:
    response = await client.post(
        VENDORS_URL,
        json={
            "vendor_name": f"Test Vendor {uuid.uuid4().hex[:6]}",
            "contact_person": "Test Contact",
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _create_item(
    client: AsyncClient,
    *,
    sku: str | None = None,
    stock: str = "0",
) -> str:
    response = await client.post(
        ITEMS_URL,
        json={
            "sku": sku or f"ITM-{uuid.uuid4().hex[:8]}",
            "name": "Test Item",
            "type": "RAW",
            "category": "Polymer",
            "unit_of_measure": "kg",
            "unit_price": "100.00",
            "stock_quantity": stock,
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _create_term(
    client: AsyncClient,
    vendor_id: str,
    item_id: str,
    *,
    rate: str = "150.00",
    discount_percent: str = "0",
    effective_from: str = "2020-01-01",
) -> str:
    response = await client.post(
        f"{VENDORS_URL}/{vendor_id}/terms",
        json={
            "item_id": item_id,
            "rate": rate,
            "discount_percent": discount_percent,
            "effective_from": effective_from,
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _line(
    item_id: str,
    *,
    quantity: str = "10",
    unit_price: str | None = "100.00",
) -> dict[str, object]:
    body: dict[str, object] = {"item_id": item_id, "quantity": quantity}
    if unit_price is not None:
        body["unit_price"] = unit_price
    return body


def _po_payload(
    vendor_id: str,
    items: list[dict[str, object]],
    **overrides: object,
) -> dict[str, object]:
    base: dict[str, object] = {"vendor_id": vendor_id, "items": items}
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Auth wall
# ---------------------------------------------------------------------------


async def test_create_po_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(str(uuid.uuid4()), [_line(str(uuid.uuid4()))]),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


async def test_list_pos_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.get(PURCHASE_ORDERS_URL)
    assert response.status_code == 401


async def test_get_po_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.get(f"{PURCHASE_ORDERS_URL}/{uuid.uuid4()}")
    assert response.status_code == 401


async def test_receive_po_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.post(f"{PURCHASE_ORDERS_URL}/{uuid.uuid4()}/receive")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Append-only / no-edit API contract
# ---------------------------------------------------------------------------


async def test_no_patch_or_delete_endpoint_for_purchase_orders(
    authenticated_client: AsyncClient,
) -> None:
    """Phase 7 deliberately exposes no PATCH/DELETE — DRAFTs sit and
    RECEIVEDs are terminal. Pinning this in a test so a future
    contributor doesn't quietly add one."""
    fake = uuid.uuid4()
    patch_resp = await authenticated_client.patch(
        f"{PURCHASE_ORDERS_URL}/{fake}", json={"notes": "x"}
    )
    delete_resp = await authenticated_client.delete(f"{PURCHASE_ORDERS_URL}/{fake}")
    assert patch_resp.status_code in (404, 405)
    assert delete_resp.status_code in (404, 405)


# ---------------------------------------------------------------------------
# Create — Pydantic / shape validation
# ---------------------------------------------------------------------------


async def test_create_po_no_lines_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    response = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, []),
    )
    assert response.status_code == 422


async def test_create_po_zero_quantity_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    response = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, [_line(item_id, quantity="0")]),
    )
    assert response.status_code == 422


async def test_create_po_negative_quantity_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    response = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, [_line(item_id, quantity="-5")]),
    )
    assert response.status_code == 422


async def test_create_po_negative_unit_price_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    response = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, [_line(item_id, unit_price="-1.00")]),
    )
    assert response.status_code == 422


async def test_create_po_unknown_field_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    """Schema must use extra='forbid' per CLAUDE.md §10.4."""
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    payload = _po_payload(vendor_id, [_line(item_id)])
    payload["nonsense_field"] = "boom"
    response = await authenticated_client.post(PURCHASE_ORDERS_URL, json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Create — business rule validation
# ---------------------------------------------------------------------------


async def test_create_po_unknown_vendor_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    item_id = await _create_item(authenticated_client)
    response = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(str(uuid.uuid4()), [_line(item_id)]),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VENDOR_NOT_FOUND"


async def test_create_po_inactive_vendor_returns_404(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    vendor = await db_session.scalar(select(Vendor).where(Vendor.id == uuid.UUID(vendor_id)))
    assert vendor is not None
    vendor.is_active = False
    await db_session.commit()

    response = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, [_line(item_id)]),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VENDOR_NOT_FOUND"


async def test_create_po_unknown_item_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    response = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, [_line(str(uuid.uuid4()))]),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ITEM_NOT_FOUND"


async def test_create_po_inactive_item_returns_404(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    item = await db_session.scalar(select(Item).where(Item.id == uuid.UUID(item_id)))
    assert item is not None
    item.is_active = False
    await db_session.commit()

    response = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, [_line(item_id)]),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ITEM_NOT_FOUND"


async def test_create_po_duplicate_item_lines_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    """Same item appearing twice in the payload is rejected.

    Keeps the line-count semantics clean and makes the UNIQUE
    (purchase_order_id, item_id) DB index a coherent backstop rather
    than a confusing failure mode.
    """
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    response = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(
            vendor_id,
            [_line(item_id, quantity="5"), _line(item_id, quantity="3")],
        ),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_LINE_ITEM"


async def test_create_po_missing_price_and_no_vendor_term_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    response = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, [_line(item_id, unit_price=None)]),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PRICE_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Create — happy paths
# ---------------------------------------------------------------------------


async def test_create_po_happy_with_explicit_prices(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_a = await _create_item(authenticated_client)
    item_b = await _create_item(authenticated_client)

    response = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(
            vendor_id,
            [
                _line(item_a, quantity="10", unit_price="12.50"),
                _line(item_b, quantity="4", unit_price="100.00"),
            ],
            notes="initial stock-up",
            expected_delivery_date="2026-07-15",
        ),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert PO_NUMBER_RE.match(body["po_number"]), body["po_number"]
    assert body["vendor_id"] == vendor_id
    assert body["status"] == "DRAFT"
    assert body["received_date"] is None
    assert body["expected_delivery_date"] == "2026-07-15"
    assert body["notes"] == "initial stock-up"
    # 10 * 12.50 + 4 * 100.00 = 525.00
    assert Decimal(body["subtotal"]) == Decimal("525.00")
    assert Decimal(body["total"]) == Decimal("525.00")
    assert len(body["items"]) == 2

    by_item = {line["item_id"]: line for line in body["items"]}
    assert Decimal(by_item[item_a]["quantity"]) == Decimal("10")
    assert Decimal(by_item[item_a]["unit_price"]) == Decimal("12.50")
    assert Decimal(by_item[item_a]["line_total"]) == Decimal("125.00")
    assert Decimal(by_item[item_b]["line_total"]) == Decimal("400.00")


async def test_create_po_with_single_line_item(
    authenticated_client: AsyncClient,
) -> None:
    """A PO with a single line is valid — partial-line interpretation
    of the spec's "partial line items" test bullet."""
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    response = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(
            vendor_id,
            [_line(item_id, quantity="7.500", unit_price="20.00")],
        ),
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["items"]) == 1
    assert Decimal(body["subtotal"]) == Decimal("150.00")  # 7.500 * 20.00


async def test_create_po_auto_fills_unit_price_from_vendor_term(
    authenticated_client: AsyncClient,
) -> None:
    """When ``unit_price`` is omitted, the service looks up an active
    ``vendor_item_term`` for (vendor, item) and computes the effective
    price as ``rate * (1 - discount_percent / 100)`` (quantized to 2 dp,
    HALF_UP). The term's standing discount is honoured because that's
    the price the vendor actually charges.
    """
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    await _create_term(
        authenticated_client,
        vendor_id,
        item_id,
        rate="200.00",
        discount_percent="10.00",  # effective = 180.00
    )

    response = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, [_line(item_id, quantity="5", unit_price=None)]),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    line = body["items"][0]
    assert Decimal(line["unit_price"]) == Decimal("180.00")
    assert Decimal(line["line_total"]) == Decimal("900.00")  # 5 * 180.00


async def test_create_po_explicit_price_overrides_vendor_term(
    authenticated_client: AsyncClient,
) -> None:
    """If the operator provides ``unit_price``, the vendor-term lookup
    is skipped — explicit beats implicit."""
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    await _create_term(
        authenticated_client,
        vendor_id,
        item_id,
        rate="200.00",
        discount_percent="10.00",
    )

    response = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, [_line(item_id, quantity="5", unit_price="50.00")]),
    )
    assert response.status_code == 201
    line = response.json()["items"][0]
    assert Decimal(line["unit_price"]) == Decimal("50.00")


async def test_create_po_generates_unique_sequential_po_numbers(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    first = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, [_line(item_id)]),
    )
    second = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, [_line(item_id)]),
    )
    assert first.status_code == 201
    assert second.status_code == 201
    n1 = first.json()["po_number"]
    n2 = second.json()["po_number"]
    assert PO_NUMBER_RE.match(n1)
    assert PO_NUMBER_RE.match(n2)
    assert n1 != n2


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


async def test_get_po_returns_full_payload_with_lines(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    created = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, [_line(item_id, quantity="3", unit_price="10")]),
    )
    po_id = created.json()["id"]

    response = await authenticated_client.get(f"{PURCHASE_ORDERS_URL}/{po_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == po_id
    assert body["vendor_id"] == vendor_id
    assert len(body["items"]) == 1
    assert body["items"][0]["item_id"] == item_id


async def test_get_po_not_found_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.get(f"{PURCHASE_ORDERS_URL}/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PURCHASE_ORDER_NOT_FOUND"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


async def test_list_pos_paginated_envelope_and_filters(
    authenticated_client: AsyncClient,
) -> None:
    vendor_a = await _create_vendor(authenticated_client)
    vendor_b = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)

    for _ in range(3):
        await authenticated_client.post(
            PURCHASE_ORDERS_URL,
            json=_po_payload(vendor_a, [_line(item_id)]),
        )
    await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_b, [_line(item_id)]),
    )

    # Full list
    resp = await authenticated_client.get(PURCHASE_ORDERS_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"items", "total", "limit", "offset"}
    assert body["total"] == 4

    # Filter by vendor
    resp = await authenticated_client.get(PURCHASE_ORDERS_URL, params={"vendor_id": vendor_a})
    assert resp.json()["total"] == 3

    # Pagination
    resp = await authenticated_client.get(PURCHASE_ORDERS_URL, params={"limit": 2, "offset": 0})
    assert len(resp.json()["items"]) == 2
    assert resp.json()["total"] == 4


async def test_list_pos_filter_by_status(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    draft = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, [_line(item_id, quantity="2", unit_price="5")]),
    )
    to_receive = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, [_line(item_id, quantity="2", unit_price="5")]),
    )
    await authenticated_client.post(f"{PURCHASE_ORDERS_URL}/{to_receive.json()['id']}/receive")

    resp_draft = await authenticated_client.get(PURCHASE_ORDERS_URL, params={"status": "DRAFT"})
    resp_received = await authenticated_client.get(
        PURCHASE_ORDERS_URL, params={"status": "RECEIVED"}
    )
    draft_ids = {p["id"] for p in resp_draft.json()["items"]}
    received_ids = {p["id"] for p in resp_received.json()["items"]}
    assert draft.json()["id"] in draft_ids
    assert to_receive.json()["id"] in received_ids


# ---------------------------------------------------------------------------
# Receive — the keystone test
# ---------------------------------------------------------------------------


async def test_receive_po_increases_stock_and_records_ledger(
    authenticated_client: AsyncClient,
) -> None:
    """Headline test: a successful receive (1) increments
    ``items.stock_quantity`` for every line, (2) inserts one
    ``stock_movements`` row per line with
    ``direction=IN, reason=PURCHASE, reference_type='PURCHASE_ORDER',
    reference_id=po.id``, (3) flips PO status to RECEIVED and stamps
    ``received_date``. All in one transaction."""
    vendor_id = await _create_vendor(authenticated_client)
    item_a = await _create_item(authenticated_client, stock="0")
    item_b = await _create_item(authenticated_client, stock="50")

    created = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(
            vendor_id,
            [
                _line(item_a, quantity="25", unit_price="12.00"),
                _line(item_b, quantity="30", unit_price="100.00"),
            ],
        ),
    )
    po_id = created.json()["id"]
    po_number = created.json()["po_number"]

    response = await authenticated_client.post(f"{PURCHASE_ORDERS_URL}/{po_id}/receive")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "RECEIVED"
    assert body["received_date"] == date.today().isoformat()

    # Stock on each item rose by the line's quantity.
    resp_a = await authenticated_client.get(f"{ITEMS_URL}/{item_a}")
    resp_b = await authenticated_client.get(f"{ITEMS_URL}/{item_b}")
    assert Decimal(resp_a.json()["stock_quantity"]) == Decimal("25")
    assert Decimal(resp_b.json()["stock_quantity"]) == Decimal("80")

    # One ledger row per line, with the right shape.
    ledger_a = await authenticated_client.get(STOCK_MOVEMENTS_URL, params={"item_id": item_a})
    ledger_b = await authenticated_client.get(STOCK_MOVEMENTS_URL, params={"item_id": item_b})
    movs_a = ledger_a.json()["items"]
    movs_b = ledger_b.json()["items"]
    assert len(movs_a) == 1
    assert len(movs_b) == 1
    for mov, item_id, before, qty, after in (
        (movs_a[0], item_a, "0", "25", "25"),
        (movs_b[0], item_b, "50", "30", "80"),
    ):
        assert mov["item_id"] == item_id
        assert mov["direction"] == "IN"
        assert mov["reason"] == "PURCHASE"
        assert mov["reference_type"] == "PURCHASE_ORDER"
        assert mov["reference_id"] == po_id
        assert Decimal(mov["quantity"]) == Decimal(qty)
        assert Decimal(mov["stock_before"]) == Decimal(before)
        assert Decimal(mov["stock_after"]) == Decimal(after)
        # po_number embedded in remarks for human-readable ledger audit.
        assert po_number in (mov["remarks"] or "")


async def test_receive_po_twice_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    """Idempotency at the state boundary — a second receive is rejected
    rather than silently no-op'd. Prevents double-counting stock."""
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="0")
    created = await authenticated_client.post(
        PURCHASE_ORDERS_URL,
        json=_po_payload(vendor_id, [_line(item_id, quantity="5", unit_price="1")]),
    )
    po_id = created.json()["id"]
    first = await authenticated_client.post(f"{PURCHASE_ORDERS_URL}/{po_id}/receive")
    second = await authenticated_client.post(f"{PURCHASE_ORDERS_URL}/{po_id}/receive")
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "PO_NOT_DRAFT"

    # Stock did not double — second receive was a true no-op on stock.
    item_resp = await authenticated_client.get(f"{ITEMS_URL}/{item_id}")
    assert Decimal(item_resp.json()["stock_quantity"]) == Decimal("5")


async def test_receive_po_not_found_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(f"{PURCHASE_ORDERS_URL}/{uuid.uuid4()}/receive")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PURCHASE_ORDER_NOT_FOUND"
