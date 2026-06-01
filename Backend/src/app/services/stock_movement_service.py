"""Stock-movement business logic — the architectural keystone.

:meth:`record_movement` is the **only** function in the codebase that
mutates ``items.stock_quantity``. Every quantity change — manual
adjustment, PO receive (Phase 7), SO create (Phase 8) — must go
through here. The contract:

1. Lock the target item row with ``SELECT ... FOR UPDATE`` so
   concurrent decrements serialize correctly.
2. Compute ``stock_after`` from the current stock + direction.
3. Reject OUT movements that would push stock below zero with a
   clean 409 ``INSUFFICIENT_STOCK`` (the DB CHECK is the backstop).
4. Update ``item.stock_quantity`` and insert the ledger row in the
   **same SQLAlchemy session**, so the caller's transaction makes
   them atomic.
5. **Do NOT commit.** The caller (Phase 7 PO service, Phase 8 SO
   service, Phase 6 adjustment endpoint) owns the transaction and
   may need to add more work to it before commit.

This pattern is what makes the rule "stock is mutated only via the
ledger" actually enforceable: there's exactly one place in the code
that writes ``item.stock_quantity``, and it always pairs with a
ledger insert.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.item import Item
from app.models.stock_movement import (
    MovementDirection,
    MovementReason,
    StockMovement,
)
from app.repositories.stock_movement_repo import StockMovementRepository
from app.schemas.stock_movement import AdjustmentCreate

logger = logging.getLogger(__name__)


class StockMovementService:
    """The append-only ledger service."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._movements = StockMovementRepository(session)

    async def record_movement(
        self,
        *,
        item_id: uuid.UUID,
        direction: MovementDirection,
        reason: MovementReason,
        quantity: Decimal,
        actor_id: uuid.UUID,
        reference_type: str | None = None,
        reference_id: uuid.UUID | None = None,
        remarks: str | None = None,
    ) -> StockMovement:
        """Atomically apply a stock change AND insert the ledger row.

        Caller is responsible for committing the transaction.

        Raises:
            NotFoundError: if ``item_id`` doesn't match a row.
            ConflictError: with code ``INSUFFICIENT_STOCK`` if an OUT
                movement would push stock below zero.
        """
        # SELECT ... FOR UPDATE — serializes concurrent decrements on
        # this item. Without it, two parallel SOs could both pass the
        # stock check and oversell.
        stmt = select(Item).where(Item.id == item_id).with_for_update()
        item = (await self._session.execute(stmt)).scalar_one_or_none()
        if item is None:
            raise NotFoundError("Item not found", code="ITEM_NOT_FOUND")

        stock_before: Decimal = item.stock_quantity
        if direction == MovementDirection.IN:
            stock_after = stock_before + quantity
        else:
            stock_after = stock_before - quantity
            if stock_after < 0:
                raise ConflictError(
                    f"Insufficient stock: {stock_before} available, {quantity} requested",
                    code="INSUFFICIENT_STOCK",
                )

        # Reference-pair consistency mirrors the DB CHECK. Surfaces
        # programmer errors at a clean error code rather than as an
        # IntegrityError from deep inside SQLAlchemy.
        if (reference_type is None) != (reference_id is None):
            raise ConflictError(
                "reference_type and reference_id must both be set or both be NULL",
                code="INVALID_REFERENCE_PAIR",
            )

        item.stock_quantity = stock_after

        movement = StockMovement(
            item_id=item_id,
            direction=direction,
            reason=reason,
            quantity=quantity,
            stock_before=stock_before,
            stock_after=stock_after,
            reference_type=reference_type,
            reference_id=reference_id,
            remarks=remarks,
            created_by_user_id=actor_id,
        )
        movement = await self._movements.add(movement)

        logger.info(
            "stock_movement_recorded",
            extra={
                "movement_id": str(movement.id),
                "item_id": str(item_id),
                "direction": direction.value,
                "reason": reason.value,
                "quantity": str(quantity),
                "stock_before": str(stock_before),
                "stock_after": str(stock_after),
            },
        )
        return movement

    async def record_adjustment(
        self,
        payload: AdjustmentCreate,
        *,
        actor_id: uuid.UUID,
    ) -> StockMovement:
        """Public adjustment entry point — called from the API route.

        Wraps :meth:`record_movement` with ``reason=ADJUSTMENT`` and
        commits, since the adjustment endpoint is a leaf operation
        (no other work in the same transaction).
        """
        movement = await self.record_movement(
            item_id=payload.item_id,
            direction=payload.direction,
            reason=MovementReason.ADJUSTMENT,
            quantity=payload.quantity,
            actor_id=actor_id,
            remarks=payload.remarks,
        )
        await self._session.commit()
        await self._session.refresh(movement)
        return movement

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        item_id: uuid.UUID | None = None,
        direction: MovementDirection | None = None,
        reason: MovementReason | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[StockMovement], int]:
        return await self._movements.list_(
            limit=limit,
            offset=offset,
            item_id=item_id,
            direction=direction,
            reason=reason,
            date_from=date_from,
            date_to=date_to,
        )
