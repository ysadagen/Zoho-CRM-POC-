"""Test factories — build CRM read-model rows for the integration tests.

This service has no write endpoints for CRM data (the Backend owns that), so
tests materialise the rows the engines read directly via the ORM. Each helper
returns an **unsaved** instance with sensible defaults; the test adds it to the
session and commits.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from app.models.customer import Customer
from app.models.customer_target import CustomerTarget
from app.models.invoice import Invoice, Payment
from app.models.item import Item
from app.models.lead import Lead
from app.models.sales_activity import ActivityType, SalesActivity
from app.models.sales_order import SalesOrder, SalesOrderItem, SalesOrderStatus
from app.models.user import User


def make_user(*, is_admin: bool = False, email: str | None = None) -> User:
    return User(
        email=email or f"rep-{uuid.uuid4().hex[:8]}@test.local",
        full_name="Rep",
        hashed_password="x",
        is_admin=is_admin,
    )


def make_customer(actor_id: uuid.UUID, **kw: object) -> Customer:
    defaults: dict[str, object] = {
        "company_name": f"Co-{uuid.uuid4().hex[:6]}",
        "contact_person": "Person",
        "created_by_user_id": actor_id,
        "updated_by_user_id": actor_id,
    }
    defaults.update(kw)
    return Customer(**defaults)


def make_item(actor_id: uuid.UUID, **kw: object) -> Item:
    defaults: dict[str, object] = {
        "sku": f"ITM-{uuid.uuid4().hex[:8]}",
        "name": "Item",
        "type": "RAW",
        "category": "Polymer",
        "unit_of_measure": "kg",
        "unit_price": Decimal("100.00"),
        "standard_cost": Decimal("75.00"),
        "created_by_user_id": actor_id,
        "updated_by_user_id": actor_id,
    }
    defaults.update(kw)
    return Item(**defaults)


def make_lead(assigned_to: uuid.UUID, actor_id: uuid.UUID, **kw: object) -> Lead:
    defaults: dict[str, object] = {
        "lead_number": f"LD-TEST-{uuid.uuid4().hex[:8]}",
        "contact_name": "Lead Contact",
        "source": "OTHER",
        "stage": "NEW",
        "assigned_to_user_id": assigned_to,
        "created_by_user_id": actor_id,
        "updated_by_user_id": actor_id,
    }
    defaults.update(kw)
    return Lead(**defaults)


def make_activity(
    rep_id: uuid.UUID,
    actor_id: uuid.UUID,
    occurred_at: datetime,
    *,
    type_: ActivityType = ActivityType.VISIT,
    customer_id: uuid.UUID | None = None,
    lead_id: uuid.UUID | None = None,
    duration_minutes: int | None = None,
) -> SalesActivity:
    return SalesActivity(
        type=type_,
        rep_user_id=rep_id,
        customer_id=customer_id,
        lead_id=lead_id,
        occurred_at=occurred_at,
        duration_minutes=duration_minutes,
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )


def make_sales_order(
    customer_id: uuid.UUID,
    actor_id: uuid.UUID,
    *,
    total: Decimal,
    shipped_date: date | None,
    status: SalesOrderStatus = SalesOrderStatus.SHIPPED,
) -> SalesOrder:
    return SalesOrder(
        so_number=f"SO-TEST-{uuid.uuid4().hex[:8]}",
        customer_id=customer_id,
        order_date=shipped_date or date.today(),
        shipped_date=shipped_date,
        status=status,
        subtotal=total,
        total=total,
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )


def make_so_item(
    sales_order_id: uuid.UUID, item_id: uuid.UUID, *, quantity: Decimal, unit_price: Decimal
) -> SalesOrderItem:
    return SalesOrderItem(
        sales_order_id=sales_order_id,
        item_id=item_id,
        quantity=quantity,
        unit_price=unit_price,
        line_total=quantity * unit_price,
    )


def make_invoice(
    customer_id: uuid.UUID,
    actor_id: uuid.UUID,
    *,
    amount: Decimal,
    invoice_date: date,
    due_date: date,
) -> Invoice:
    return Invoice(
        invoice_number=f"INV-TEST-{uuid.uuid4().hex[:8]}",
        customer_id=customer_id,
        invoice_date=invoice_date,
        due_date=due_date,
        amount=amount,
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )


def make_payment(
    invoice_id: uuid.UUID, actor_id: uuid.UUID, *, amount: Decimal, paid_date: date
) -> Payment:
    return Payment(
        invoice_id=invoice_id,
        paid_date=paid_date,
        amount=amount,
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )


def make_target(
    customer_id: uuid.UUID,
    actor_id: uuid.UUID,
    *,
    period_start: date,
    period_end: date,
    target_quantity: Decimal,
) -> CustomerTarget:
    return CustomerTarget(
        customer_id=customer_id,
        period_start=period_start,
        period_end=period_end,
        target_quantity=target_quantity,
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )
