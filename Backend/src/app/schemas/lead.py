"""Lead-related Pydantic schemas.

``stage`` is deliberately **absent** from ``LeadCreate`` (every lead starts
at NEW) and from ``LeadUpdate`` (stage changes go through the dedicated
``/transition`` endpoint so the state machine and history trail can't be
bypassed). ``StageTransitionRequest`` enforces the terminal-state rules
(WON needs a value, LOST needs a reason) at the schema layer → clean 422.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.lead import DealerPotential, LeadSource, LeadStage

__all__ = [
    "DealerPotential",
    "LeadCreate",
    "LeadDetailRead",
    "LeadList",
    "LeadRead",
    "LeadSource",
    "LeadStage",
    "LeadStageHistoryRead",
    "LeadUpdate",
    "StageTransitionRequest",
]


class LeadCreate(BaseModel):
    """Payload to create a new lead. The lead always starts at stage NEW."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    contact_name: str = Field(min_length=1, max_length=160)
    source: LeadSource
    assigned_to_user_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    phone: str | None = Field(default=None, min_length=1, max_length=40)
    email: EmailStr | None = None
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


class LeadUpdate(BaseModel):
    """Partial update for a lead. ``stage`` is not updatable here — use
    ``POST /leads/{id}/transition``."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    contact_name: str | None = Field(default=None, min_length=1, max_length=160)
    source: LeadSource | None = None
    assigned_to_user_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    phone: str | None = Field(default=None, min_length=1, max_length=40)
    email: EmailStr | None = None
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
    is_active: bool | None = None


class StageTransitionRequest(BaseModel):
    """Request to move a lead to a new stage.

    Cross-field rules (enforced here → 422):
    * ``WON`` requires ``won_value`` (> 0).
    * ``LOST`` requires ``lost_reason``.
    * Neither field is accepted for any other target stage (avoids
      setting a win value on, say, a QUALIFICATION move).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    to_stage: LeadStage
    remark: str | None = Field(default=None, max_length=500)
    won_value: Decimal | None = Field(default=None, gt=0)
    lost_reason: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def _check_terminal_fields(self) -> StageTransitionRequest:
        if self.to_stage == LeadStage.WON:
            if self.won_value is None:
                raise ValueError("won_value is required when transitioning to WON")
            if self.lost_reason is not None:
                raise ValueError("lost_reason is not valid for a WON transition")
        elif self.to_stage == LeadStage.LOST:
            if self.lost_reason is None:
                raise ValueError("lost_reason is required when transitioning to LOST")
            if self.won_value is not None:
                raise ValueError("won_value is not valid for a LOST transition")
        else:
            if self.won_value is not None or self.lost_reason is not None:
                raise ValueError(
                    "won_value / lost_reason are only valid for WON / LOST transitions"
                )
        return self


class LeadRead(BaseModel):
    """Lead as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_number: str
    stage: LeadStage
    contact_name: str
    source: LeadSource
    assigned_to_user_id: uuid.UUID
    customer_id: uuid.UUID | None
    phone: str | None
    email: EmailStr | None
    item_id: uuid.UUID | None
    quantity: Decimal | None
    estimated_budget: Decimal | None
    dealer_potential: DealerPotential | None
    required_by_date: date | None
    state: str | None
    district: str | None
    city: str | None
    pincode: str | None
    won_value: Decimal | None
    won_at: datetime | None
    lost_at: datetime | None
    lost_reason: str | None
    notes: str | None
    is_active: bool
    created_by_user_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class LeadStageHistoryRead(BaseModel):
    """One append-only stage-transition record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_stage: LeadStage | None
    to_stage: LeadStage
    changed_at: datetime
    changed_by_user_id: uuid.UUID
    remark: str | None


class LeadDetailRead(LeadRead):
    """Lead detail — the full record plus its stage history (newest first)."""

    stage_history: list[LeadStageHistoryRead]


class LeadList(BaseModel):
    """Paginated envelope for ``GET /leads`` (CLAUDE.md §6)."""

    items: list[LeadRead]
    total: int
    limit: int
    offset: int
