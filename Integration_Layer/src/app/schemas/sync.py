"""Request/response schemas for Track B push endpoints (/sync/*)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SyncResponse(BaseModel):
    """Returned by every /sync/* endpoint on success."""

    zoho_id: str
    operation: Literal["created", "updated"]


# ---------------------------------------------------------------------------
# Customer → Accounts
# ---------------------------------------------------------------------------

class CustomerSyncRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: uuid.UUID
    company_name: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    gstin: str | None = None
    customer_code: str | None = None
    is_privileged: bool = False
    competitive_risk_level: str = "NONE"
    notes: str | None = None


# ---------------------------------------------------------------------------
# Vendor → Vendors
# ---------------------------------------------------------------------------

class VendorSyncRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: uuid.UUID
    vendor_name: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    gstin: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Item → Products
# ---------------------------------------------------------------------------

class ItemSyncRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: uuid.UUID
    name: str
    sku: str
    item_type: str  # RAW | FINISHED
    unit_of_measure: str
    unit_price: Decimal
    reorder_threshold: Decimal | None = None


# ---------------------------------------------------------------------------
# SalesOrder → Sales_Orders
# ---------------------------------------------------------------------------

class SalesOrderLineItemRequest(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal
    unit_price: Decimal


class SalesOrderSyncRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: uuid.UUID
    so_number: str
    customer_id: uuid.UUID
    order_date: date
    status: str  # DRAFT | SHIPPED
    notes: str | None = None
    items: list[SalesOrderLineItemRequest] = []


# ---------------------------------------------------------------------------
# PurchaseOrder → Purchase_Orders
# ---------------------------------------------------------------------------

class PurchaseOrderLineItemRequest(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal
    unit_price: Decimal


class PurchaseOrderSyncRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: uuid.UUID
    po_number: str
    vendor_id: uuid.UUID
    order_date: date
    status: str  # DRAFT | RECEIVED
    notes: str | None = None
    items: list[PurchaseOrderLineItemRequest] = []


# ---------------------------------------------------------------------------
# Lead → Leads
# ---------------------------------------------------------------------------

class LeadSyncRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: uuid.UUID
    contact_name: str
    source: str  # LeadSource value
    stage: str   # LeadStage value
    phone: str | None = None
    email: str | None = None
    state: str | None = None
    city: str | None = None
    notes: str | None = None
    estimated_budget: Decimal | None = None
