"""Tests for /api/v1/customers — full CRUD coverage."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer

CUSTOMERS_URL = "/api/v1/customers"


def _customer_url(customer_id: str | uuid.UUID) -> str:
    return f"{CUSTOMERS_URL}/{customer_id}"


def _customer_payload(**overrides: object) -> dict[str, object]:
    """A valid CustomerCreate payload. Tests override individual fields."""
    base: dict[str, object] = {
        "company_name": "Acme Industries Pvt. Ltd.",
        "contact_person": "Sneha Kapoor",
        "phone": "+91 98765 11223",
        "email": "sneha@acme.example.com",
        "address": "Mumbai, MH",
        "is_privileged": True,
        "customer_code": "C-0011",
        "gstin": "27AAACA1234B1Z5",
        "notes": "Premium account",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Auth wall
# ---------------------------------------------------------------------------


async def test_create_customer_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.post(CUSTOMERS_URL, json=_customer_payload())
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


async def test_get_customer_requires_auth_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.get(_customer_url(uuid.uuid4()))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


async def test_delete_customer_as_non_admin_returns_403(
    authenticated_client: AsyncClient,
) -> None:
    """Non-admin authenticated users cannot soft-delete customers."""
    created = await authenticated_client.post(CUSTOMERS_URL, json=_customer_payload())
    customer_id = created.json()["id"]

    response = await authenticated_client.delete(_customer_url(customer_id))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_REQUIRED"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_customer_returns_201_with_payload(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(CUSTOMERS_URL, json=_customer_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["company_name"] == "Acme Industries Pvt. Ltd."
    assert body["contact_person"] == "Sneha Kapoor"
    assert body["customer_code"] == "C-0011"
    assert body["gstin"] == "27AAACA1234B1Z5"
    assert body["is_privileged"] is True
    assert body["is_active"] is True
    assert "id" in body
    assert "created_at" in body


async def test_create_customer_minimal_fields_succeed(
    authenticated_client: AsyncClient,
) -> None:
    """Only ``company_name`` and ``contact_person`` are required."""
    response = await authenticated_client.post(
        CUSTOMERS_URL,
        json={
            "company_name": "Bare Minimum Co.",
            "contact_person": "A. Person",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["is_privileged"] is False  # default
    assert body["is_active"] is True  # default
    assert body["customer_code"] is None
    assert body["gstin"] is None


async def test_create_customer_includes_audit_fields(
    authenticated_client: AsyncClient,
) -> None:
    """Every created row records who created and last touched it."""
    response = await authenticated_client.post(CUSTOMERS_URL, json=_customer_payload())
    body = response.json()

    assert uuid.UUID(body["created_by_user_id"])
    assert uuid.UUID(body["updated_by_user_id"])
    assert body["created_by_user_id"] == body["updated_by_user_id"]


async def test_create_customer_duplicate_code_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    first = await authenticated_client.post(CUSTOMERS_URL, json=_customer_payload())
    assert first.status_code == 201

    second = await authenticated_client.post(
        CUSTOMERS_URL,
        json=_customer_payload(company_name="Different Company", gstin="27AAACA9999X1Z9"),
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CUSTOMER_CODE_ALREADY_EXISTS"


async def test_create_customer_duplicate_gstin_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    first = await authenticated_client.post(CUSTOMERS_URL, json=_customer_payload())
    assert first.status_code == 201

    second = await authenticated_client.post(
        CUSTOMERS_URL,
        json=_customer_payload(company_name="Different Co.", customer_code="C-0099"),
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "GSTIN_ALREADY_EXISTS"


async def test_create_customer_invalid_email_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(
        CUSTOMERS_URL, json=_customer_payload(email="not-an-email")
    )
    assert response.status_code == 422


async def test_create_customer_invalid_gstin_length_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    """GSTIN must be exactly 15 characters."""
    response = await authenticated_client.post(
        CUSTOMERS_URL, json=_customer_payload(gstin="TOO-SHORT")
    )
    assert response.status_code == 422


async def test_create_customer_strips_whitespace_from_code(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(
        CUSTOMERS_URL,
        json=_customer_payload(customer_code="  C-0011  ", company_name="  Padded Co.  "),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["customer_code"] == "C-0011"
    assert body["company_name"] == "Padded Co."


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


async def test_get_customer_returns_200_with_customer(
    authenticated_client: AsyncClient,
) -> None:
    created = await authenticated_client.post(CUSTOMERS_URL, json=_customer_payload())
    customer_id = created.json()["id"]

    response = await authenticated_client.get(_customer_url(customer_id))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == customer_id
    assert body["customer_code"] == "C-0011"


async def test_get_customer_not_found_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.get(_customer_url(uuid.uuid4()))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


async def test_list_customers_returns_paginated_shape(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.get(CUSTOMERS_URL)

    assert response.status_code == 200
    body = response.json()
    assert {"items", "total", "limit", "offset"} <= body.keys()
    assert body["limit"] == 25
    assert body["offset"] == 0


async def test_list_customers_filter_by_is_privileged(
    authenticated_client: AsyncClient,
) -> None:
    await authenticated_client.post(
        CUSTOMERS_URL,
        json=_customer_payload(
            company_name="Privileged Co.",
            customer_code="C-PRIV",
            gstin="27AAACP1234B1Z5",
            is_privileged=True,
        ),
    )
    await authenticated_client.post(
        CUSTOMERS_URL,
        json=_customer_payload(
            company_name="Standard Co.",
            customer_code="C-STD",
            gstin="27AAACS1234B1Z5",
            is_privileged=False,
        ),
    )

    response = await authenticated_client.get(CUSTOMERS_URL, params={"is_privileged": True})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["is_privileged"] is True


async def test_list_customers_search_matches_name_or_code(
    authenticated_client: AsyncClient,
) -> None:
    await authenticated_client.post(
        CUSTOMERS_URL,
        json=_customer_payload(
            company_name="Vector Polymers", customer_code="C-0089", gstin="24AAACV5678C1Z2"
        ),
    )
    await authenticated_client.post(
        CUSTOMERS_URL,
        json=_customer_payload(
            company_name="Northland Bottling", customer_code="C-0124", gstin="06AAACN9012D1Z3"
        ),
    )

    by_name = await authenticated_client.get(CUSTOMERS_URL, params={"search": "polymers"})
    by_code = await authenticated_client.get(CUSTOMERS_URL, params={"search": "0124"})

    assert by_name.json()["total"] == 1
    assert by_name.json()["items"][0]["company_name"] == "Vector Polymers"
    assert by_code.json()["total"] == 1
    assert by_code.json()["items"][0]["customer_code"] == "C-0124"


# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------


async def test_patch_customer_partial_update_succeeds(
    authenticated_client: AsyncClient,
) -> None:
    created = await authenticated_client.post(CUSTOMERS_URL, json=_customer_payload())
    customer_id = created.json()["id"]

    response = await authenticated_client.patch(
        _customer_url(customer_id),
        json={"contact_person": "Sneha K. (renamed)", "is_privileged": False},
    )

    assert response.status_code == 200
    body = response.json()
    # Updated fields changed.
    assert body["contact_person"] == "Sneha K. (renamed)"
    assert body["is_privileged"] is False
    # Untouched fields preserved.
    assert body["company_name"] == "Acme Industries Pvt. Ltd."
    assert body["customer_code"] == "C-0011"


async def test_patch_customer_not_found_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.patch(
        _customer_url(uuid.uuid4()), json={"contact_person": "Anyone"}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"


async def test_patch_customer_can_deactivate_via_is_active_false(
    authenticated_client: AsyncClient,
) -> None:
    """Soft-deactivation via PATCH is allowed for any authenticated user.
    Admin-only DELETE is for irreversible-feeling 'remove from list' actions;
    PATCH is_active=false is the lighter pause/resume."""
    created = await authenticated_client.post(CUSTOMERS_URL, json=_customer_payload())
    customer_id = created.json()["id"]

    response = await authenticated_client.patch(
        _customer_url(customer_id), json={"is_active": False}
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_patch_customer_rejects_unknown_field_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    """``extra='forbid'`` rejects typos like ``compny_name``."""
    created = await authenticated_client.post(CUSTOMERS_URL, json=_customer_payload())
    customer_id = created.json()["id"]

    response = await authenticated_client.patch(
        _customer_url(customer_id), json={"compny_name": "Typo Co."}
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Delete (admin only soft-delete)
# ---------------------------------------------------------------------------


async def test_delete_customer_as_admin_returns_204_and_deactivates(
    admin_authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Soft-delete: row is retained, ``is_active`` flips to false."""
    created = await admin_authenticated_client.post(CUSTOMERS_URL, json=_customer_payload())
    customer_id = uuid.UUID(created.json()["id"])

    response = await admin_authenticated_client.delete(_customer_url(customer_id))

    assert response.status_code == 204
    assert response.content == b""

    customer = await db_session.scalar(select(Customer).where(Customer.id == customer_id))
    assert customer is not None
    assert customer.is_active is False


async def test_delete_customer_not_found_returns_404(
    admin_authenticated_client: AsyncClient,
) -> None:
    response = await admin_authenticated_client.delete(_customer_url(uuid.uuid4()))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"


async def test_delete_already_inactive_customer_is_idempotent(
    admin_authenticated_client: AsyncClient,
) -> None:
    """Second delete on an inactive customer still returns 204, no error."""
    created = await admin_authenticated_client.post(CUSTOMERS_URL, json=_customer_payload())
    customer_id = created.json()["id"]

    first = await admin_authenticated_client.delete(_customer_url(customer_id))
    assert first.status_code == 204

    second = await admin_authenticated_client.delete(_customer_url(customer_id))
    assert second.status_code == 204
