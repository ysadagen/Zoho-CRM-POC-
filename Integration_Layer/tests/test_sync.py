"""Tests for Track B sync endpoints (POST /api/v1/sync/*).

Strategy:
- ``client_with_db`` gives a real DB session (idempotency_keys, crm_mappings,
  sync_logs persist within the test transaction and roll back at teardown).
- ``respx.mock`` intercepts all outbound httpx calls; we mock Zoho module
  endpoints so no real Zoho traffic is made.
- ``seed_token`` plants a fresh ZohoToken so the token service never tries to
  refresh via OAuth (which would also need mocking).

Each entity covers:
1. Missing internal API key → 401
2. Missing Idempotency-Key header → 422
3. Happy path (Zoho create) → 200, zoho_id returned, crm_mapping written
4. Idempotent replay (same key, same body) → 200, Zoho NOT called again
5. Idempotency conflict (same key, different body) → 409
6. Second call with new key after first succeeds → Zoho UPDATE used
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import respx
from httpx import AsyncClient, Response

from app.core.config import get_settings
from app.core.security import INTERNAL_API_KEY_HEADER
from app.models.zoho_token import ZohoToken

_SETTINGS = get_settings()
_ZOHO = _SETTINGS.zoho_api_base_url.rstrip("/")

_INTERNAL_HEADERS = {INTERNAL_API_KEY_HEADER: _SETTINGS.internal_api_key}

# Zoho always returns the new/updated record id inside data[0].details.id
_ZOHO_ACCOUNT_ID = "ZACC-0001"
_ZOHO_VENDOR_ID = "ZVEN-0001"
_ZOHO_PRODUCT_ID = "ZPRD-0001"
_ZOHO_SO_ID = "ZSO-0001"
_ZOHO_PO_ID = "ZPO-0001"


def _zoho_created(zoho_id: str) -> dict[str, Any]:
    """Successful Zoho POST/PUT response body."""
    return {"data": [{"code": "SUCCESS", "details": {"id": zoho_id}, "status": "success"}]}


def _idempotency_header(key: str | None = None) -> dict[str, str]:
    return {"Idempotency-Key": key or str(uuid.uuid4())}


def _sync_headers(idempotency_key: str | None = None) -> dict[str, str]:
    return {**_INTERNAL_HEADERS, **_idempotency_header(idempotency_key)}


# ---------------------------------------------------------------------------
# Helpers — canonical request payloads per entity
# ---------------------------------------------------------------------------

def _customer_payload(customer_id: str | None = None) -> dict[str, Any]:
    return {
        "id": customer_id or str(uuid.uuid4()),
        "company_name": "Acme Pharma Pvt. Ltd.",
        "email": "acme@example.com",
        "phone": "+91 99887 76655",
        "address": "14 MG Road, Mumbai",
        "gstin": "27AAACA1234B1Z5",
        "customer_code": "C-0099",
        "is_privileged": False,
        "competitive_risk_level": "LOW",
        "notes": "Priority account",
    }


def _vendor_payload(vendor_id: str | None = None) -> dict[str, Any]:
    return {
        "id": vendor_id or str(uuid.uuid4()),
        "vendor_name": "BioSync Chemicals",
        "email": "biosync@example.com",
        "phone": "+91 88776 55443",
        "address": "Plot 9, MIDC, Pune",
        "gstin": "27BBBBB1234C1Z5",
        "notes": "Approved API supplier",
    }


def _item_payload(item_id: str | None = None) -> dict[str, Any]:
    return {
        "id": item_id or str(uuid.uuid4()),
        "name": "Paracetamol 500mg Tablet",
        "sku": "FIN-PARA-500",
        "item_type": "FINISHED",
        "unit_of_measure": "pcs",
        "unit_price": "12.50",
        "reorder_threshold": "500",
    }


def _so_payload(
    so_id: str | None = None,
    customer_id: str | None = None,
    item_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": so_id or str(uuid.uuid4()),
        "so_number": "SO-2026-0001",
        "customer_id": customer_id or str(uuid.uuid4()),
        "order_date": "2026-06-01",
        "status": "DRAFT",
        "notes": "First batch",
        "items": [
            {
                "item_id": item_id or str(uuid.uuid4()),
                "quantity": "100",
                "unit_price": "12.50",
            }
        ],
    }


def _po_payload(
    po_id: str | None = None,
    vendor_id: str | None = None,
    item_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": po_id or str(uuid.uuid4()),
        "po_number": "PO-2026-0001",
        "vendor_id": vendor_id or str(uuid.uuid4()),
        "order_date": "2026-06-01",
        "status": "DRAFT",
        "notes": "Quarterly raw material",
        "items": [
            {
                "item_id": item_id or str(uuid.uuid4()),
                "quantity": "500",
                "unit_price": "8.00",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Shared: auth gate + idempotency header gate
# ---------------------------------------------------------------------------

async def test_sync_customer_requires_internal_api_key(client_with_db: AsyncClient) -> None:
    response = await client_with_db.post(
        "/api/v1/sync/customers",
        json=_customer_payload(),
        headers=_idempotency_header(),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_API_KEY"


async def test_sync_customer_requires_idempotency_key(client_with_db: AsyncClient) -> None:
    response = await client_with_db.post(
        "/api/v1/sync/customers",
        json=_customer_payload(),
        headers=_INTERNAL_HEADERS,
    )
    assert response.status_code == 422


async def test_sync_vendor_requires_internal_api_key(client_with_db: AsyncClient) -> None:
    response = await client_with_db.post(
        "/api/v1/sync/vendors",
        json=_vendor_payload(),
        headers=_idempotency_header(),
    )
    assert response.status_code == 401


async def test_sync_item_requires_internal_api_key(client_with_db: AsyncClient) -> None:
    response = await client_with_db.post(
        "/api/v1/sync/items",
        json=_item_payload(),
        headers=_idempotency_header(),
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Customer → Accounts
# ---------------------------------------------------------------------------

async def test_sync_customer_creates_zoho_account(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token()
    key = str(uuid.uuid4())

    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{_ZOHO}/Accounts").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_ACCOUNT_ID))
        )

        response = await client_with_db.post(
            "/api/v1/sync/customers",
            json=_customer_payload(),
            headers=_sync_headers(key),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["zoho_id"] == _ZOHO_ACCOUNT_ID
    assert body["operation"] == "created"


async def test_sync_customer_idempotent_replay_skips_zoho(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token()
    key = str(uuid.uuid4())
    payload = _customer_payload()

    with respx.mock(assert_all_called=False) as mock:
        create_route = mock.post(f"{_ZOHO}/Accounts").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_ACCOUNT_ID))
        )

        await client_with_db.post(
            "/api/v1/sync/customers", json=payload, headers=_sync_headers(key)
        )
        # Replay with same key + same body
        second = await client_with_db.post(
            "/api/v1/sync/customers", json=payload, headers=_sync_headers(key)
        )

    assert second.status_code == 200
    assert second.json()["zoho_id"] == _ZOHO_ACCOUNT_ID
    assert create_route.call_count == 1  # Zoho called exactly once


async def test_sync_customer_idempotency_conflict_returns_409(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token()
    key = str(uuid.uuid4())

    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{_ZOHO}/Accounts").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_ACCOUNT_ID))
        )

        await client_with_db.post(
            "/api/v1/sync/customers",
            json=_customer_payload(),
            headers=_sync_headers(key),
        )
        # Same key, different body
        conflict = await client_with_db.post(
            "/api/v1/sync/customers",
            json={**_customer_payload(), "company_name": "Different Co."},
            headers=_sync_headers(key),
        )

    assert conflict.status_code == 409


async def test_sync_customer_second_call_uses_update(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    """A second sync with a NEW idempotency key updates the already-mapped record."""
    await seed_token()
    customer_id = str(uuid.uuid4())
    payload = _customer_payload(customer_id)

    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{_ZOHO}/Accounts").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_ACCOUNT_ID))
        )
        update_route = mock.put(f"{_ZOHO}/Accounts/{_ZOHO_ACCOUNT_ID}").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_ACCOUNT_ID))
        )

        await client_with_db.post(
            "/api/v1/sync/customers", json=payload, headers=_sync_headers()
        )
        second = await client_with_db.post(
            "/api/v1/sync/customers",
            json={**payload, "notes": "Updated notes"},
            headers=_sync_headers(),  # fresh key each call
        )

    assert second.status_code == 200
    assert second.json()["operation"] == "updated"
    assert update_route.call_count == 1


# ---------------------------------------------------------------------------
# Vendor → Vendors
# ---------------------------------------------------------------------------

async def test_sync_vendor_creates_zoho_vendor(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token()

    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{_ZOHO}/Vendors").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_VENDOR_ID))
        )

        response = await client_with_db.post(
            "/api/v1/sync/vendors",
            json=_vendor_payload(),
            headers=_sync_headers(),
        )

    assert response.status_code == 200
    assert response.json()["zoho_id"] == _ZOHO_VENDOR_ID
    assert response.json()["operation"] == "created"


async def test_sync_vendor_idempotent_replay_skips_zoho(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token()
    key = str(uuid.uuid4())
    payload = _vendor_payload()

    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(f"{_ZOHO}/Vendors").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_VENDOR_ID))
        )

        await client_with_db.post(
            "/api/v1/sync/vendors", json=payload, headers=_sync_headers(key)
        )
        second = await client_with_db.post(
            "/api/v1/sync/vendors", json=payload, headers=_sync_headers(key)
        )

    assert second.status_code == 200
    assert route.call_count == 1


# ---------------------------------------------------------------------------
# Item → Products
# ---------------------------------------------------------------------------

async def test_sync_item_creates_zoho_product(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token()

    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{_ZOHO}/Products").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_PRODUCT_ID))
        )

        response = await client_with_db.post(
            "/api/v1/sync/items",
            json=_item_payload(),
            headers=_sync_headers(),
        )

    assert response.status_code == 200
    assert response.json()["zoho_id"] == _ZOHO_PRODUCT_ID
    assert response.json()["operation"] == "created"


async def test_sync_item_idempotent_replay_skips_zoho(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token()
    key = str(uuid.uuid4())
    payload = _item_payload()

    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(f"{_ZOHO}/Products").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_PRODUCT_ID))
        )

        await client_with_db.post(
            "/api/v1/sync/items", json=payload, headers=_sync_headers(key)
        )
        second = await client_with_db.post(
            "/api/v1/sync/items", json=payload, headers=_sync_headers(key)
        )

    assert second.status_code == 200
    assert route.call_count == 1


# ---------------------------------------------------------------------------
# SalesOrder → Sales_Orders (requires Customer + Item already synced)
# ---------------------------------------------------------------------------

async def test_sync_sales_order_creates_zoho_so(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    """SO sync succeeds when Customer and Item are already in crm_mappings."""
    await seed_token()
    customer_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())

    with respx.mock(assert_all_called=False) as mock:
        # First sync customer and item so their mappings exist
        mock.post(f"{_ZOHO}/Accounts").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_ACCOUNT_ID))
        )
        mock.post(f"{_ZOHO}/Products").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_PRODUCT_ID))
        )
        mock.post(f"{_ZOHO}/Sales_Orders").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_SO_ID))
        )

        await client_with_db.post(
            "/api/v1/sync/customers",
            json=_customer_payload(customer_id),
            headers=_sync_headers(),
        )
        await client_with_db.post(
            "/api/v1/sync/items",
            json=_item_payload(item_id),
            headers=_sync_headers(),
        )
        response = await client_with_db.post(
            "/api/v1/sync/sales-orders",
            json=_so_payload(customer_id=customer_id, item_id=item_id),
            headers=_sync_headers(),
        )

    assert response.status_code == 200
    assert response.json()["zoho_id"] == _ZOHO_SO_ID
    assert response.json()["operation"] == "created"


async def test_sync_sales_order_fails_when_customer_not_synced(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    """SO sync returns 502 when Customer crm_mapping is missing."""
    await seed_token()

    with respx.mock(assert_all_called=False):
        response = await client_with_db.post(
            "/api/v1/sync/sales-orders",
            json=_so_payload(),
            headers=_sync_headers(),
        )

    assert response.status_code == 502


async def test_sync_sales_order_idempotent_replay_skips_zoho(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token()
    customer_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())
    key = str(uuid.uuid4())
    payload = _so_payload(customer_id=customer_id, item_id=item_id)

    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{_ZOHO}/Accounts").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_ACCOUNT_ID))
        )
        mock.post(f"{_ZOHO}/Products").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_PRODUCT_ID))
        )
        so_route = mock.post(f"{_ZOHO}/Sales_Orders").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_SO_ID))
        )

        await client_with_db.post(
            "/api/v1/sync/customers",
            json=_customer_payload(customer_id),
            headers=_sync_headers(),
        )
        await client_with_db.post(
            "/api/v1/sync/items",
            json=_item_payload(item_id),
            headers=_sync_headers(),
        )
        await client_with_db.post(
            "/api/v1/sync/sales-orders", json=payload, headers=_sync_headers(key)
        )
        second = await client_with_db.post(
            "/api/v1/sync/sales-orders", json=payload, headers=_sync_headers(key)
        )

    assert second.status_code == 200
    assert so_route.call_count == 1


# ---------------------------------------------------------------------------
# PurchaseOrder → Purchase_Orders (requires Vendor + Item already synced)
# ---------------------------------------------------------------------------

async def test_sync_purchase_order_creates_zoho_po(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token()
    vendor_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())

    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{_ZOHO}/Vendors").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_VENDOR_ID))
        )
        mock.post(f"{_ZOHO}/Products").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_PRODUCT_ID))
        )
        mock.post(f"{_ZOHO}/Purchase_Orders").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_PO_ID))
        )

        await client_with_db.post(
            "/api/v1/sync/vendors",
            json=_vendor_payload(vendor_id),
            headers=_sync_headers(),
        )
        await client_with_db.post(
            "/api/v1/sync/items",
            json=_item_payload(item_id),
            headers=_sync_headers(),
        )
        response = await client_with_db.post(
            "/api/v1/sync/purchase-orders",
            json=_po_payload(vendor_id=vendor_id, item_id=item_id),
            headers=_sync_headers(),
        )

    assert response.status_code == 200
    assert response.json()["zoho_id"] == _ZOHO_PO_ID
    assert response.json()["operation"] == "created"


async def test_sync_purchase_order_fails_when_vendor_not_synced(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token()

    with respx.mock(assert_all_called=False):
        response = await client_with_db.post(
            "/api/v1/sync/purchase-orders",
            json=_po_payload(),
            headers=_sync_headers(),
        )

    assert response.status_code == 502


async def test_sync_purchase_order_idempotent_replay_skips_zoho(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token()
    vendor_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())
    key = str(uuid.uuid4())
    payload = _po_payload(vendor_id=vendor_id, item_id=item_id)

    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{_ZOHO}/Vendors").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_VENDOR_ID))
        )
        mock.post(f"{_ZOHO}/Products").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_PRODUCT_ID))
        )
        po_route = mock.post(f"{_ZOHO}/Purchase_Orders").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_PO_ID))
        )

        await client_with_db.post(
            "/api/v1/sync/vendors",
            json=_vendor_payload(vendor_id),
            headers=_sync_headers(),
        )
        await client_with_db.post(
            "/api/v1/sync/items",
            json=_item_payload(item_id),
            headers=_sync_headers(),
        )
        await client_with_db.post(
            "/api/v1/sync/purchase-orders", json=payload, headers=_sync_headers(key)
        )
        second = await client_with_db.post(
            "/api/v1/sync/purchase-orders", json=payload, headers=_sync_headers(key)
        )

    assert second.status_code == 200
    assert po_route.call_count == 1


# ---------------------------------------------------------------------------
# Lead → Leads
# ---------------------------------------------------------------------------

_ZOHO_LEAD_ID = "ZLEAD-0001"


def _lead_sync_payload(lead_id: str | None = None) -> dict[str, Any]:
    return {
        "id": lead_id or str(uuid.uuid4()),
        "contact_name": "Yash Sharma",
        "source": "FIELD_VISIT",
        "stage": "NEW",
        "phone": "+91 90000 00001",
        "email": "yash@example.com",
        "state": "Maharashtra",
        "city": "Pune",
        "notes": "Met at a pharma expo",
        "estimated_budget": "50000.00",
    }


async def test_sync_lead_requires_internal_api_key(client_with_db: AsyncClient) -> None:
    response = await client_with_db.post(
        "/api/v1/sync/leads",
        json=_lead_sync_payload(),
        headers=_idempotency_header(),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_API_KEY"


async def test_sync_lead_requires_idempotency_key(client_with_db: AsyncClient) -> None:
    response = await client_with_db.post(
        "/api/v1/sync/leads",
        json=_lead_sync_payload(),
        headers=_INTERNAL_HEADERS,
    )
    assert response.status_code == 422


async def test_sync_lead_creates_zoho_lead(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token()
    key = str(uuid.uuid4())

    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{_ZOHO}/Leads").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_LEAD_ID))
        )

        response = await client_with_db.post(
            "/api/v1/sync/leads",
            json=_lead_sync_payload(),
            headers=_sync_headers(key),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["zoho_id"] == _ZOHO_LEAD_ID
    assert body["operation"] == "created"


async def test_sync_lead_idempotent_replay_skips_zoho(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token()
    key = str(uuid.uuid4())
    payload = _lead_sync_payload()

    with respx.mock(assert_all_called=False) as mock:
        lead_route = mock.post(f"{_ZOHO}/Leads").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_LEAD_ID))
        )

        await client_with_db.post(
            "/api/v1/sync/leads", json=payload, headers=_sync_headers(key)
        )
        second = await client_with_db.post(
            "/api/v1/sync/leads", json=payload, headers=_sync_headers(key)
        )

    assert second.status_code == 200
    assert second.json()["zoho_id"] == _ZOHO_LEAD_ID
    assert lead_route.call_count == 1


async def test_sync_lead_idempotency_conflict_returns_409(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token()
    key = str(uuid.uuid4())

    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{_ZOHO}/Leads").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_LEAD_ID))
        )

        await client_with_db.post(
            "/api/v1/sync/leads",
            json=_lead_sync_payload(),
            headers=_sync_headers(key),
        )
        conflict = await client_with_db.post(
            "/api/v1/sync/leads",
            json={**_lead_sync_payload(), "contact_name": "Different Name"},
            headers=_sync_headers(key),
        )

    assert conflict.status_code == 409


async def test_sync_lead_second_call_uses_zoho_put(
    client_with_db: AsyncClient,
    seed_token: Callable[..., Awaitable[ZohoToken]],
) -> None:
    await seed_token()
    lead_id = str(uuid.uuid4())

    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{_ZOHO}/Leads").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_LEAD_ID))
        )
        put_route = mock.put(f"{_ZOHO}/Leads/{_ZOHO_LEAD_ID}").mock(
            return_value=Response(200, json=_zoho_created(_ZOHO_LEAD_ID))
        )

        await client_with_db.post(
            "/api/v1/sync/leads",
            json=_lead_sync_payload(lead_id),
            headers=_sync_headers(),
        )
        second = await client_with_db.post(
            "/api/v1/sync/leads",
            json={**_lead_sync_payload(lead_id), "stage": "QUALIFICATION"},
            headers=_sync_headers(),
        )

    assert second.status_code == 200
    assert second.json()["operation"] == "updated"
    assert put_route.call_count == 1
