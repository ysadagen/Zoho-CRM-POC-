"""Tests for /api/v1/vendors/{vendor_id}/terms — pricing-term CRUD."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

VENDORS_URL = "/api/v1/vendors"
ITEMS_URL = "/api/v1/items"


def _terms_url(vendor_id: str | uuid.UUID) -> str:
    return f"{VENDORS_URL}/{vendor_id}/terms"


def _term_url(vendor_id: str | uuid.UUID, term_id: str | uuid.UUID) -> str:
    return f"{VENDORS_URL}/{vendor_id}/terms/{term_id}"


async def _create_vendor(client: AsyncClient, *, vendor_code: str | None = None) -> str:
    payload: dict[str, object] = {
        "vendor_name": f"Test Vendor {uuid.uuid4().hex[:6]}",
        "contact_person": "Test Contact",
    }
    if vendor_code is not None:
        payload["vendor_code"] = vendor_code
    response = await client.post(VENDORS_URL, json=payload)
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _create_item(client: AsyncClient, *, sku: str | None = None) -> str:
    response = await client.post(
        ITEMS_URL,
        json={
            "sku": sku or f"ITM-{uuid.uuid4().hex[:8]}",
            "name": "Test Item",
            "type": "RAW",
            "category": "Polymer",
            "unit_of_measure": "kg",
            "unit_price": "100.00",
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _term_payload(item_id: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "item_id": item_id,
        "rate": "150.00",
        "discount_percent": "5.00",
        "effective_from": "2026-01-01",
        "effective_to": "2026-06-30",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Auth wall
# ---------------------------------------------------------------------------


async def test_create_term_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.post(
        _terms_url(uuid.uuid4()),
        json=_term_payload(str(uuid.uuid4())),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


async def test_list_terms_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.get(_terms_url(uuid.uuid4()))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_term_returns_201_with_payload(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)

    response = await authenticated_client.post(
        _terms_url(vendor_id),
        json=_term_payload(item_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["vendor_id"] == vendor_id
    assert body["item_id"] == item_id
    assert body["rate"] == "150.00"
    assert body["is_active"] is True
    assert "id" in body
    assert uuid.UUID(body["created_by_user_id"])


async def test_create_term_for_unknown_vendor_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    item_id = await _create_item(authenticated_client)
    response = await authenticated_client.post(
        _terms_url(uuid.uuid4()),
        json=_term_payload(item_id),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VENDOR_NOT_FOUND"


async def test_create_term_for_unknown_item_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    response = await authenticated_client.post(
        _terms_url(vendor_id),
        json=_term_payload(str(uuid.uuid4())),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ITEM_NOT_FOUND"


async def test_create_overlapping_term_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    """The headline business invariant — no two active terms for the
    same (vendor, item) may have overlapping date ranges."""
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)

    first = await authenticated_client.post(
        _terms_url(vendor_id),
        json=_term_payload(item_id, effective_from="2026-01-01", effective_to="2026-06-30"),
    )
    assert first.status_code == 201

    # New range overlaps the existing one on 2026-04-01 to 2026-06-30.
    second = await authenticated_client.post(
        _terms_url(vendor_id),
        json=_term_payload(
            item_id, effective_from="2026-04-01", effective_to="2026-09-30", rate="160.00"
        ),
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "OVERLAPPING_TERMS"


async def test_create_non_overlapping_consecutive_terms_both_succeed(
    authenticated_client: AsyncClient,
) -> None:
    """Adjacent (non-overlapping) date ranges are allowed."""
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)

    first = await authenticated_client.post(
        _terms_url(vendor_id),
        json=_term_payload(item_id, effective_from="2026-01-01", effective_to="2026-03-31"),
    )
    assert first.status_code == 201

    # New range starts the day AFTER the first ended.
    second = await authenticated_client.post(
        _terms_url(vendor_id),
        json=_term_payload(
            item_id, effective_from="2026-04-01", effective_to="2026-06-30", rate="160.00"
        ),
    )
    assert second.status_code == 201


async def test_create_term_with_inverted_dates_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    """``effective_to`` must be >= ``effective_from``. Pydantic catches it."""
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)

    response = await authenticated_client.post(
        _terms_url(vendor_id),
        json=_term_payload(item_id, effective_from="2026-06-30", effective_to="2026-01-01"),
    )
    assert response.status_code == 422


async def test_create_term_with_negative_rate_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)

    response = await authenticated_client.post(
        _terms_url(vendor_id),
        json=_term_payload(item_id, rate="-1.00"),
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


async def test_get_term_returns_200(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    created = await authenticated_client.post(_terms_url(vendor_id), json=_term_payload(item_id))
    term_id = created.json()["id"]

    response = await authenticated_client.get(_term_url(vendor_id, term_id))

    assert response.status_code == 200
    assert response.json()["id"] == term_id


async def test_get_term_under_different_vendor_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    """Cross-vendor probing is blocked — the term's vendor_id must match
    the URL's vendor_id. Even though the term exists, returning 404
    (not 403) prevents an attacker from learning which term ids exist."""
    vendor_a = await _create_vendor(authenticated_client, vendor_code="V-AAA")
    vendor_b = await _create_vendor(authenticated_client, vendor_code="V-BBB")
    item_id = await _create_item(authenticated_client)

    created = await authenticated_client.post(_terms_url(vendor_a), json=_term_payload(item_id))
    term_id = created.json()["id"]

    response = await authenticated_client.get(_term_url(vendor_b, term_id))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TERM_NOT_FOUND"


async def test_get_term_not_found_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    response = await authenticated_client.get(_term_url(vendor_id, uuid.uuid4()))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TERM_NOT_FOUND"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


async def test_list_terms_returns_paginated_shape(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    response = await authenticated_client.get(_terms_url(vendor_id))

    assert response.status_code == 200
    body = response.json()
    assert {"items", "total", "limit", "offset"} <= body.keys()
    assert body["limit"] == 25


async def test_list_terms_active_only_excludes_inactive(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)

    # Create an active term and a soft-deleted one (different ranges,
    # so no overlap conflict).
    active = await authenticated_client.post(
        _terms_url(vendor_id),
        json=_term_payload(item_id, effective_from="2026-01-01", effective_to="2026-03-31"),
    )
    inactive = await authenticated_client.post(
        _terms_url(vendor_id),
        json=_term_payload(
            item_id, effective_from="2025-07-01", effective_to="2025-12-31", rate="140.00"
        ),
    )
    await authenticated_client.delete(_term_url(vendor_id, inactive.json()["id"]))

    response = await authenticated_client.get(_terms_url(vendor_id), params={"active_only": True})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == active.json()["id"]


# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------


async def test_patch_term_partial_update_succeeds(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    created = await authenticated_client.post(_terms_url(vendor_id), json=_term_payload(item_id))
    term_id = created.json()["id"]

    response = await authenticated_client.patch(
        _term_url(vendor_id, term_id),
        json={"rate": "175.50", "discount_percent": "10.00"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rate"] == "175.50"
    assert body["discount_percent"] == "10.00"
    # Unchanged fields preserved.
    assert body["effective_from"] == "2026-01-01"


async def test_patch_term_into_overlap_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    """Updating dates so the resulting range overlaps another active
    term for the same (vendor, item) → 409."""
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)

    first = await authenticated_client.post(
        _terms_url(vendor_id),
        json=_term_payload(item_id, effective_from="2026-01-01", effective_to="2026-03-31"),
    )
    second = await authenticated_client.post(
        _terms_url(vendor_id),
        json=_term_payload(
            item_id, effective_from="2026-07-01", effective_to="2026-09-30", rate="160.00"
        ),
    )

    # Try to extend the second backwards into the first's range.
    response = await authenticated_client.patch(
        _term_url(vendor_id, second.json()["id"]),
        json={"effective_from": "2026-03-01"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OVERLAPPING_TERMS"
    # And the first still exists unchanged.
    check = await authenticated_client.get(_term_url(vendor_id, first.json()["id"]))
    assert check.json()["effective_from"] == "2026-01-01"


# ---------------------------------------------------------------------------
# Delete (soft-delete)
# ---------------------------------------------------------------------------


async def test_delete_term_returns_204_and_deactivates(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    created = await authenticated_client.post(_terms_url(vendor_id), json=_term_payload(item_id))
    term_id = created.json()["id"]

    response = await authenticated_client.delete(_term_url(vendor_id, term_id))
    assert response.status_code == 204

    fetched = await authenticated_client.get(_term_url(vendor_id, term_id))
    assert fetched.status_code == 200
    assert fetched.json()["is_active"] is False


async def test_delete_already_inactive_term_is_idempotent(
    authenticated_client: AsyncClient,
) -> None:
    vendor_id = await _create_vendor(authenticated_client)
    item_id = await _create_item(authenticated_client)
    created = await authenticated_client.post(_terms_url(vendor_id), json=_term_payload(item_id))
    term_id = created.json()["id"]

    first = await authenticated_client.delete(_term_url(vendor_id, term_id))
    assert first.status_code == 204
    second = await authenticated_client.delete(_term_url(vendor_id, term_id))
    assert second.status_code == 204
