"""Sales-activity business logic — append-only create + read.

No update or delete: activities are immutable facts (a correction is a new
row). The service defaults ``rep_user_id`` to the actor, enforces the
subject rule (customer and/or lead) with a specific ``SUBJECT_REQUIRED``
code, and validates that every referenced entity exists.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.sales_activity import ActivityType, SalesActivity
from app.repositories.customer_repo import CustomerRepository
from app.repositories.lead_repo import LeadRepository
from app.repositories.sales_activity_repo import SalesActivityRepository
from app.repositories.user_repo import UserRepository
from app.schemas.sales_activity import ActivityCreate

logger = logging.getLogger(__name__)


class SalesActivityService:
    """Orchestrates sales-activity create / read flows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._activities = SalesActivityRepository(session)
        self._users = UserRepository(session)
        self._customers = CustomerRepository(session)
        self._leads = LeadRepository(session)

    async def create(self, payload: ActivityCreate, *, actor_id: uuid.UUID) -> SalesActivity:
        """Record an activity. ``rep_user_id`` defaults to the actor.

        Raises 422 ``SUBJECT_REQUIRED`` if neither a customer nor a lead is
        given, and 404 if the rep / customer / lead does not exist.
        """
        if payload.customer_id is None and payload.lead_id is None:
            raise ValidationError(
                "An activity must reference a customer and/or a lead",
                code="SUBJECT_REQUIRED",
            )

        rep_user_id = payload.rep_user_id or actor_id
        if await self._users.get_by_id(rep_user_id) is None:
            raise NotFoundError("Rep user not found", code="USER_NOT_FOUND")
        if payload.customer_id is not None:
            customer = await self._customers.get_by_id(payload.customer_id)
            if customer is None:
                raise NotFoundError("Customer not found", code="CUSTOMER_NOT_FOUND")
        if payload.lead_id is not None:
            lead = await self._leads.get_by_id(payload.lead_id)
            if lead is None:
                raise NotFoundError("Lead not found", code="LEAD_NOT_FOUND")

        activity = SalesActivity(
            type=payload.type,
            rep_user_id=rep_user_id,
            customer_id=payload.customer_id,
            lead_id=payload.lead_id,
            occurred_at=payload.occurred_at,
            duration_minutes=payload.duration_minutes,
            remarks=payload.remarks,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        activity = await self._activities.add(activity)
        await self._session.commit()
        await self._session.refresh(activity)
        logger.info(
            "sales_activity_recorded",
            extra={
                "activity_id": str(activity.id),
                "type": activity.type.value,
                "rep_user_id": str(activity.rep_user_id),
            },
        )
        return activity

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        type_: ActivityType | None = None,
        rep_user_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        lead_id: uuid.UUID | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> tuple[list[SalesActivity], int]:
        return await self._activities.list_(
            limit=limit,
            offset=offset,
            type_=type_,
            rep_user_id=rep_user_id,
            customer_id=customer_id,
            lead_id=lead_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        )
