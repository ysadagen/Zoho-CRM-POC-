"""Zoho-ingest business logic (Track A — Zoho → app, via the Integration Layer).

A faithful, idempotent mirror of Zoho into the existing ``leads`` and
``sales_activities`` tables. Distinct from the interactive lead/activity
services in two deliberate ways:

* **Stage is set directly** (not walked through the interactive transition
  state machine): Zoho is authoritative for an ingested lead, so a status that
  jumps the funnel must still land. Every DB CHECK and the append-only history
  trail are honoured — only the *interactive legality* rule is bypassed.
* **There is no human actor.** The audit columns (``created_by``/
  ``updated_by``/``changed_by``) are stamped with the resolved rep/owner, who
  is the real source of the record in Zoho.

The owner is already resolved to a local user id by the IL; this service only
validates that referenced users/customers/items/leads exist.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.lead import Lead, LeadStage, LeadStageHistory
from app.models.sales_activity import SalesActivity
from app.models.user import User
from app.repositories.customer_repo import CustomerRepository
from app.repositories.item_repo import ItemRepository
from app.repositories.lead_repo import LeadRepository
from app.repositories.sales_activity_repo import SalesActivityRepository
from app.repositories.user_repo import UserRepository
from app.schemas.ingest import ActivityIngest, LeadIngestCreate, LeadIngestUpdate

logger = logging.getLogger(__name__)

# Lead fields an update may set straight onto the row (stage + terminal fields
# are handled separately because they drive history and the CHECK constraints).
_LEAD_PLAIN_UPDATE_FIELDS = (
    "contact_name",
    "source",
    "assigned_to_user_id",
    "customer_id",
    "phone",
    "email",
    "item_id",
    "quantity",
    "estimated_budget",
    "dealer_potential",
    "required_by_date",
    "state",
    "district",
    "city",
    "pincode",
    "notes",
)


def _as_utc(value: datetime | None) -> datetime | None:
    """Coerce a naive datetime to UTC; pass through tz-aware / ``None``."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class IngestService:
    """Upsert Zoho-sourced leads and activities into the app's own tables."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._leads = LeadRepository(session)
        self._customers = CustomerRepository(session)
        self._items = ItemRepository(session)
        self._activities = SalesActivityRepository(session)

    async def list_users(self) -> list[User]:
        """Return all users, for the IL's owner-email → app-user resolver."""
        # 3-user POC; a generous page is effectively "all". Ordering is the
        # repository's default (newest first) — the IL builds a dict by email.
        users, _ = await self._users.list_(limit=1000, offset=0)
        return users

    async def create_lead(self, payload: LeadIngestCreate) -> Lead:
        """Create a lead mirrored from Zoho, with its creation-history row.

        Validates the resolved owner / customer / item exist (404 otherwise).
        ``created_at`` is set from the Zoho creation instant when supplied.
        """
        await self._require_user(payload.assigned_to_user_id, "Assigned user not found")
        await self._require_customer(payload.customer_id)
        await self._require_item(payload.item_id)

        actor_id = payload.assigned_to_user_id
        lead = Lead(
            lead_number=await self._leads.next_lead_number(),
            stage=payload.stage,
            contact_name=payload.contact_name,
            source=payload.source,
            assigned_to_user_id=payload.assigned_to_user_id,
            customer_id=payload.customer_id,
            phone=payload.phone,
            email=payload.email,
            item_id=payload.item_id,
            quantity=payload.quantity,
            estimated_budget=payload.estimated_budget,
            dealer_potential=payload.dealer_potential,
            required_by_date=payload.required_by_date,
            state=payload.state,
            district=payload.district,
            city=payload.city,
            pincode=payload.pincode,
            notes=payload.notes,
            won_value=payload.won_value,
            won_at=_as_utc(payload.won_at),
            lost_at=_as_utc(payload.lost_at),
            lost_reason=payload.lost_reason,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        source_created_at = _as_utc(payload.source_created_at)
        if source_created_at is not None:
            lead.created_at = source_created_at

        lead = await self._leads.add(lead)
        await self._leads.add_stage_history(
            LeadStageHistory(
                lead_id=lead.id,
                from_stage=None,
                to_stage=payload.stage,
                changed_by_user_id=actor_id,
            )
        )
        await self._session.commit()
        await self._session.refresh(lead)
        logger.info(
            "lead_ingested",
            extra={
                "lead_id": str(lead.id),
                "lead_number": lead.lead_number,
                "stage": lead.stage.value,
            },
        )
        return lead

    async def update_lead(self, lead_id: uuid.UUID, payload: LeadIngestUpdate) -> Lead:
        """Apply a mirrored update to an existing lead.

        Plain fields are set directly. A changed ``stage`` is written
        directly (Zoho-authoritative) with the terminal fields stamped/cleared
        to keep the CHECK satisfied, and an append-only history row recorded.
        """
        lead = await self._leads.get_by_id(lead_id)
        if lead is None:
            raise NotFoundError("Lead not found", code="LEAD_NOT_FOUND")

        updates = payload.model_dump(
            exclude_unset=True,
            include=set(_LEAD_PLAIN_UPDATE_FIELDS),
        )
        if "assigned_to_user_id" in updates:
            await self._require_user(updates["assigned_to_user_id"], "Assigned user not found")
        if "customer_id" in updates:
            await self._require_customer(updates["customer_id"])
        if "item_id" in updates:
            await self._require_item(updates["item_id"])
        for field, value in updates.items():
            setattr(lead, field, value)

        actor_id = lead.assigned_to_user_id
        if payload.stage is not None and payload.stage != lead.stage:
            self._apply_stage(lead, payload, actor_id=actor_id)

        lead.updated_by_user_id = actor_id
        await self._session.commit()
        await self._session.refresh(lead)
        logger.info(
            "lead_ingest_updated",
            extra={"lead_id": str(lead.id), "stage": lead.stage.value},
        )
        return lead

    def _apply_stage(self, lead: Lead, payload: LeadIngestUpdate, *, actor_id: uuid.UUID) -> None:
        """Set a lead's stage directly and append a history row.

        Terminal fields are stamped for WON/LOST and cleared for any
        non-terminal stage, so the lead always satisfies the DB CHECKs.
        """
        from_stage = lead.stage
        lead.stage = payload.stage  # type: ignore[assignment]  # guarded non-None by caller
        if payload.stage == LeadStage.WON:
            lead.won_value = payload.won_value
            lead.won_at = _as_utc(payload.won_at)
            lead.lost_at = None
            lead.lost_reason = None
        elif payload.stage == LeadStage.LOST:
            lead.lost_at = _as_utc(payload.lost_at)
            lead.lost_reason = payload.lost_reason
            lead.won_value = None
            lead.won_at = None
        else:
            lead.won_value = None
            lead.won_at = None
            lead.lost_at = None
            lead.lost_reason = None
        self._session.add(
            LeadStageHistory(
                lead_id=lead.id,
                from_stage=from_stage,
                to_stage=payload.stage,
                changed_by_user_id=actor_id,
                remark="Ingested from Zoho",
            )
        )

    async def create_activity(self, payload: ActivityIngest) -> SalesActivity:
        """Create a sales activity mirrored from a Zoho Call/Meeting/Task."""
        if payload.customer_id is None and payload.lead_id is None:
            raise ValidationError(
                "An activity must reference a customer and/or a lead",
                code="SUBJECT_REQUIRED",
            )
        await self._require_user(payload.rep_user_id, "Rep user not found")
        await self._require_customer(payload.customer_id)
        if payload.lead_id is not None and await self._leads.get_by_id(payload.lead_id) is None:
            raise NotFoundError("Lead not found", code="LEAD_NOT_FOUND")

        activity = SalesActivity(
            type=payload.type,
            rep_user_id=payload.rep_user_id,
            customer_id=payload.customer_id,
            lead_id=payload.lead_id,
            occurred_at=_as_utc(payload.occurred_at),
            duration_minutes=payload.duration_minutes,
            remarks=payload.remarks,
            created_by_user_id=payload.rep_user_id,
            updated_by_user_id=payload.rep_user_id,
        )
        activity = await self._activities.add(activity)
        await self._session.commit()
        await self._session.refresh(activity)
        logger.info(
            "activity_ingested",
            extra={
                "activity_id": str(activity.id),
                "type": activity.type.value,
                "rep_user_id": str(activity.rep_user_id),
            },
        )
        return activity

    async def _require_user(self, user_id: uuid.UUID, message: str) -> None:
        if await self._users.get_by_id(user_id) is None:
            raise NotFoundError(message, code="USER_NOT_FOUND")

    async def _require_customer(self, customer_id: uuid.UUID | None) -> None:
        if customer_id is not None and await self._customers.get_by_id(customer_id) is None:
            raise NotFoundError("Customer not found", code="CUSTOMER_NOT_FOUND")

    async def _require_item(self, item_id: uuid.UUID | None) -> None:
        if item_id is not None and await self._items.get_by_id(item_id) is None:
            raise NotFoundError("Item not found", code="ITEM_NOT_FOUND")
