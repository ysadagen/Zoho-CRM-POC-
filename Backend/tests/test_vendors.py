"""Tests for /api/v1/vendors — full CRUD coverage."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vendor import Vendor

VENDORS_URL = "/api/v1/vendors"


def _vendor_url(vendor_id: str | uuid.UUID) -> str:
    return f"{VENDORS_URL}/{vendor_id}"


def _vendor_payload(**overrides: object) -> dict[str, object]:
    """A valid VendorCreate payload. Tests override individual fields."""
    base: dict[str, object] = {
        "vendor_name": "Steelcraft Co.",
        "contact_person": "Anita Joshi",
        "phone": "+91 98765 43210",
        "email": "anita@steelcraft.example.com",
        "address": "Pune, MH",
        "vendor_code": "V-0008",
        "gstin": "27AAACS1234R1Z2",
        "notes": "Primary steel supplier",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Auth wall
# ---------------------------------------------------------------------------


async def test_create_vendor_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.post(VENDORS_URL, json=_vendor_payload())
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


async def test_get_vendor_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.get(_vendor_url(uuid.uuid4()))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


async def test_delete_vendor_as_non_admin_returns_403(
    authenticated_client: AsyncClient,
) -> None:
    """Non-admin authenticated users cannot soft-delete vendors."""
    created = await authenticated_client.post(VENDORS_URL, json=_vendor_payload())
    vendor_id = created.json()["id"]

    response = await authenticated_client.delete(_vendor_url(vendor_id))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_REQUIRED"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_vendor_returns_201_with_payload(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(VENDORS_URL, json=_vendor_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["vendor_name"] == "Steelcraft Co."
    assert body["contact_person"] == "Anita Joshi"
    assert body["vendor_code"] == "V-0008"
    assert body["gstin"] == "27AAACS1234R1Z2"
    assert body["is_active"] is True
    assert "id" in body
    assert "created_at" in body


async def test_create_vendor_minimal_fields_succeed(
    authenticated_client: AsyncClient,
) -> None:
    """Only ``vendor_name`` and ``contact_person`` are required."""
    response = await authenticated_client.post(
        VENDORS_URL,
        json={
            "vendor_name": "Bare Minimum Supply",
            "contact_person": "Office",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["is_active"] is True  # default
    assert body["vendor_code"] is None
    assert body["gstin"] is None


async def test_create_vendor_includes_audit_fields(
    authenticated_client: AsyncClient,
) -> None:
    """Every created row records who created and last touched it."""
    response = await authenticated_client.post(VENDORS_URL, json=_vendor_payload())
    body = response.json()

    assert uuid.UUID(body["created_by_user_id"])
    assert uuid.UUID(body["updated_by_user_id"])
    assert body["created_by_user_id"] == body["updated_by_user_id"]


async def test_create_vendor_duplicate_code_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    first = await authenticated_client.post(VENDORS_URL, json=_vendor_payload())
    assert first.status_code == 201

    second = await authenticated_client.post(
        VENDORS_URL,
        json=_vendor_payload(vendor_name="Different Vendor", gstin="27AAACS9999X1Z9"),
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "VENDOR_CODE_ALREADY_EXISTS"


async def test_create_vendor_duplicate_gstin_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    first = await authenticated_client.post(VENDORS_URL, json=_vendor_payload())
    assert first.status_code == 201

    second = await authenticated_client.post(
        VENDORS_URL,
        json=_vendor_payload(vendor_name="Different Co.", vendor_code="V-0099"),
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "GSTIN_ALREADY_EXISTS"


async def test_create_vendor_invalid_email_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(
        VENDORS_URL, json=_vendor_payload(email="not-an-email")
    )
    assert response.status_code == 422


async def test_create_vendor_invalid_gstin_length_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    """GSTIN must be exactly 15 characters."""
    response = await authenticated_client.post(VENDORS_URL, json=_vendor_payload(gstin="TOO-SHORT"))
    assert response.status_code == 422


async def test_create_vendor_strips_whitespace_from_code(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(
        VENDORS_URL,
        json=_vendor_payload(vendor_code="  V-0008  ", vendor_name="  Padded Co.  "),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["vendor_code"] == "V-0008"
    assert body["vendor_name"] == "Padded Co."


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


async def test_get_vendor_returns_200_with_vendor(
    authenticated_client: AsyncClient,
) -> None:
    created = await authenticated_client.post(VENDORS_URL, json=_vendor_payload())
    vendor_id = created.json()["id"]

    response = await authenticated_client.get(_vendor_url(vendor_id))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == vendor_id
    assert body["vendor_code"] == "V-0008"


async def test_get_vendor_not_found_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.get(_vendor_url(uuid.uuid4()))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VENDOR_NOT_FOUND"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


async def test_list_vendors_returns_paginated_shape(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.get(VENDORS_URL)

    assert response.status_code == 200
    body = response.json()
    assert {"items", "total", "limit", "offset"} <= body.keys()
    assert body["limit"] == 25
    assert body["offset"] == 0


async def test_list_vendors_search_matches_name_or_code(
    authenticated_client: AsyncClient,
) -> None:
    await authenticated_client.post(
        VENDORS_URL,
        json=_vendor_payload(
            vendor_name="Polyrise Industries",
            vendor_code="V-0021",
            gstin="24AABCP4567K1Z8",
        ),
    )
    await authenticated_client.post(
        VENDORS_URL,
        json=_vendor_payload(
            vendor_name="Cap-Lock Hardware",
            vendor_code="V-0024",
            gstin="27AAFCC4321L1Z3",
        ),
    )

    by_name = await authenticated_client.get(VENDORS_URL, params={"search": "polyrise"})
    by_code = await authenticated_client.get(VENDORS_URL, params={"search": "0024"})

    assert by_name.json()["total"] == 1
    assert by_name.json()["items"][0]["vendor_name"] == "Polyrise Industries"
    assert by_code.json()["total"] == 1
    assert by_code.json()["items"][0]["vendor_code"] == "V-0024"


# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------


async def test_patch_vendor_partial_update_succeeds(
    authenticated_client: AsyncClient,
) -> None:
    created = await authenticated_client.post(VENDORS_URL, json=_vendor_payload())
    vendor_id = created.json()["id"]

    response = await authenticated_client.patch(
        _vendor_url(vendor_id),
        json={"contact_person": "Anita J. (renamed)", "phone": "+91 99999 00000"},
    )

    assert response.status_code == 200
    body = response.json()
    # Updated fields changed.
    assert body["contact_person"] == "Anita J. (renamed)"
    assert body["phone"] == "+91 99999 00000"
    # Untouched fields preserved.
    assert body["vendor_name"] == "Steelcraft Co."
    assert body["vendor_code"] == "V-0008"


async def test_patch_vendor_not_found_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.patch(
        _vendor_url(uuid.uuid4()), json={"contact_person": "Anyone"}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VENDOR_NOT_FOUND"


async def test_patch_vendor_can_deactivate_via_is_active_false(
    authenticated_client: AsyncClient,
) -> None:
    """Soft-deactivation via PATCH is allowed for any authenticated user."""
    created = await authenticated_client.post(VENDORS_URL, json=_vendor_payload())
    vendor_id = created.json()["id"]

    response = await authenticated_client.patch(_vendor_url(vendor_id), json={"is_active": False})

    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_patch_vendor_rejects_unknown_field_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    """``extra='forbid'`` rejects typos like ``vendr_name``."""
    created = await authenticated_client.post(VENDORS_URL, json=_vendor_payload())
    vendor_id = created.json()["id"]

    response = await authenticated_client.patch(
        _vendor_url(vendor_id), json={"vendr_name": "Typo Co."}
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Delete (admin only soft-delete)
# ---------------------------------------------------------------------------


async def test_delete_vendor_as_admin_returns_204_and_deactivates(
    admin_authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Soft-delete: row is retained, ``is_active`` flips to false."""
    created = await admin_authenticated_client.post(VENDORS_URL, json=_vendor_payload())
    vendor_id = uuid.UUID(created.json()["id"])

    response = await admin_authenticated_client.delete(_vendor_url(vendor_id))

    assert response.status_code == 204
    assert response.content == b""

    vendor = await db_session.scalar(select(Vendor).where(Vendor.id == vendor_id))
    assert vendor is not None
    assert vendor.is_active is False


async def test_delete_vendor_not_found_returns_404(
    admin_authenticated_client: AsyncClient,
) -> None:
    response = await admin_authenticated_client.delete(_vendor_url(uuid.uuid4()))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VENDOR_NOT_FOUND"


async def test_delete_already_inactive_vendor_is_idempotent(
    admin_authenticated_client: AsyncClient,
) -> None:
    """Second delete on an inactive vendor still returns 204, no error."""
    created = await admin_authenticated_client.post(VENDORS_URL, json=_vendor_payload())
    vendor_id = created.json()["id"]

    first = await admin_authenticated_client.delete(_vendor_url(vendor_id))
    assert first.status_code == 204

    second = await admin_authenticated_client.delete(_vendor_url(vendor_id))
    assert second.status_code == 204
