"""Lead business logic — CRUD + the stage-transition state machine.

The service owns two invariants the rest of the system relies on:

1. **Every lead has a creation-history row** (``to_stage = NEW``) written in
   the same transaction as the lead — so the append-only trail is complete
   from birth.
2. **Stage only ever changes through** :meth:`transition`, which validates
   the move against :data:`LEAD_STAGE_TRANSITIONS`, stamps the terminal
   fields (WON value / LOST reason), and appends a history row — all
   atomically. ``LeadUpdate`` has no ``stage`` field, so PATCH cannot bypass
   this.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.lead import (
    LEAD_STAGE_TRANSITIONS,
    Lead,
    LeadSource,
    LeadStage,
    LeadStageHistory,
)
from app.models.score_snapshot import LeadScore
from app.repositories.customer_repo import CustomerRepository
from app.repositories.item_repo import ItemRepository
from app.repositories.lead_repo import LeadRepository
from app.repositories.score_snapshot_repo import ScoreSnapshotRepository
from app.repositories.user_repo import UserRepository
from app.schemas.lead import LeadCreate, LeadUpdate, StageTransitionRequest
from app.services.scoring.lead_scoring import LEAD_SCORING_INPUT_FIELDS, LeadScoringService

logger = logging.getLogger(__name__)


class LeadService:
    """Orchestrates lead create / read / update / transition flows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._leads = LeadRepository(session)
        self._customers = CustomerRepository(session)
        self._items = ItemRepository(session)
        self._users = UserRepository(session)
        self._scorer = LeadScoringService(session)
        self._snapshots = ScoreSnapshotRepository(session)

    async def create(self, payload: LeadCreate, *, actor_id: uuid.UUID) -> Lead:
        """Create a lead at stage NEW and write its creation-history row.

        Validates that ``assigned_to_user_id`` and any supplied
        ``customer_id`` / ``item_id`` exist (404 otherwise) before touching
        the DB.
        """
        await self._validate_refs(
            assigned_to_user_id=payload.assigned_to_user_id,
            customer_id=payload.customer_id,
            item_id=payload.item_id,
        )

        lead_number = await self._leads.next_lead_number()
        lead = Lead(
            lead_number=lead_number,
            stage=LeadStage.NEW,
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
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )

        try:
            lead = await self._leads.add(lead)
            await self._leads.add_stage_history(
                LeadStageHistory(
                    lead_id=lead.id,
                    from_stage=None,
                    to_stage=LeadStage.NEW,
                    changed_by_user_id=actor_id,
                )
            )
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                "Database constraint violation creating lead",
                code="LEAD_CONSTRAINT_VIOLATION",
            ) from exc

        await self._session.refresh(lead)
        logger.info(
            "lead_created",
            extra={
                "lead_id": str(lead.id),
                "lead_number": lead.lead_number,
                "source": lead.source.value,
                "assigned_to_user_id": str(lead.assigned_to_user_id),
            },
        )
        # Compute the initial score snapshot (§4.7 — on create).
        await self._scorer.score_lead(lead)
        return lead

    async def get(self, lead_id: uuid.UUID) -> Lead:
        lead = await self._leads.get_by_id(lead_id)
        if lead is None:
            raise NotFoundError("Lead not found", code="LEAD_NOT_FOUND")
        return lead

    async def get_with_history(self, lead_id: uuid.UUID) -> tuple[Lead, list[LeadStageHistory]]:
        """Return a lead plus its stage history (newest first) for the
        detail view."""
        lead = await self.get(lead_id)
        history = await self._leads.list_stage_history(lead_id)
        return lead, history

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        stage: LeadStage | None = None,
        source: LeadSource | None = None,
        assigned_to_user_id: uuid.UUID | None = None,
        state: str | None = None,
        district: str | None = None,
        created_from: date | None = None,
        created_to: date | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Lead], int]:
        return await self._leads.list_(
            limit=limit,
            offset=offset,
            stage=stage,
            source=source,
            assigned_to_user_id=assigned_to_user_id,
            state=state,
            district=district,
            created_from=created_from,
            created_to=created_to,
            is_active=is_active,
        )

    async def update(
        self,
        lead_id: uuid.UUID,
        payload: LeadUpdate,
        *,
        actor_id: uuid.UUID,
    ) -> Lead:
        """Apply a partial update. ``stage`` is not updatable here (see
        :meth:`transition`). Re-validates any changed FK reference."""
        lead = await self.get(lead_id)
        updates = payload.model_dump(exclude_unset=True)

        await self._validate_refs(
            assigned_to_user_id=updates.get("assigned_to_user_id"),
            customer_id=updates.get("customer_id"),
            item_id=updates.get("item_id"),
        )

        for field, value in updates.items():
            setattr(lead, field, value)
        lead.updated_by_user_id = actor_id

        await self._session.commit()
        await self._session.refresh(lead)
        logger.info(
            "lead_updated",
            extra={"lead_id": str(lead.id), "fields": sorted(updates.keys())},
        )
        # Recompute the score only when a scoring input actually changed (§4.7).
        if set(updates) & LEAD_SCORING_INPUT_FIELDS:
            await self._scorer.score_lead(lead)
        return lead

    async def transition(
        self,
        lead_id: uuid.UUID,
        payload: StageTransitionRequest,
        *,
        actor_id: uuid.UUID,
    ) -> Lead:
        """Move a lead to ``payload.to_stage`` if the move is legal.

        Validates against :data:`LEAD_STAGE_TRANSITIONS` (409
        ``INVALID_STAGE_TRANSITION`` otherwise), stamps WON/LOST terminal
        fields, appends a history row, and commits — atomically. The
        schema has already guaranteed WON carries a ``won_value`` and LOST
        a ``lost_reason``.
        """
        lead = await self.get(lead_id)
        allowed = LEAD_STAGE_TRANSITIONS[lead.stage]
        if payload.to_stage not in allowed:
            raise ConflictError(
                f"Cannot transition a lead from {lead.stage.value} to {payload.to_stage.value}",
                code="INVALID_STAGE_TRANSITION",
            )

        from_stage = lead.stage
        now = datetime.now(UTC)
        lead.stage = payload.to_stage
        if payload.to_stage == LeadStage.WON:
            lead.won_value = payload.won_value
            lead.won_at = now
        elif payload.to_stage == LeadStage.LOST:
            lead.lost_at = now
            lead.lost_reason = payload.lost_reason
        lead.updated_by_user_id = actor_id

        await self._leads.add_stage_history(
            LeadStageHistory(
                lead_id=lead.id,
                from_stage=from_stage,
                to_stage=payload.to_stage,
                changed_by_user_id=actor_id,
                remark=payload.remark,
            )
        )
        await self._session.commit()
        await self._session.refresh(lead)
        logger.info(
            "lead_transitioned",
            extra={
                "lead_id": str(lead.id),
                "from_stage": from_stage.value,
                "to_stage": payload.to_stage.value,
                "actor_id": str(actor_id),
            },
        )
        # Recompute the score after a stage change (§4.7).
        await self._scorer.score_lead(lead)
        return lead

    async def latest_score(self, lead_id: uuid.UUID) -> LeadScore | None:
        """Latest score snapshot for a lead (None if never scored)."""
        return await self._snapshots.latest_lead_score(lead_id)

    async def latest_scores_map(self, lead_ids: list[uuid.UUID]) -> dict[uuid.UUID, LeadScore]:
        """Latest score per lead for a page of leads (no N+1)."""
        return await self._snapshots.latest_lead_scores_map(lead_ids)

    async def soft_delete(self, lead_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        """Deactivate a lead (``is_active = false``). Idempotent."""
        lead = await self.get(lead_id)
        if lead.is_active:
            lead.is_active = False
            lead.updated_by_user_id = actor_id
            await self._session.commit()
        logger.info("lead_deactivated", extra={"lead_id": str(lead.id)})

    async def _validate_refs(
        self,
        *,
        assigned_to_user_id: uuid.UUID | None,
        customer_id: uuid.UUID | None,
        item_id: uuid.UUID | None,
    ) -> None:
        """Reject references to non-existent users / customers / items (404).

        Each argument may be ``None`` (not supplied / not changed) — only
        present references are checked.
        """
        await self._require_exists(
            assigned_to_user_id,
            self._users.get_by_id,
            message="Assigned user not found",
            code="USER_NOT_FOUND",
        )
        await self._require_exists(
            customer_id,
            self._customers.get_by_id,
            message="Customer not found",
            code="CUSTOMER_NOT_FOUND",
        )
        await self._require_exists(
            item_id,
            self._items.get_by_id,
            message="Item not found",
            code="ITEM_NOT_FOUND",
        )

    @staticmethod
    async def _require_exists(
        entity_id: uuid.UUID | None,
        getter: Callable[[uuid.UUID], Awaitable[object | None]],
        *,
        message: str,
        code: str,
    ) -> None:
        """Raise :class:`NotFoundError` if a supplied id resolves to nothing.

        ``entity_id is None`` (not supplied / not changed) is a no-op.
        """
        if entity_id is not None and await getter(entity_id) is None:
            raise NotFoundError(message, code=code)
