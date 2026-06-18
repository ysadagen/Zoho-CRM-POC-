"""Tests for /api/v1/invoices — create, list, detail, payments, overpayment."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice

INVOICES_URL = "/api/v1/invoices"
CUSTOMERS_URL = "/api/v1/customers"


async def _customer_id(client: AsyncClient) -> str:
    resp = await client.post(
        CUSTOMERS_URL, json={"company_name": "Inv Co", "contact_person": "Inv Person"}
    )
    return resp.json()["id"]


def _invoice_payload(customer_id: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "customer_id": customer_id,
        "invoice_date": "2026-05-01",
        "due_date": "2026-05-31",
        "amount": "100000",
    }
    base.update(overrides)
    return base


async def test_create_invoice_generates_number_and_full_outstanding(
    authenticated_client: AsyncClient,
) -> None:
    cid = await _customer_id(authenticated_client)
    resp = await authenticated_client.post(INVOICES_URL, json=_invoice_payload(cid))
    assert resp.status_code == 201
    body = resp.json()
    assert body["invoice_number"].startswith("INV-")
    assert body["amount"] == "100000.00"
    assert body["amount_paid"] == "0.00"
    assert body["outstanding"] == "100000.00"
    assert body["is_paid"] is False


async def test_create_invoice_unknown_customer_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    resp = await authenticated_client.post(
        INVOICES_URL, json=_invoice_payload(str(uuid.uuid4()))
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"


async def test_create_invoice_due_before_invoice_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    cid = await _customer_id(authenticated_client)
    resp = await authenticated_client.post(
        INVOICES_URL,
        json=_invoice_payload(cid, invoice_date="2026-05-31", due_date="2026-05-01"),
    )
    assert resp.status_code == 422


async def test_record_payment_updates_outstanding(authenticated_client: AsyncClient) -> None:
    cid = await _customer_id(authenticated_client)
    created = await authenticated_client.post(INVOICES_URL, json=_invoice_payload(cid))
    invoice_id = created.json()["id"]

    resp = await authenticated_client.post(
        f"{INVOICES_URL}/{invoice_id}/payments",
        json={"paid_date": "2026-05-20", "amount": "40000"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["amount_paid"] == "40000.00"
    assert body["outstanding"] == "60000.00"
    assert body["is_paid"] is False


async def test_full_payment_marks_invoice_paid(authenticated_client: AsyncClient) -> None:
    cid = await _customer_id(authenticated_client)
    created = await authenticated_client.post(INVOICES_URL, json=_invoice_payload(cid))
    invoice_id = created.json()["id"]

    resp = await authenticated_client.post(
        f"{INVOICES_URL}/{invoice_id}/payments",
        json={"paid_date": "2026-05-20", "amount": "100000"},
    )
    assert resp.json()["is_paid"] is True
    assert resp.json()["outstanding"] == "0.00"


async def test_overpayment_returns_409(authenticated_client: AsyncClient) -> None:
    cid = await _customer_id(authenticated_client)
    created = await authenticated_client.post(INVOICES_URL, json=_invoice_payload(cid))
    invoice_id = created.json()["id"]
    await authenticated_client.post(
        f"{INVOICES_URL}/{invoice_id}/payments",
        json={"paid_date": "2026-05-20", "amount": "80000"},
    )
    # 80k already paid; another 30k would exceed the 100k invoice.
    resp = await authenticated_client.post(
        f"{INVOICES_URL}/{invoice_id}/payments",
        json={"paid_date": "2026-05-21", "amount": "30000"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "OVERPAYMENT"


async def test_invoice_detail_lists_payments(authenticated_client: AsyncClient) -> None:
    cid = await _customer_id(authenticated_client)
    created = await authenticated_client.post(INVOICES_URL, json=_invoice_payload(cid))
    invoice_id = created.json()["id"]
    await authenticated_client.post(
        f"{INVOICES_URL}/{invoice_id}/payments",
        json={"paid_date": "2026-05-20", "amount": "25000"},
    )

    detail = await authenticated_client.get(f"{INVOICES_URL}/{invoice_id}")
    assert detail.status_code == 200
    assert len(detail.json()["payments"]) == 1
    assert detail.json()["payments"][0]["amount"] == "25000.00"


async def test_record_payment_unknown_invoice_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    resp = await authenticated_client.post(
        f"{INVOICES_URL}/{uuid.uuid4()}/payments",
        json={"paid_date": "2026-05-20", "amount": "100"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "INVOICE_NOT_FOUND"


async def test_db_rejects_non_positive_invoice_amount_when_set_directly(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The amount CHECK rejects a non-positive invoice even via the ORM."""
    cid = await _customer_id(authenticated_client)
    created = await authenticated_client.post(INVOICES_URL, json=_invoice_payload(cid))
    invoice_id = uuid.UUID(created.json()["id"])

    invoice = await db_session.scalar(select(Invoice).where(Invoice.id == invoice_id))
    assert invoice is not None
    invoice.amount = invoice.amount * 0  # zero — violates amount > 0

    with pytest.raises(IntegrityError):
        await db_session.flush()
