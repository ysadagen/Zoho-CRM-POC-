"""Customer-target business logic — CRUD with non-overlap enforcement."""

from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.customer_target import CustomerTarget
from app.repositories.customer_repo import CustomerRepository
from app.repositories.customer_target_repo import CustomerTargetRepository
from app.schemas.customer_target import CustomerTargetCreate, CustomerTargetUpdate

logger = logging.getLogger(__name__)


class CustomerTargetService:
    """Orchestrates customer-target flows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._targets = CustomerTargetRepository(session)
        self._customers = CustomerRepository(session)

    async def list_for_customer(self, customer_id: uuid.UUID) -> list[CustomerTarget]:
        await self._require_customer(customer_id)
        return await self._targets.list_for_customer(customer_id)

    async def create(
        self,
        customer_id: uuid.UUID,
        payload: CustomerTargetCreate,
        *,
        actor_id: uuid.UUID,
    ) -> CustomerTarget:
        """Create a target. 404 if the customer is unknown; 409
        ``OVERLAPPING_TARGET_PERIOD`` if it overlaps an existing period."""
        await self._require_customer(customer_id)
        await self._reject_overlap(
            customer_id=customer_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
            exclude_id=None,
        )

        target = CustomerTarget(
            customer_id=customer_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
            target_quantity=payload.target_quantity,
            target_revenue=payload.target_revenue,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        try:
            target = await self._targets.add(target)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                "A target for that exact period already exists",
                code="OVERLAPPING_TARGET_PERIOD",
            ) from exc

        await self._session.refresh(target)
        logger.info(
            "customer_target_created",
            extra={"target_id": str(target.id), "customer_id": str(customer_id)},
        )
        return target

    async def update(
        self,
        customer_id: uuid.UUID,
        target_id: uuid.UUID,
        payload: CustomerTargetUpdate,
        *,
        actor_id: uuid.UUID,
    ) -> CustomerTarget:
        """Apply a partial update; re-validates period order and overlap
        against the merged values."""
        target = await self._get_owned(customer_id, target_id)
        updates = payload.model_dump(exclude_unset=True)

        new_start = updates.get("period_start", target.period_start)
        new_end = updates.get("period_end", target.period_end)
        if new_end <= new_start:
            raise ValidationError(
                "period_end must be after period_start",
                code="INVALID_TARGET_PERIOD",
            )
        if "period_start" in updates or "period_end" in updates:
            await self._reject_overlap(
                customer_id=customer_id,
                period_start=new_start,
                period_end=new_end,
                exclude_id=target.id,
            )

        for field, value in updates.items():
            setattr(target, field, value)
        target.updated_by_user_id = actor_id

        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                "A target for that exact period already exists",
                code="OVERLAPPING_TARGET_PERIOD",
            ) from exc

        await self._session.refresh(target)
        logger.info(
            "customer_target_updated",
            extra={"target_id": str(target.id), "fields": sorted(updates.keys())},
        )
        return target

    async def _require_customer(self, customer_id: uuid.UUID) -> None:
        if await self._customers.get_by_id(customer_id) is None:
            raise NotFoundError("Customer not found", code="CUSTOMER_NOT_FOUND")

    async def _get_owned(self, customer_id: uuid.UUID, target_id: uuid.UUID) -> CustomerTarget:
        target = await self._targets.get_by_id(target_id)
        if target is None or target.customer_id != customer_id:
            raise NotFoundError("Target not found", code="TARGET_NOT_FOUND")
        return target

    async def _reject_overlap(
        self,
        *,
        customer_id: uuid.UUID,
        period_start: date,
        period_end: date,
        exclude_id: uuid.UUID | None,
    ) -> None:
        existing = await self._targets.find_overlapping(
            customer_id=customer_id,
            period_start=period_start,
            period_end=period_end,
            exclude_id=exclude_id,
        )
        if existing is not None:
            raise ConflictError(
                "A target overlapping that period already exists",
                code="OVERLAPPING_TARGET_PERIOD",
            )
