"""Tests for Phase 2A.1 — customer + item intelligence-layer extensions.

Covers the new ``customers`` columns (``customer_type``, structured location,
``competitive_risk_level``) and the new ``items.standard_cost`` column:
happy-path create/read, conservative defaults, PATCH, Pydantic validation,
and the DB-level CHECK constraint (last line of defence) per CLAUDE.md §10.3.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item

CUSTOMERS_URL = "/api/v1/customers"
ITEMS_URL = "/api/v1/items"


def _customer_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "company_name": "Cluster Cement Traders",
        "contact_person": "Rohit Verma",
    }
    base.update(overrides)
    return base


def _raw_item_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "sku": f"ITM-{uuid.uuid4().hex[:8]}",
        "name": "Raw Plastic Pellets",
        "type": "RAW",
        "category": "Polymer",
        "unit_of_measure": "kg",
        "unit_price": "82.00",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Customers — new attributes
# ---------------------------------------------------------------------------


async def test_create_customer_persists_intelligence_fields(
    authenticated_client: AsyncClient,
) -> None:
    resp = await authenticated_client.post(
        CUSTOMERS_URL,
        json=_customer_payload(
            customer_type="DEALER",
            state="Odisha",
            district="Jajpur",
            city="Jajpur Town",
            pincode="755019",
            competitive_risk_level="MEDIUM",
        ),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["customer_type"] == "DEALER"
    assert body["state"] == "Odisha"
    assert body["district"] == "Jajpur"
    assert body["city"] == "Jajpur Town"
    assert body["pincode"] == "755019"
    assert body["competitive_risk_level"] == "MEDIUM"


async def test_create_customer_applies_conservative_defaults(
    authenticated_client: AsyncClient,
) -> None:
    """Omitting the new fields yields the conservative tier/level + NULL geo."""
    resp = await authenticated_client.post(CUSTOMERS_URL, json=_customer_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["customer_type"] == "RETAILER"
    assert body["competitive_risk_level"] == "NONE"
    assert body["state"] is None
    assert body["district"] is None
    assert body["city"] is None
    assert body["pincode"] is None


async def test_patch_customer_updates_intelligence_fields(
    authenticated_client: AsyncClient,
) -> None:
    created = await authenticated_client.post(CUSTOMERS_URL, json=_customer_payload())
    customer_id = created.json()["id"]

    resp = await authenticated_client.patch(
        f"{CUSTOMERS_URL}/{customer_id}",
        json={
            "customer_type": "SUB_DEALER",
            "district": "Cuttack",
            "competitive_risk_level": "HIGH",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer_type"] == "SUB_DEALER"
    assert body["district"] == "Cuttack"
    assert body["competitive_risk_level"] == "HIGH"
    # Untouched defaults preserved.
    assert body["state"] is None


async def test_create_customer_rejects_unknown_customer_type_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    resp = await authenticated_client.post(
        CUSTOMERS_URL, json=_customer_payload(customer_type="WHOLESALER")
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Items — standard_cost
# ---------------------------------------------------------------------------


async def test_create_item_persists_standard_cost(
    authenticated_client: AsyncClient,
) -> None:
    created = await authenticated_client.post(
        ITEMS_URL, json=_raw_item_payload(unit_price="100.00", standard_cost="76.00")
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    got = await authenticated_client.get(f"{ITEMS_URL}/{item_id}")
    assert got.status_code == 200
    assert got.json()["standard_cost"] == "76.00"


async def test_create_item_without_standard_cost_is_null(
    authenticated_client: AsyncClient,
) -> None:
    created = await authenticated_client.post(ITEMS_URL, json=_raw_item_payload())
    item_id = created.json()["id"]
    got = await authenticated_client.get(f"{ITEMS_URL}/{item_id}")
    assert got.json()["standard_cost"] is None


async def test_patch_item_updates_standard_cost(
    authenticated_client: AsyncClient,
) -> None:
    created = await authenticated_client.post(ITEMS_URL, json=_raw_item_payload())
    item_id = created.json()["id"]

    resp = await authenticated_client.patch(
        f"{ITEMS_URL}/{item_id}", json={"standard_cost": "55.50"}
    )
    assert resp.status_code == 200
    assert resp.json()["standard_cost"] == "55.50"


async def test_create_item_rejects_negative_standard_cost_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    resp = await authenticated_client.post(
        ITEMS_URL, json=_raw_item_payload(standard_cost="-1")
    )
    assert resp.status_code == 422


async def test_db_rejects_negative_standard_cost_even_when_set_directly(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The CHECK constraint is the last line of defence for standard_cost >= 0.

    Bypasses the Pydantic layer by writing ``-1`` straight to the ORM,
    proving Postgres rejects it (CLAUDE.md §10.3).
    """
    created = await authenticated_client.post(ITEMS_URL, json=_raw_item_payload())
    item_id = uuid.UUID(created.json()["id"])

    item = await db_session.scalar(select(Item).where(Item.id == item_id))
    assert item is not None
    item.standard_cost = Decimal("-1")

    with pytest.raises(IntegrityError):
        await db_session.flush()
