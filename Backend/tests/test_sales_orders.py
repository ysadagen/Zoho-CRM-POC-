"""Tests for /api/v1/sales-orders — Phase 8.

Two headline tests pin the core promises of this phase:

* ``test_ship_so_increases_decreases_stock_and_records_ledger`` — a
  successful ship deducts stock for every line, writes one
  ``stock_movements`` row per line (OUT, SALE, reference_type=SALES_ORDER),
  flips status to SHIPPED, stamps ``shipped_date``. All in one
  transaction.
* ``test_ship_so_insufficient_stock_rolls_back_all_lines`` — the
  failure that Phase 6's SELECT FOR UPDATE was built to protect against.
  If any line would push stock below zero, the *entire* transaction
  rolls back — earlier lines' stock is unchanged, no partial ledger.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.item import Item

SALES_ORDERS_URL = "/api/v1/sales-orders"
CUSTOMERS_URL = "/api/v1/customers"
ITEMS_URL = "/api/v1/items"
STOCK_MOVEMENTS_URL = "/api/v1/stock-movements"

# Format pinned by the service's so_number generator: SO-YYYYMM-NNNNNN.
SO_NUMBER_RE = re.compile(r"^SO-\d{6}-\d{6}$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_customer(client: AsyncClient) -> str:
    response = await client.post(
        CUSTOMERS_URL,
        json={
            "company_name": f"Test Customer {uuid.uuid4().hex[:6]}",
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
    unit_price: str = "100.00",
) -> str:
    response = await client.post(
        ITEMS_URL,
        json={
            "sku": sku or f"ITM-{uuid.uuid4().hex[:8]}",
            "name": "Test Item",
            "type": "FINISHED",
            "category": "Bottle",
            "unit_of_measure": "pcs",
            "unit_price": unit_price,
            "stock_quantity": stock,
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _line(
    item_id: str,
    *,
    quantity: str = "1",
    unit_price: str | None = "100.00",
    batch_id: str | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {"item_id": item_id, "quantity": quantity}
    if unit_price is not None:
        body["unit_price"] = unit_price
    if batch_id is not None:
        body["batch_id"] = batch_id
    return body


def _so_payload(
    customer_id: str,
    items: list[dict[str, object]],
    **overrides: object,
) -> dict[str, object]:
    base: dict[str, object] = {"customer_id": customer_id, "items": items}
    base.update(overrides)
    return base


async def _lot(
    client: AsyncClient,
    item_id: str,
    *,
    quantity: str,
    batch_number: str = "LOT-1",
    expiry: str = "2035-01-01",
    batch_status: str = "RELEASED",
) -> str:
    """Record an opening-balance lot so the item's stock is lot-tracked.

    Only lot-tracked, non-expired, **released** stock is shippable, so ship
    tests create their lots RELEASED by default. Pass
    ``batch_status="QUARANTINE"`` to exercise the not-yet-QC-released path.
    """
    resp = await client.post(
        "/api/v1/batches",
        json={
            "item_id": item_id,
            "batch_number": batch_number,
            "expiry_date": expiry,
            "quantity": quantity,
            "batch_status": batch_status,
        },
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


# ---------------------------------------------------------------------------
# Auth wall
# ---------------------------------------------------------------------------


async def test_create_so_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.post(
        SALES_ORDERS_URL,
        json=_so_payload(str(uuid.uuid4()), [_line(str(uuid.uuid4()))]),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


async def test_list_sos_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.get(SALES_ORDERS_URL)
    assert response.status_code == 401


async def test_get_so_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.get(f"{SALES_ORDERS_URL}/{uuid.uuid4()}")
    assert response.status_code == 401


async def test_ship_so_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.post(f"{SALES_ORDERS_URL}/{uuid.uuid4()}/ship")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Append-only / no-edit API contract
# ---------------------------------------------------------------------------


async def test_no_patch_or_delete_endpoint_for_sales_orders(
    authenticated_client: AsyncClient,
) -> None:
    """No PATCH or DELETE — DRAFTs sit and SHIPPEDs are terminal."""
    fake = uuid.uuid4()
    patch_resp = await authenticated_client.patch(f"{SALES_ORDERS_URL}/{fake}", json={"notes": "x"})
    delete_resp = await authenticated_client.delete(f"{SALES_ORDERS_URL}/{fake}")
    assert patch_resp.status_code in (404, 405)
    assert delete_resp.status_code in (404, 405)


# ---------------------------------------------------------------------------
# Create — Pydantic / shape validation
# ---------------------------------------------------------------------------


async def test_create_so_no_lines_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    response = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, []),
    )
    assert response.status_code == 422


async def test_create_so_zero_quantity_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client)
    response = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, quantity="0")]),
    )
    assert response.status_code == 422


async def test_create_so_negative_quantity_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client)
    response = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, quantity="-3")]),
    )
    assert response.status_code == 422


async def test_create_so_negative_unit_price_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client)
    response = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, unit_price="-1.00")]),
    )
    assert response.status_code == 422


async def test_create_so_unknown_field_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    """Schema must use extra='forbid' per CLAUDE.md §10.4."""
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client)
    payload = _so_payload(customer_id, [_line(item_id)])
    payload["nonsense_field"] = "boom"
    response = await authenticated_client.post(SALES_ORDERS_URL, json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Create — business rule validation
# ---------------------------------------------------------------------------


async def test_create_so_unknown_customer_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    item_id = await _create_item(authenticated_client)
    response = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(str(uuid.uuid4()), [_line(item_id)]),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"


async def test_create_so_inactive_customer_returns_404(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client)
    customer = await db_session.scalar(
        select(Customer).where(Customer.id == uuid.UUID(customer_id))
    )
    assert customer is not None
    customer.is_active = False
    await db_session.commit()

    response = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id)]),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"


async def test_create_so_unknown_item_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    response = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(str(uuid.uuid4()))]),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ITEM_NOT_FOUND"


async def test_create_so_inactive_item_returns_404(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client)
    item = await db_session.scalar(select(Item).where(Item.id == uuid.UUID(item_id)))
    assert item is not None
    item.is_active = False
    await db_session.commit()

    response = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id)]),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ITEM_NOT_FOUND"


async def test_create_so_duplicate_item_lines_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client)
    response = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(
            customer_id,
            [_line(item_id, quantity="2"), _line(item_id, quantity="3")],
        ),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_LINE_ITEM"


# ---------------------------------------------------------------------------
# Create — happy paths
# ---------------------------------------------------------------------------


async def test_create_so_happy_with_explicit_prices(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_a = await _create_item(authenticated_client)
    item_b = await _create_item(authenticated_client)

    response = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(
            customer_id,
            [
                _line(item_a, quantity="10", unit_price="12.50"),
                _line(item_b, quantity="4", unit_price="100.00"),
            ],
            notes="trial dispatch",
            expected_delivery_date="2026-07-15",
        ),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert SO_NUMBER_RE.match(body["so_number"]), body["so_number"]
    assert body["customer_id"] == customer_id
    assert body["status"] == "DRAFT"
    assert body["shipped_date"] is None
    assert body["expected_delivery_date"] == "2026-07-15"
    assert body["notes"] == "trial dispatch"
    # 10 * 12.50 + 4 * 100.00 = 525.00
    assert Decimal(body["subtotal"]) == Decimal("525.00")
    assert Decimal(body["total"]) == Decimal("525.00")
    assert len(body["items"]) == 2

    by_item = {line["item_id"]: line for line in body["items"]}
    assert Decimal(by_item[item_a]["line_total"]) == Decimal("125.00")
    assert Decimal(by_item[item_b]["line_total"]) == Decimal("400.00")


async def test_create_so_with_single_line_item(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client)
    response = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(
            customer_id,
            [_line(item_id, quantity="7.500", unit_price="20.00")],
        ),
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["items"]) == 1
    assert Decimal(body["subtotal"]) == Decimal("150.00")


async def test_create_so_auto_fills_unit_price_from_item_list_price(
    authenticated_client: AsyncClient,
) -> None:
    """When ``unit_price`` is omitted, the service uses the item's
    catalog ``unit_price`` (the list price). Phase 1 has no
    customer-specific pricing table; every customer pays the list
    price unless the SO explicitly overrides per line.
    """
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, unit_price="42.00")

    response = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(
            customer_id,
            [_line(item_id, quantity="3", unit_price=None)],
        ),
    )
    assert response.status_code == 201, response.text
    line = response.json()["items"][0]
    assert Decimal(line["unit_price"]) == Decimal("42.00")
    assert Decimal(line["line_total"]) == Decimal("126.00")


async def test_create_so_explicit_price_overrides_list_price(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, unit_price="200.00")

    response = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(
            customer_id,
            [_line(item_id, quantity="5", unit_price="50.00")],
        ),
    )
    assert response.status_code == 201
    line = response.json()["items"][0]
    assert Decimal(line["unit_price"]) == Decimal("50.00")


async def test_create_so_generates_unique_sequential_so_numbers(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client)
    first = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id)]),
    )
    second = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id)]),
    )
    assert first.status_code == 201
    assert second.status_code == 201
    n1 = first.json()["so_number"]
    n2 = second.json()["so_number"]
    assert SO_NUMBER_RE.match(n1)
    assert SO_NUMBER_RE.match(n2)
    assert n1 != n2


async def test_create_so_does_not_require_stock_to_be_available(
    authenticated_client: AsyncClient,
) -> None:
    """An operator may book a DRAFT SO knowing stock will be
    procured before shipment. Stock is only enforced at ship-time."""
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="0")
    response = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, quantity="50")]),
    )
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


async def test_get_so_returns_full_payload_with_lines(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client)
    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, quantity="3", unit_price="10")]),
    )
    so_id = created.json()["id"]

    response = await authenticated_client.get(f"{SALES_ORDERS_URL}/{so_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == so_id
    assert body["customer_id"] == customer_id
    assert len(body["items"]) == 1
    assert body["items"][0]["item_id"] == item_id


async def test_get_so_not_found_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.get(f"{SALES_ORDERS_URL}/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SALES_ORDER_NOT_FOUND"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


async def test_list_sos_paginated_envelope_and_filters(
    authenticated_client: AsyncClient,
) -> None:
    customer_a = await _create_customer(authenticated_client)
    customer_b = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client)

    for _ in range(3):
        await authenticated_client.post(
            SALES_ORDERS_URL,
            json=_so_payload(customer_a, [_line(item_id)]),
        )
    await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_b, [_line(item_id)]),
    )

    resp = await authenticated_client.get(SALES_ORDERS_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"items", "total", "limit", "offset"}
    assert body["total"] == 4

    resp = await authenticated_client.get(SALES_ORDERS_URL, params={"customer_id": customer_a})
    assert resp.json()["total"] == 3

    resp = await authenticated_client.get(SALES_ORDERS_URL, params={"limit": 2, "offset": 0})
    assert len(resp.json()["items"]) == 2


async def test_list_sos_filter_by_status(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="100")
    await _lot(authenticated_client, item_id, quantity="100")
    draft = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, quantity="2", unit_price="5")]),
    )
    to_ship = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, quantity="2", unit_price="5")]),
    )
    await authenticated_client.post(f"{SALES_ORDERS_URL}/{to_ship.json()['id']}/ship")

    resp_draft = await authenticated_client.get(SALES_ORDERS_URL, params={"status": "DRAFT"})
    resp_shipped = await authenticated_client.get(SALES_ORDERS_URL, params={"status": "SHIPPED"})
    draft_ids = {p["id"] for p in resp_draft.json()["items"]}
    shipped_ids = {p["id"] for p in resp_shipped.json()["items"]}
    assert draft.json()["id"] in draft_ids
    assert to_ship.json()["id"] in shipped_ids


# ---------------------------------------------------------------------------
# Ship — the keystone tests
# ---------------------------------------------------------------------------


async def test_ship_so_decreases_stock_and_records_ledger(
    authenticated_client: AsyncClient,
) -> None:
    """Headline test: a successful ship (1) decrements
    ``items.stock_quantity`` for every line, (2) inserts one
    ``stock_movements`` row per line with
    ``direction=OUT, reason=SALE, reference_type='SALES_ORDER',
    reference_id=so.id``, (3) flips SO status to SHIPPED and stamps
    ``shipped_date``. All in one transaction."""
    customer_id = await _create_customer(authenticated_client)
    item_a = await _create_item(authenticated_client, stock="100")
    item_b = await _create_item(authenticated_client, stock="50")
    await _lot(authenticated_client, item_a, quantity="100")
    await _lot(authenticated_client, item_b, quantity="50")

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(
            customer_id,
            [
                _line(item_a, quantity="25", unit_price="12.00"),
                _line(item_b, quantity="30", unit_price="100.00"),
            ],
        ),
    )
    so_id = created.json()["id"]
    so_number = created.json()["so_number"]

    response = await authenticated_client.post(f"{SALES_ORDERS_URL}/{so_id}/ship")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "SHIPPED"
    assert body["shipped_date"] == date.today().isoformat()

    resp_a = await authenticated_client.get(f"{ITEMS_URL}/{item_a}")
    resp_b = await authenticated_client.get(f"{ITEMS_URL}/{item_b}")
    assert Decimal(resp_a.json()["stock_quantity"]) == Decimal("75")
    assert Decimal(resp_b.json()["stock_quantity"]) == Decimal("20")

    ledger_a = await authenticated_client.get(STOCK_MOVEMENTS_URL, params={"item_id": item_a})
    ledger_b = await authenticated_client.get(STOCK_MOVEMENTS_URL, params={"item_id": item_b})
    movs_a = ledger_a.json()["items"]
    movs_b = ledger_b.json()["items"]
    assert len(movs_a) == 1
    assert len(movs_b) == 1
    for mov, item_id, before, qty, after in (
        (movs_a[0], item_a, "100", "25", "75"),
        (movs_b[0], item_b, "50", "30", "20"),
    ):
        assert mov["item_id"] == item_id
        assert mov["direction"] == "OUT"
        assert mov["reason"] == "SALE"
        assert mov["reference_type"] == "SALES_ORDER"
        assert mov["reference_id"] == so_id
        assert Decimal(mov["quantity"]) == Decimal(qty)
        assert Decimal(mov["stock_before"]) == Decimal(before)
        assert Decimal(mov["stock_after"]) == Decimal(after)
        assert so_number in (mov["remarks"] or "")


async def test_ship_so_insufficient_stock_returns_409_and_rolls_back_all_lines(
    authenticated_client: AsyncClient,
) -> None:
    """The Phase 8 failure mode — and the proof of atomicity.

    SO has two lines: line 1 fits in stock; line 2 does not. The ship
    must fail 409 INSUFFICIENT_STOCK and roll back **everything** —
    line 1's stock is unchanged, no ledger rows written, SO stays DRAFT.
    This pins the single-transaction promise of ship_so.
    """
    customer_id = await _create_customer(authenticated_client)
    item_a = await _create_item(authenticated_client, stock="100")
    item_b = await _create_item(authenticated_client, stock="5")  # too little
    await _lot(authenticated_client, item_a, quantity="100")
    await _lot(authenticated_client, item_b, quantity="5")

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(
            customer_id,
            [
                _line(item_a, quantity="10", unit_price="1"),
                _line(item_b, quantity="50", unit_price="1"),  # 50 > 5
            ],
        ),
    )
    so_id = created.json()["id"]

    response = await authenticated_client.post(f"{SALES_ORDERS_URL}/{so_id}/ship")
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "INSUFFICIENT_STOCK"

    # Stock untouched on BOTH items — atomicity.
    resp_a = await authenticated_client.get(f"{ITEMS_URL}/{item_a}")
    resp_b = await authenticated_client.get(f"{ITEMS_URL}/{item_b}")
    assert Decimal(resp_a.json()["stock_quantity"]) == Decimal("100")
    assert Decimal(resp_b.json()["stock_quantity"]) == Decimal("5")

    # No ledger rows written for either item.
    ledger_a = await authenticated_client.get(STOCK_MOVEMENTS_URL, params={"item_id": item_a})
    ledger_b = await authenticated_client.get(STOCK_MOVEMENTS_URL, params={"item_id": item_b})
    assert ledger_a.json()["total"] == 0
    assert ledger_b.json()["total"] == 0

    # SO still in DRAFT — can be retried after stock is procured.
    so_resp = await authenticated_client.get(f"{SALES_ORDERS_URL}/{so_id}")
    assert so_resp.json()["status"] == "DRAFT"
    assert so_resp.json()["shipped_date"] is None


async def test_ship_so_twice_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    """Idempotency at the state boundary — a second ship is rejected."""
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="100")
    await _lot(authenticated_client, item_id, quantity="100")
    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, quantity="5", unit_price="1")]),
    )
    so_id = created.json()["id"]
    first = await authenticated_client.post(f"{SALES_ORDERS_URL}/{so_id}/ship")
    second = await authenticated_client.post(f"{SALES_ORDERS_URL}/{so_id}/ship")
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "SO_NOT_DRAFT"

    item_resp = await authenticated_client.get(f"{ITEMS_URL}/{item_id}")
    assert Decimal(item_resp.json()["stock_quantity"]) == Decimal("95")


async def test_ship_so_not_found_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(f"{SALES_ORDERS_URL}/{uuid.uuid4()}/ship")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SALES_ORDER_NOT_FOUND"


# ---------------------------------------------------------------------------
# Ship → FEFO lot consumption (Phase 1D)
# ---------------------------------------------------------------------------


async def _lots_by_number(client: AsyncClient, item_id: str) -> dict[str, dict[str, object]]:
    body = (await client.get(f"/api/v1/batches?item_id={item_id}")).json()
    return {lot["batch_number"]: lot for lot in body["items"]}


async def test_ship_consumes_lots_earliest_expiry_first(
    authenticated_client: AsyncClient,
) -> None:
    """FEFO: a line spanning lots drains the earliest-expiry lot fully before
    touching a later one, writing one OUT movement per lot touched."""
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="100")
    await _lot(
        authenticated_client, item_id, quantity="30", batch_number="EARLY", expiry="2027-01-01"
    )
    await _lot(
        authenticated_client, item_id, quantity="70", batch_number="LATE", expiry="2030-01-01"
    )

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, quantity="50", unit_price="1")]),
    )
    resp = await authenticated_client.post(f"{SALES_ORDERS_URL}/{created.json()['id']}/ship")
    assert resp.status_code == 200, resp.text

    # Earliest-expiry lot fully drained; the later lot covers the rest.
    lots = await _lots_by_number(authenticated_client, item_id)
    assert Decimal(str(lots["EARLY"]["quantity"])) == Decimal("0")
    assert Decimal(str(lots["LATE"]["quantity"])) == Decimal("50")

    # Item stock fell by the full line quantity.
    item = (await authenticated_client.get(f"{ITEMS_URL}/{item_id}")).json()
    assert Decimal(str(item["stock_quantity"])) == Decimal("50")

    # One OUT movement per lot touched, each linked to its lot.
    ledger = (await authenticated_client.get(f"{STOCK_MOVEMENTS_URL}?item_id={item_id}")).json()
    assert ledger["total"] == 2
    by_batch = {m["batch_id"]: m for m in ledger["items"]}
    assert Decimal(str(by_batch[lots["EARLY"]["id"]]["quantity"])) == Decimal("30")
    assert Decimal(str(by_batch[lots["LATE"]["id"]]["quantity"])) == Decimal("20")


async def test_ship_skips_expired_lots(
    authenticated_client: AsyncClient,
) -> None:
    """Stock sitting only in an expired lot cannot ship — expired stock is
    excluded from FEFO, so the order fails 409."""
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="50")
    await _lot(
        authenticated_client, item_id, quantity="50", batch_number="OLD", expiry="2020-01-01"
    )

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, quantity="10", unit_price="1")]),
    )
    resp = await authenticated_client.post(f"{SALES_ORDERS_URL}/{created.json()['id']}/ship")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INSUFFICIENT_STOCK"

    item = (await authenticated_client.get(f"{ITEMS_URL}/{item_id}")).json()
    assert Decimal(str(item["stock_quantity"])) == Decimal("50")  # untouched


async def test_ship_rejects_unbatched_stock(
    authenticated_client: AsyncClient,
) -> None:
    """The pharma rule: only lot-tracked stock ships. An item with 100 in
    stock but only 30 in lots can't ship 50 — even though item stock looks
    sufficient — because the uncovered 20 would be untraceable."""
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="100")
    await _lot(authenticated_client, item_id, quantity="30", batch_number="ONLY")  # 70 unbatched

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, quantity="50", unit_price="1")]),
    )
    resp = await authenticated_client.post(f"{SALES_ORDERS_URL}/{created.json()['id']}/ship")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INSUFFICIENT_STOCK"

    # Nothing consumed — stock, lot, and SO state all intact.
    item = (await authenticated_client.get(f"{ITEMS_URL}/{item_id}")).json()
    assert Decimal(str(item["stock_quantity"])) == Decimal("100")
    lots = await _lots_by_number(authenticated_client, item_id)
    assert Decimal(str(lots["ONLY"]["quantity"])) == Decimal("30")
    so = (await authenticated_client.get(f"{SALES_ORDERS_URL}/{created.json()['id']}")).json()
    assert so["status"] == "DRAFT"


# ---------------------------------------------------------------------------
# SO batch selection (#9) — ship from an operator-chosen lot
# ---------------------------------------------------------------------------


async def test_create_so_persists_chosen_batch(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="100")
    lot_id = await _lot(authenticated_client, item_id, quantity="100")

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(
            customer_id, [_line(item_id, quantity="10", unit_price="1", batch_id=lot_id)]
        ),
    )
    assert created.status_code == 201, created.text
    assert created.json()["items"][0]["batch_id"] == lot_id


async def test_create_so_unknown_batch_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="100")

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(
            customer_id,
            [_line(item_id, quantity="10", unit_price="1", batch_id=str(uuid.uuid4()))],
        ),
    )
    assert created.status_code == 404
    assert created.json()["error"]["code"] == "BATCH_NOT_FOUND"


async def test_create_so_batch_for_wrong_item_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_a = await _create_item(authenticated_client, stock="100")
    item_b = await _create_item(authenticated_client, stock="100")
    other_lot = await _lot(authenticated_client, item_b, quantity="100")

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(
            customer_id, [_line(item_a, quantity="10", unit_price="1", batch_id=other_lot)]
        ),
    )
    assert created.status_code == 422
    assert created.json()["error"]["code"] == "BATCH_ITEM_MISMATCH"


async def test_ship_so_consumes_chosen_lot_overriding_fefo(
    authenticated_client: AsyncClient,
) -> None:
    """The chosen lot ships even when an earlier-expiry lot exists — FEFO
    would have picked the other one, so this proves the override."""
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="200")
    await _lot(
        authenticated_client, item_id, quantity="100", batch_number="LOT-EARLY", expiry="2030-01-01"
    )
    chosen = await _lot(
        authenticated_client, item_id, quantity="100", batch_number="LOT-LATE", expiry="2035-01-01"
    )

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(
            customer_id, [_line(item_id, quantity="30", unit_price="1", batch_id=chosen)]
        ),
    )
    resp = await authenticated_client.post(f"{SALES_ORDERS_URL}/{created.json()['id']}/ship")
    assert resp.status_code == 200, resp.text

    lots = await _lots_by_number(authenticated_client, item_id)
    assert Decimal(str(lots["LOT-LATE"]["quantity"])) == Decimal("70")  # chosen consumed
    assert Decimal(str(lots["LOT-EARLY"]["quantity"])) == Decimal("100")  # FEFO lot untouched

    ledger = (
        await authenticated_client.get(STOCK_MOVEMENTS_URL, params={"item_id": item_id})
    ).json()
    out = [m for m in ledger["items"] if m["direction"] == "OUT"]
    assert len(out) == 1
    assert out[0]["batch_id"] == chosen


async def test_ship_so_chosen_lot_insufficient_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="100")
    small = await _lot(authenticated_client, item_id, quantity="20", batch_number="SMALL")

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(
            customer_id, [_line(item_id, quantity="50", unit_price="1", batch_id=small)]
        ),
    )
    resp = await authenticated_client.post(f"{SALES_ORDERS_URL}/{created.json()['id']}/ship")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INSUFFICIENT_STOCK"

    lots = await _lots_by_number(authenticated_client, item_id)
    assert Decimal(str(lots["SMALL"]["quantity"])) == Decimal("20")  # rolled back


async def test_ship_so_chosen_lot_expired_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="100")
    expired = await _lot(
        authenticated_client, item_id, quantity="100", batch_number="OLD", expiry="2020-01-01"
    )

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(
            customer_id, [_line(item_id, quantity="10", unit_price="1", batch_id=expired)]
        ),
    )
    resp = await authenticated_client.post(f"{SALES_ORDERS_URL}/{created.json()['id']}/ship")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BATCH_NOT_SHIPPABLE"


# ---------------------------------------------------------------------------
# QC status ↔ ship (#7) — recalled/rejected lots stop being shippable
# ---------------------------------------------------------------------------


async def _set_status(client: AsyncClient, lot_id: str, status: str) -> None:
    resp = await client.post(f"/api/v1/batches/{lot_id}/status", json={"status": status})
    assert resp.status_code == 200, resp.text


async def _recall(client: AsyncClient, lot_id: str) -> None:
    """Recall an already-released lot so it's no longer shippable."""
    await _set_status(client, lot_id, "RECALLED")


async def test_ship_so_skips_recalled_lot_via_fefo(
    authenticated_client: AsyncClient,
) -> None:
    """A recalled lot is no longer shippable — FEFO skips it; if it's the only
    lot the ship fails INSUFFICIENT_STOCK and nothing is consumed."""
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="100")
    lot_id = await _lot(authenticated_client, item_id, quantity="100", batch_number="REC")
    await _recall(authenticated_client, lot_id)

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, quantity="10", unit_price="1")]),
    )
    resp = await authenticated_client.post(f"{SALES_ORDERS_URL}/{created.json()['id']}/ship")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INSUFFICIENT_STOCK"

    lots = await _lots_by_number(authenticated_client, item_id)
    assert Decimal(str(lots["REC"]["quantity"])) == Decimal("100")  # untouched


async def test_ship_so_chosen_recalled_lot_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="100")
    lot_id = await _lot(authenticated_client, item_id, quantity="100", batch_number="REC")
    await _recall(authenticated_client, lot_id)

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(
            customer_id, [_line(item_id, quantity="10", unit_price="1", batch_id=lot_id)]
        ),
    )
    resp = await authenticated_client.post(f"{SALES_ORDERS_URL}/{created.json()['id']}/ship")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BATCH_NOT_SHIPPABLE"


# ---------------------------------------------------------------------------
# QC release gating — only RELEASED stock ships (quarantine is held back)
# ---------------------------------------------------------------------------


async def test_ship_so_skips_quarantine_lot_via_fefo(
    authenticated_client: AsyncClient,
) -> None:
    """Quarantine-held stock is not shippable: FEFO ignores it, and if it's the
    only lot the ship fails INSUFFICIENT_STOCK with nothing consumed."""
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="100")
    await _lot(
        authenticated_client,
        item_id,
        quantity="100",
        batch_number="QTN",
        batch_status="QUARANTINE",
    )

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, quantity="10", unit_price="1")]),
    )
    resp = await authenticated_client.post(f"{SALES_ORDERS_URL}/{created.json()['id']}/ship")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INSUFFICIENT_STOCK"

    lots = await _lots_by_number(authenticated_client, item_id)
    assert Decimal(str(lots["QTN"]["quantity"])) == Decimal("100")  # untouched


async def test_ship_so_succeeds_after_releasing_quarantine_lot(
    authenticated_client: AsyncClient,
) -> None:
    """Releasing a quarantine lot makes it shippable; the ship then consumes it."""
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="100")
    lot_id = await _lot(
        authenticated_client,
        item_id,
        quantity="100",
        batch_number="QTN",
        batch_status="QUARANTINE",
    )

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, quantity="40", unit_price="1")]),
    )
    so_id = created.json()["id"]

    # Before release: not shippable.
    blocked = await authenticated_client.post(f"{SALES_ORDERS_URL}/{so_id}/ship")
    assert blocked.status_code == 409

    # Release, then ship succeeds.
    await _set_status(authenticated_client, lot_id, "RELEASED")
    shipped = await authenticated_client.post(f"{SALES_ORDERS_URL}/{so_id}/ship")
    assert shipped.status_code == 200, shipped.text
    assert shipped.json()["status"] == "SHIPPED"

    lots = await _lots_by_number(authenticated_client, item_id)
    assert Decimal(str(lots["QTN"]["quantity"])) == Decimal("60")  # 100 - 40


async def test_ship_so_chosen_quarantine_lot_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    """Explicitly picking a quarantine lot is rejected — only RELEASED ships."""
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="100")
    lot_id = await _lot(
        authenticated_client,
        item_id,
        quantity="100",
        batch_number="QTN",
        batch_status="QUARANTINE",
    )

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(
            customer_id, [_line(item_id, quantity="10", unit_price="1", batch_id=lot_id)]
        ),
    )
    resp = await authenticated_client.post(f"{SALES_ORDERS_URL}/{created.json()['id']}/ship")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BATCH_NOT_SHIPPABLE"


# ---------------------------------------------------------------------------
# Batch traceability — the consumed lot is recorded on the shipped SO line
# ---------------------------------------------------------------------------


async def test_ship_so_single_lot_stamps_batch_id_on_line(
    authenticated_client: AsyncClient,
) -> None:
    """A line fulfilled FEFO from a single lot gets that lot stamped on the SO
    line for at-a-glance traceability (was NULL before)."""
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="100")
    lot_id = await _lot(authenticated_client, item_id, quantity="100", batch_number="ONE")

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, quantity="30", unit_price="1")]),
    )
    so_id = created.json()["id"]
    # Created via FEFO (no chosen lot) → line batch_id starts NULL.
    assert created.json()["items"][0]["batch_id"] is None

    await authenticated_client.post(f"{SALES_ORDERS_URL}/{so_id}/ship")

    detail = (await authenticated_client.get(f"{SALES_ORDERS_URL}/{so_id}")).json()
    assert detail["items"][0]["batch_id"] == lot_id


async def test_ship_so_multi_lot_leaves_line_batch_id_null(
    authenticated_client: AsyncClient,
) -> None:
    """A line split across several lots leaves the line batch_id NULL — one
    column can't name many lots; the full split lives in the ledger."""
    customer_id = await _create_customer(authenticated_client)
    item_id = await _create_item(authenticated_client, stock="100")
    await _lot(
        authenticated_client, item_id, quantity="20", batch_number="EARLY", expiry="2030-01-01"
    )
    await _lot(
        authenticated_client, item_id, quantity="50", batch_number="LATE", expiry="2031-01-01"
    )

    created = await authenticated_client.post(
        SALES_ORDERS_URL,
        json=_so_payload(customer_id, [_line(item_id, quantity="40", unit_price="1")]),
    )
    so_id = created.json()["id"]
    await authenticated_client.post(f"{SALES_ORDERS_URL}/{so_id}/ship")

    detail = (await authenticated_client.get(f"{SALES_ORDERS_URL}/{so_id}")).json()
    assert detail["items"][0]["batch_id"] is None
    # The ledger has one OUT row per lot touched, each carrying its batch.
    ledger = (await authenticated_client.get(f"/api/v1/stock-movements?item_id={item_id}")).json()
    out_lots = {m["batch_id"] for m in ledger["items"] if m["direction"] == "OUT"}
    assert len(out_lots) == 2
