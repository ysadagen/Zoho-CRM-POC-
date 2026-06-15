"""Batch (lot) business logic.

Phase 1B is the **opening-balance** model: recording a lot associates
*existing* item stock with that lot and changes no totals — so it writes
no ``stock_movements`` row. The one rule it enforces is that you cannot
batch more than the item physically has unbatched:

    Σ(existing lot quantities) + new quantity  ≤  items.stock_quantity

To make that check correct under concurrency, ``create`` locks the item
row with ``SELECT ... FOR UPDATE`` before summing existing lots — mirroring
:class:`~app.services.stock_movement_service.StockMovementService`. New
stock entering inventory (which *does* move stock) is the PO-receive flow
in Phase 1C, not this service.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.batch import Batch, BatchStatus
from app.models.item import Item
from app.repositories.batch_repo import BatchRepository
from app.schemas.batch import BatchCreate

logger = logging.getLogger(__name__)

# QC lifecycle (#7). A lot is received into QUARANTINE; QC then RELEASES it
# (sellable) or REJECTS it (terminal). A RELEASED lot can later be RECALLED
# (terminal). REJECTED / RECALLED / EXPIRED are terminal — no transitions out.
# EXPIRED is system-derived (from expiry_date), not a manual transition.
_ALLOWED_TRANSITIONS: dict[BatchStatus, frozenset[BatchStatus]] = {
    BatchStatus.QUARANTINE: frozenset({BatchStatus.RELEASED, BatchStatus.REJECTED}),
    BatchStatus.RELEASED: frozenset({BatchStatus.RECALLED}),
    BatchStatus.REJECTED: frozenset(),
    BatchStatus.RECALLED: frozenset(),
    BatchStatus.EXPIRED: frozenset(),
}


class BatchService:
    """Orchestrates lot flows on top of :class:`BatchRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._batches = BatchRepository(session)

    async def create(self, payload: BatchCreate, *, actor_id: uuid.UUID) -> Batch:
        """Record an opening-balance lot for an item.

        Raises:
            NotFoundError: ``ITEM_NOT_FOUND`` if the item doesn't exist.
            ConflictError: ``DUPLICATE_BATCH`` if ``(item_id, batch_number)``
                already exists; ``BATCH_EXCEEDS_UNBATCHED_STOCK`` if the lot
                quantity exceeds the item's unbatched remainder.
        """
        # Lock the item row so concurrent lot creations for the same item
        # serialise and the unbatched-remainder check stays correct.
        stmt = select(Item).where(Item.id == payload.item_id).with_for_update()
        item = (await self._session.execute(stmt)).scalar_one_or_none()
        if item is None:
            raise NotFoundError("Item not found", code="ITEM_NOT_FOUND")

        existing = await self._batches.get_by_item_and_number(payload.item_id, payload.batch_number)
        if existing is not None:
            raise ConflictError(
                "A batch with that number already exists for this item",
                code="DUPLICATE_BATCH",
            )

        batched = await self._batches.sum_quantity_for_item(payload.item_id)
        unbatched = item.stock_quantity - batched
        if payload.quantity > unbatched:
            raise ConflictError(
                f"Lot quantity {payload.quantity} exceeds the item's unbatched stock {unbatched}",
                code="BATCH_EXCEEDS_UNBATCHED_STOCK",
            )

        batch = Batch(
            item_id=payload.item_id,
            batch_number=payload.batch_number,
            batch_status=payload.batch_status,
            batch_received_date=payload.batch_received_date,
            manufacturing_date=payload.manufacturing_date,
            expiry_date=payload.expiry_date,
            quantity=payload.quantity,
            initial_quantity=payload.quantity,
            unit_cost=payload.unit_cost,
            storage_location=payload.storage_location,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        try:
            batch = await self._batches.add(batch)
            await self._session.commit()
        except IntegrityError as exc:
            # Race backstop for the unique (item_id, batch_number) constraint.
            await self._session.rollback()
            raise ConflictError(
                "A batch with that number already exists for this item",
                code="DUPLICATE_BATCH",
            ) from exc

        logger.info(
            "batch_created",
            extra={
                "batch_id": str(batch.id),
                "item_id": str(batch.item_id),
                "batch_number": batch.batch_number,
                "quantity": str(batch.quantity),
                "status": batch.batch_status.value,
            },
        )
        return batch

    async def get(self, batch_id: uuid.UUID) -> Batch:
        """Return one lot or raise :class:`NotFoundError`."""
        batch = await self._batches.get_by_id(batch_id)
        if batch is None:
            raise NotFoundError("Batch not found", code="BATCH_NOT_FOUND")
        return batch

    async def change_status(
        self,
        batch_id: uuid.UUID,
        new_status: BatchStatus,
        *,
        actor_id: uuid.UUID,
    ) -> Batch:
        """Move a lot through its QC lifecycle (#7).

        Only the transitions in :data:`_ALLOWED_TRANSITIONS` are permitted:
        QUARANTINE → RELEASED / REJECTED, RELEASED → RECALLED. Anything else
        (including a no-op to the same status, or a move out of a terminal
        state) is a 409 ``INVALID_BATCH_TRANSITION``. 404 if the lot is unknown.

        REJECTED / RECALLED lots are no longer shippable (see
        :data:`~app.models.batch.SHIPPABLE_BATCH_STATUSES`), so a recall
        immediately removes remaining stock from FEFO and explicit lot picks.
        """
        batch = await self._batches.get_by_id_for_update(batch_id)
        if batch is None:
            raise NotFoundError("Batch not found", code="BATCH_NOT_FOUND")

        if new_status not in _ALLOWED_TRANSITIONS[batch.batch_status]:
            raise ConflictError(
                f"Cannot change lot status from {batch.batch_status.value} "
                f"to {new_status.value}",
                code="INVALID_BATCH_TRANSITION",
            )

        previous = batch.batch_status
        batch.batch_status = new_status
        batch.updated_by_user_id = actor_id
        await self._session.commit()
        await self._session.refresh(batch)
        logger.info(
            "batch_status_changed",
            extra={
                "batch_id": str(batch.id),
                "from_status": previous.value,
                "to_status": new_status.value,
                "actor_id": str(actor_id),
            },
        )
        return batch

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        item_id: uuid.UUID | None = None,
        status: BatchStatus | None = None,
        expiring_before: date | None = None,
    ) -> tuple[list[Batch], int]:
        return await self._batches.list_(
            limit=limit,
            offset=offset,
            item_id=item_id,
            status=status,
            expiring_before=expiring_before,
        )
