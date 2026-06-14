"""Customer-related Pydantic schemas.

``customer_code`` and ``gstin`` are optional **but unique when present** —
the schema enforces non-empty values (``min_length=1`` resp. ``15``) so an
empty string can't sneak in and collide with another empty string at the
DB unique-constraint level.

``email`` is a regular ``EmailStr | None`` — no normalisation to lower
because customer email isn't a login identity (no case-insensitive lookup
needed).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

__all__ = [
    "CustomerCreate",
    "CustomerList",
    "CustomerRead",
    "CustomerUpdate",
]


class CustomerCreate(BaseModel):
    """Payload to create a new customer."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_name: str = Field(min_length=1, max_length=160)
    contact_person: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, min_length=1, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, min_length=1, max_length=2000)
    is_privileged: bool = False
    customer_code: str | None = Field(default=None, min_length=1, max_length=60)
    gstin: str | None = Field(default=None, min_length=15, max_length=15)
    notes: str | None = Field(default=None, max_length=2000)


class CustomerUpdate(BaseModel):
    """Partial update for an existing customer.

    All fields optional. ``extra="forbid"`` so typos (``compny_name``)
    fail with 422 instead of silently no-op'ing. ``id``,
    ``created_by_user_id``, ``created_at`` are not in this schema
    because they are server-owned identity/provenance.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_name: str | None = Field(default=None, min_length=1, max_length=160)
    contact_person: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, min_length=1, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, min_length=1, max_length=2000)
    is_privileged: bool | None = None
    customer_code: str | None = Field(default=None, min_length=1, max_length=60)
    gstin: str | None = Field(default=None, min_length=15, max_length=15)
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class CustomerRead(BaseModel):
    """Customer as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_name: str
    contact_person: str
    phone: str | None
    email: EmailStr | None
    address: str | None
    is_privileged: bool
    customer_code: str | None
    gstin: str | None
    notes: str | None
    is_active: bool
    created_by_user_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CustomerList(BaseModel):
    """Paginated envelope for ``GET /customers`` (CLAUDE.md §6)."""

    items: list[CustomerRead]
    total: int
    limit: int
    offset: int
