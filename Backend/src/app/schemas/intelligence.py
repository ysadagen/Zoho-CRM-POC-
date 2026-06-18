"""Pydantic schemas for the intelligence layer (§9.6).

This module grows over Phase 2B: 2B.0 adds the scoring-config admin shapes;
later slices append the per-engine score read shapes and the recompute
envelope. Every ``*Create`` forbids extra keys so a typo'd param key surfaces
as a validation error rather than silently dropping.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from app.models.score_snapshot import HealthClassification, LeadClassification
from app.models.scoring_config import ScoringEngine

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.lead import Lead
    from app.models.score_snapshot import CustomerHealthScore, LeadScore
    from app.services.scoring.customer_health import CustomerHealthResult

__all__ = [
    "CustomerHealthDetailOut",
    "CustomerHealthList",
    "CustomerHealthOut",
    "CustomerHealthSnapshotOut",
    "LeadScoreComponents",
    "LeadScoreDetailOut",
    "LeadScoreList",
    "LeadScoreListItem",
    "LeadScoreOut",
    "ScoringConfigCreate",
    "ScoringConfigList",
    "ScoringConfigOut",
]


class ScoringConfigOut(BaseModel):
    """A scoring config version as returned to admins."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    engine: ScoringEngine
    version: int
    is_active: bool
    description: str | None
    params: dict[str, Any]
    created_at: datetime


class ScoringConfigList(BaseModel):
    """Envelope for ``GET /intelligence/configs`` (not paginated — few rows)."""

    items: list[ScoringConfigOut]
    total: int


class LeadScoreComponents(BaseModel):
    """The five lead-score parameters (each 0-100)."""

    urgency: int
    location: int
    contribution_margin: int
    quantity: int
    product_margin: int


class LeadScoreOut(BaseModel):
    """A lead score with its component breakdown (§9.6)."""

    lead_id: uuid.UUID
    config_version: int
    computed_at: datetime
    components: LeadScoreComponents
    total_score: float
    classification: LeadClassification
    defaults_applied: list[str]

    @classmethod
    def from_score(cls, score: LeadScore) -> LeadScoreOut:
        return cls(
            lead_id=score.lead_id,
            config_version=score.config.version,
            computed_at=score.computed_at,
            components=LeadScoreComponents(
                urgency=score.urgency_score,
                location=score.location_score,
                contribution_margin=score.contribution_margin_score,
                quantity=score.quantity_score,
                product_margin=score.product_margin_score,
            ),
            total_score=float(score.total_score),
            classification=score.classification,
            defaults_applied=list(score.defaults_applied),
        )


class LeadScoreListItem(LeadScoreOut):
    """A lead score plus enough lead identity to render a list row."""

    lead_number: str
    contact_name: str
    assigned_to_user_id: uuid.UUID

    @classmethod
    def from_score_and_lead(cls, score: LeadScore, lead: Lead) -> LeadScoreListItem:
        base = LeadScoreOut.from_score(score)
        return cls(
            **base.model_dump(),
            lead_number=lead.lead_number,
            contact_name=lead.contact_name,
            assigned_to_user_id=lead.assigned_to_user_id,
        )


class LeadScoreList(BaseModel):
    """Paginated envelope for ``GET /intelligence/lead-scores``."""

    items: list[LeadScoreListItem]
    total: int
    limit: int
    offset: int


class LeadScoreDetailOut(LeadScoreOut):
    """Latest score plus its full snapshot history (newest first)."""

    history: list[LeadScoreOut]


class CustomerHealthOut(BaseModel):
    """Live customer-health score with CPS/CRS component breakdown (§9.6)."""

    customer_id: uuid.UUID
    company_name: str
    computed_at: datetime
    weight_profile: str
    cps: float
    crs: float
    cps_components: dict[str, int]
    crs_components: dict[str, int]
    health_score: float
    classification: HealthClassification
    defaults_applied: list[str]

    @classmethod
    def from_result(
        cls, customer: Customer, result: CustomerHealthResult, computed_at: datetime
    ) -> CustomerHealthOut:
        return cls(
            customer_id=customer.id,
            company_name=customer.company_name,
            computed_at=computed_at,
            weight_profile=result.weight_profile,
            cps=result.cps,
            crs=result.crs,
            cps_components=result.cps_components,
            crs_components=result.crs_components,
            health_score=result.health_score,
            classification=HealthClassification(result.classification),
            defaults_applied=result.defaults_applied,
        )


class CustomerHealthList(BaseModel):
    """Envelope for ``GET /intelligence/customer-health`` (lowest health first)."""

    items: list[CustomerHealthOut]
    total: int


class CustomerHealthSnapshotOut(BaseModel):
    """One historical health snapshot — the trend series."""

    model_config = ConfigDict(from_attributes=True)

    computed_at: datetime
    cps: float
    crs: float
    health_score: float
    classification: HealthClassification


class CustomerHealthDetailOut(CustomerHealthOut):
    """Live health plus the snapshot history (trend, newest first)."""

    history: list[CustomerHealthSnapshotOut]

    @classmethod
    def from_result_and_history(
        cls,
        customer: Customer,
        result: CustomerHealthResult,
        computed_at: datetime,
        history: list[CustomerHealthScore],
    ) -> CustomerHealthDetailOut:
        base = CustomerHealthOut.from_result(customer, result, computed_at)
        return cls(
            **base.model_dump(),
            history=[CustomerHealthSnapshotOut.model_validate(h) for h in history],
        )


class ScoringConfigCreate(BaseModel):
    """Create a new config version for an engine and activate it.

    ``version`` is assigned server-side (max existing + 1); ``params`` is
    validated against the engine's shape in the service (422 on violation).
    """

    model_config = ConfigDict(extra="forbid")

    engine: ScoringEngine
    params: dict[str, Any]
    description: str | None = None
