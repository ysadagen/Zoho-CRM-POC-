"""Schemas for the internal Zoho-ingest endpoints (Track A).

These are the contract between the Integration Layer (caller) and the Backend
(writer). Unlike the interactive lead/activity schemas, ingest is a faithful
mirror of Zoho: ``stage`` is settable directly (Zoho is authoritative for an
ingested lead) and ``source_created_at`` carries the Zoho creation instant so
time-to-close is computed against when the lead really originated, not when we
happened to pull it.

The owner is already resolved to a local ``assigned_to_user_id`` /
``rep_user_id`` by the IL (email → app user); the Backend only validates the
id exists. Terminal-state consistency (WON needs value+date, LOST needs
reason+date) is enforced here so the DB CHECK is never the first line of
defence.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.lead import DealerPotential, LeadSource, LeadStage
from app.models.sales_activity import ActivityType

__all__ = [
    "ActivityIngest",
    "ActivityIngestResult",
    "IngestUserList",
    "IngestUserRead",
    "LeadIngestCreate",
    "LeadIngestResult",
    "LeadIngestUpdate",
]


def _validate_terminal_fields(
    *,
    stage: LeadStage | None,
    won_value: Decimal | None,
    won_at: datetime | None,
    lost_at: datetime | None,
    lost_reason: str | None,
) -> None:
    """Enforce the lead terminal-state rules shared by create and update.

    Mirrors the DB CHECKs: a WON stage requires ``won_value`` + ``won_at`` (and
    no LOST fields); a LOST stage requires ``lost_at`` + ``lost_reason`` (and no
    won value); any non-terminal stage forbids all terminal fields. ``stage is
    None`` (an update that doesn't touch stage) skips the check.
    """
    if stage is None:
        return
    if stage == LeadStage.WON:
        if won_value is None or won_at is None:
            raise ValueError("WON requires won_value and won_at")
        if lost_at is not None or lost_reason is not None:
            raise ValueError("LOST fields are not valid for a WON lead")
    elif stage == LeadStage.LOST:
        if lost_at is None or lost_reason is None:
            raise ValueError("LOST requires lost_at and lost_reason")
        if won_value is not None or won_at is not None:
            raise ValueError("won fields are not valid for a LOST lead")
    elif any(v is not None for v in (won_value, won_at, lost_at, lost_reason)):
        raise ValueError("won/lost fields are only valid for a WON/LOST stage")


class LeadIngestCreate(BaseModel):
    """Create a lead from a Zoho record (owner already resolved to a local id)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    contact_name: str = Field(min_length=1, max_length=160)
    source: LeadSource
    stage: LeadStage = LeadStage.NEW
    assigned_to_user_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    phone: str | None = Field(default=None, min_length=1, max_length=40)
    email: str | None = Field(default=None, max_length=160)
    item_id: uuid.UUID | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    estimated_budget: Decimal | None = Field(default=None, ge=0)
    dealer_potential: DealerPotential | None = None
    required_by_date: date | None = None
    state: str | None = Field(default=None, min_length=1, max_length=120)
    district: str | None = Field(default=None, min_length=1, max_length=120)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    pincode: str | None = Field(default=None, min_length=1, max_length=20)
    notes: str | None = Field(default=None, max_length=2000)
    # Zoho's Created_Time → lead.created_at (accurate time-to-close).
    source_created_at: datetime | None = None
    # Terminal fields — set only when ingesting a lead already WON/LOST in Zoho.
    won_value: Decimal | None = Field(default=None, gt=0)
    won_at: datetime | None = None
    lost_at: datetime | None = None
    lost_reason: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def _check_terminal(self) -> Self:
        _validate_terminal_fields(
            stage=self.stage,
            won_value=self.won_value,
            won_at=self.won_at,
            lost_at=self.lost_at,
            lost_reason=self.lost_reason,
        )
        return self


class LeadIngestUpdate(BaseModel):
    """Update an already-ingested lead (stage move, owner change, won Deal)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    contact_name: str | None = Field(default=None, min_length=1, max_length=160)
    source: LeadSource | None = None
    stage: LeadStage | None = None
    assigned_to_user_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    phone: str | None = Field(default=None, min_length=1, max_length=40)
    email: str | None = Field(default=None, max_length=160)
    item_id: uuid.UUID | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    estimated_budget: Decimal | None = Field(default=None, ge=0)
    dealer_potential: DealerPotential | None = None
    required_by_date: date | None = None
    state: str | None = Field(default=None, min_length=1, max_length=120)
    district: str | None = Field(default=None, min_length=1, max_length=120)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    pincode: str | None = Field(default=None, min_length=1, max_length=20)
    notes: str | None = Field(default=None, max_length=2000)
    won_value: Decimal | None = Field(default=None, gt=0)
    won_at: datetime | None = None
    lost_at: datetime | None = None
    lost_reason: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def _check_terminal(self) -> Self:
        _validate_terminal_fields(
            stage=self.stage,
            won_value=self.won_value,
            won_at=self.won_at,
            lost_at=self.lost_at,
            lost_reason=self.lost_reason,
        )
        return self


class LeadIngestResult(BaseModel):
    """What the Backend returns to the IL after an upsert (drives mapping)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_number: str
    stage: LeadStage


class ActivityIngest(BaseModel):
    """Create a sales activity from a Zoho Call/Meeting/Task (append-only)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: ActivityType
    rep_user_id: uuid.UUID
    occurred_at: datetime
    customer_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    remarks: str | None = Field(default=None, max_length=2000)


class ActivityIngestResult(BaseModel):
    """What the Backend returns after creating an ingested activity."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class IngestUserRead(BaseModel):
    """An app user, for the IL's owner-email → app-user resolver."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool


class IngestUserList(BaseModel):
    """All app users the IL may attribute ingested records to."""

    items: list[IngestUserRead]
