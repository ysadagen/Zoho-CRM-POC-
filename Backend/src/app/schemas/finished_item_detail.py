"""Pydantic schemas for the FINISHED-item subtype detail.

Same In/Read split and partial-update semantics as
:mod:`app.schemas.raw_item_detail`. String length caps mirror the ORM
column widths; money fields are non-negative.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.finished_item_detail import DosageForm, DrugSchedule

__all__ = ["FinishedItemDetailIn", "FinishedItemDetailRead"]


class FinishedItemDetailIn(BaseModel):
    """Create/patch payload for a FINISHED item's detail block."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    generic_name: str | None = Field(default=None, max_length=255)
    brand_name: str | None = Field(default=None, max_length=255)
    strength: str | None = Field(default=None, max_length=64)
    dosage_form: DosageForm | None = None
    pack_size: str | None = Field(default=None, max_length=64)
    ingredients: str | None = Field(default=None, max_length=2000)
    container_specification: str | None = Field(default=None, max_length=255)
    selling_price: Decimal | None = Field(default=None, ge=0)
    license_number: str | None = Field(default=None, max_length=64)
    registration_code: str | None = Field(default=None, max_length=64)
    mrp: Decimal | None = Field(default=None, ge=0)
    drug_schedule: DrugSchedule | None = None
    is_prescription_required: bool = False


class FinishedItemDetailRead(BaseModel):
    """FINISHED detail as returned inside ``ItemRead``."""

    model_config = ConfigDict(from_attributes=True)

    generic_name: str | None
    brand_name: str | None
    strength: str | None
    dosage_form: DosageForm | None
    pack_size: str | None
    ingredients: str | None
    container_specification: str | None
    selling_price: Decimal | None
    license_number: str | None
    registration_code: str | None
    mrp: Decimal | None
    drug_schedule: DrugSchedule | None
    is_prescription_required: bool
