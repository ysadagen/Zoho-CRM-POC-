"""Tests for /api/v1/items — full CRUD coverage."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item

ITEMS_URL = "/api/v1/items"


def _item_url(item_id: str | uuid.UUID) -> str:
    return f"{ITEMS_URL}/{item_id}"


def _raw_item_payload(**overrides: object) -> dict[str, object]:
    """A valid ItemCreate payload — tests can override individual fields."""
    base: dict[str, object] = {
        "sku": "ITM-0001",
        "name": "Raw Plastic Pellets",
        "type": "RAW",
        "category": "Polymer",
        "unit_of_measure": "kg",
        "description": "Standard PET pellets",
        "stock_quantity": "1250",
        "reorder_threshold": "200",
        "unit_price": "82.00",
    }
    base.update(overrides)
    return base


def _finished_item_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "sku": "PRD-0001",
        "name": "Bottle — 250ml",
        "type": "FINISHED",
        "category": "Beverage",
        "unit_of_measure": "pcs",
        "stock_quantity": "4250",
        "reorder_threshold": "1000",
        "unit_price": "18.50",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def test_create_item_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.post(ITEMS_URL, json=_raw_item_payload())
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


async def test_get_item_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.get(_item_url(uuid.uuid4()))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_item_returns_201_with_item_payload(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(ITEMS_URL, json=_raw_item_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["sku"] == "ITM-0001"
    assert body["name"] == "Raw Plastic Pellets"
    assert body["type"] == "RAW"
    assert body["category"] == "Polymer"
    assert body["unit_of_measure"] == "kg"
    assert body["is_active"] is True
    # Computed field surfaces in the response.
    assert body["status"] == "IN_STOCK"
    assert "id" in body
    assert "created_at" in body


async def test_create_item_includes_audit_fields(
    authenticated_client: AsyncClient,
) -> None:
    """Every created row records who created and last updated it."""
    response = await authenticated_client.post(ITEMS_URL, json=_raw_item_payload())

    assert response.status_code == 201
    body = response.json()
    # Both fields populated, both are UUIDs (parsing as UUID raises if not).
    assert uuid.UUID(body["created_by_user_id"])
    assert uuid.UUID(body["updated_by_user_id"])
    # On creation, both audit users are the same actor.
    assert body["created_by_user_id"] == body["updated_by_user_id"]


async def test_create_item_strips_whitespace_from_sku(
    authenticated_client: AsyncClient,
) -> None:
    """``str_strip_whitespace`` normalises input so trailing spaces don't create duplicates."""
    payload = _raw_item_payload(sku="  ITM-0001  ", name="  Padded Name  ")
    response = await authenticated_client.post(ITEMS_URL, json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["sku"] == "ITM-0001"
    assert body["name"] == "Padded Name"


async def test_create_item_duplicate_sku_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    first = await authenticated_client.post(ITEMS_URL, json=_raw_item_payload())
    assert first.status_code == 201

    second = await authenticated_client.post(ITEMS_URL, json=_raw_item_payload())
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "SKU_ALREADY_EXISTS"


async def test_create_item_invalid_type_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(
        ITEMS_URL,
        json=_raw_item_payload(type="SEMI_FINISHED"),
    )
    assert response.status_code == 422


async def test_create_item_negative_stock_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(
        ITEMS_URL,
        json=_raw_item_payload(stock_quantity="-1"),
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


async def test_get_item_returns_200_with_item(authenticated_client: AsyncClient) -> None:
    created = await authenticated_client.post(ITEMS_URL, json=_raw_item_payload())
    item_id = created.json()["id"]

    response = await authenticated_client.get(_item_url(item_id))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == item_id
    assert body["sku"] == "ITM-0001"


async def test_get_item_not_found_returns_404(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get(_item_url(uuid.uuid4()))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ITEM_NOT_FOUND"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


async def test_list_items_returns_paginated_shape(
    authenticated_client: AsyncClient,
) -> None:
    # Empty list still returns the full envelope.
    response = await authenticated_client.get(ITEMS_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["limit"] == 25
    assert body["offset"] == 0


async def test_list_items_filter_by_type_returns_only_matching(
    authenticated_client: AsyncClient,
) -> None:
    await authenticated_client.post(ITEMS_URL, json=_raw_item_payload())
    await authenticated_client.post(ITEMS_URL, json=_finished_item_payload())

    response = await authenticated_client.get(ITEMS_URL, params={"type": "RAW"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["type"] == "RAW"


async def test_list_items_filter_by_category_returns_only_matching(
    authenticated_client: AsyncClient,
) -> None:
    await authenticated_client.post(ITEMS_URL, json=_raw_item_payload())
    await authenticated_client.post(ITEMS_URL, json=_finished_item_payload())

    response = await authenticated_client.get(ITEMS_URL, params={"category": "Beverage"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["category"] == "Beverage"


async def test_list_items_search_matches_sku_or_name(
    authenticated_client: AsyncClient,
) -> None:
    await authenticated_client.post(ITEMS_URL, json=_raw_item_payload())
    await authenticated_client.post(ITEMS_URL, json=_finished_item_payload())

    by_sku = await authenticated_client.get(ITEMS_URL, params={"search": "PRD"})
    by_name = await authenticated_client.get(ITEMS_URL, params={"search": "plastic"})

    assert by_sku.json()["total"] == 1
    assert by_sku.json()["items"][0]["sku"] == "PRD-0001"
    assert by_name.json()["total"] == 1
    assert by_name.json()["items"][0]["name"] == "Raw Plastic Pellets"


# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------


async def test_patch_item_partial_update_succeeds(
    authenticated_client: AsyncClient,
) -> None:
    created = await authenticated_client.post(ITEMS_URL, json=_raw_item_payload())
    item_id = created.json()["id"]

    response = await authenticated_client.patch(
        _item_url(item_id),
        json={"name": "Raw Plastic Pellets (Grade A)", "unit_price": "85.50"},
    )

    assert response.status_code == 200
    body = response.json()
    # Updated fields changed.
    assert body["name"] == "Raw Plastic Pellets (Grade A)"
    assert body["unit_price"] == "85.50"
    # Untouched fields preserved.
    assert body["sku"] == "ITM-0001"
    assert body["category"] == "Polymer"


async def test_patch_item_not_found_returns_404(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.patch(
        _item_url(uuid.uuid4()),
        json={"name": "anything"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ITEM_NOT_FOUND"


async def test_patch_item_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    """PATCH is on the auth wall too — auditing relies on knowing the actor."""
    response = await client_with_db.patch(
        _item_url(uuid.uuid4()),
        json={"name": "anything"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


async def test_patch_item_can_deactivate_via_is_active_false(
    authenticated_client: AsyncClient,
) -> None:
    """Soft-delete path: with no DELETE endpoint, deactivation is via PATCH."""
    created = await authenticated_client.post(ITEMS_URL, json=_raw_item_payload())
    item_id = created.json()["id"]

    response = await authenticated_client.patch(
        _item_url(item_id),
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_patch_item_rejects_stock_quantity_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    """Stock changes must go through the stock-movement ledger (Phase 6+).

    Pinned with ``extra="forbid"`` on ItemUpdate so attempts to sneak
    stock changes through PATCH fail loudly with 422 instead of being
    silently ignored.
    """
    created = await authenticated_client.post(ITEMS_URL, json=_raw_item_payload())
    item_id = created.json()["id"]

    response = await authenticated_client.patch(
        _item_url(item_id),
        json={"stock_quantity": "9999"},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Derived status field
# ---------------------------------------------------------------------------


async def test_db_rejects_negative_stock_even_when_set_directly(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The DB CHECK constraint is the last line of defence for stock >= 0.

    Phase 4 has no API path to set stock < 0 — ``ItemUpdate`` doesn't
    accept stock changes at all, and ``ItemCreate`` Pydantic-rejects
    negatives. This test deliberately bypasses both layers and writes
    ``-1`` directly to the ORM, proving Postgres rejects it. This
    protects against future bugs in Phase 7/8 stock-movement code.
    """
    created = await authenticated_client.post(
        ITEMS_URL, json=_raw_item_payload(stock_quantity="20")
    )
    item_id = uuid.UUID(created.json()["id"])

    item = await db_session.scalar(select(Item).where(Item.id == item_id))
    assert item is not None
    item.stock_quantity = Decimal("-1")

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.parametrize(
    ("stock", "threshold", "expected_status"),
    [
        ("100", "50", "IN_STOCK"),
        ("25", "50", "LOW_STOCK"),
        ("0", "50", "OUT_OF_STOCK"),
        ("100", None, "IN_STOCK"),  # no threshold = never "low"
    ],
)
async def test_item_status_is_computed_from_stock_and_threshold(
    authenticated_client: AsyncClient,
    stock: str,
    threshold: str | None,
    expected_status: str,
) -> None:
    payload = _raw_item_payload(
        sku=f"ITM-{uuid.uuid4().hex[:8]}",
        stock_quantity=stock,
        reorder_threshold=threshold,
    )
    response = await authenticated_client.post(ITEMS_URL, json=payload)

    assert response.status_code == 201
    assert response.json()["status"] == expected_status
