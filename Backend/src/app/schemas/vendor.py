"""Vendor-related Pydantic schemas.

Mirrors :mod:`app.schemas.customer` minus the ``is_privileged`` tier
flag (vendors don't have a privileged-vs-standard distinction in the
business spec).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

__all__ = [
    "VendorCreate",
    "VendorList",
    "VendorRead",
    "VendorUpdate",
]


class VendorCreate(BaseModel):
    """Payload to create a new vendor."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    vendor_name: str = Field(min_length=1, max_length=160)
    contact_person: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, min_length=1, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, min_length=1, max_length=2000)
    vendor_code: str | None = Field(default=None, min_length=1, max_length=60)
    gstin: str | None = Field(default=None, min_length=15, max_length=15)
    notes: str | None = Field(default=None, max_length=2000)


class VendorUpdate(BaseModel):
    """Partial update for an existing vendor."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    vendor_name: str | None = Field(default=None, min_length=1, max_length=160)
    contact_person: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, min_length=1, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, min_length=1, max_length=2000)
    vendor_code: str | None = Field(default=None, min_length=1, max_length=60)
    gstin: str | None = Field(default=None, min_length=15, max_length=15)
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class VendorRead(BaseModel):
    """Vendor as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vendor_name: str
    contact_person: str
    phone: str | None
    email: EmailStr | None
    address: str | None
    vendor_code: str | None
    gstin: str | None
    notes: str | None
    is_active: bool
    created_by_user_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class VendorList(BaseModel):
    """Paginated envelope for ``GET /vendors`` (CLAUDE.md §6)."""

    items: list[VendorRead]
    total: int
    limit: int
    offset: int
