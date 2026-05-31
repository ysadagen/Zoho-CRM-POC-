"""Item business logic — CRUD orchestration on top of :class:`ItemRepository`.

Services own transaction boundaries and raise domain exceptions. The
route layer never catches; the global :class:`AppError` handler maps
them to the JSON envelope.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.item import Item, ItemType
from app.repositories.item_repo import ItemRepository
from app.schemas.item import ItemCreate, ItemUpdate

logger = logging.getLogger(__name__)


class ItemService:
    """Orchestrates item flows on top of :class:`ItemRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._items = ItemRepository(session)

    async def create(self, payload: ItemCreate, *, actor_id: uuid.UUID) -> Item:
        """Create a new item.

        ``actor_id`` is the authenticated user creating the record;
        it populates both ``created_by_user_id`` and the initial
        ``updated_by_user_id``.

        Raises :class:`ConflictError` on duplicate SKU. The pre-check
        gives a clear error in the common case, and the
        ``IntegrityError`` catch covers the narrow race window where
        two concurrent requests both pass the pre-check.
        """
        existing = await self._items.get_by_sku(payload.sku)
        if existing is not None:
            raise ConflictError(
                "An item with that SKU already exists",
                code="SKU_ALREADY_EXISTS",
            )

        item = Item(
            sku=payload.sku,
            name=payload.name,
            type=payload.type,
            category=payload.category,
            unit_of_measure=payload.unit_of_measure,
            description=payload.description,
            stock_quantity=payload.stock_quantity,
            reorder_threshold=payload.reorder_threshold,
            unit_price=payload.unit_price,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        try:
            item = await self._items.add(item)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                "An item with that SKU already exists",
                code="SKU_ALREADY_EXISTS",
            ) from exc

        logger.info(
            "item_created",
            extra={
                "item_id": str(item.id),
                "sku": item.sku,
                "type": item.type.value,
            },
        )
        return item

    async def get(self, item_id: uuid.UUID) -> Item:
        """Return one item or raise :class:`NotFoundError`."""
        item = await self._items.get_by_id(item_id)
        if item is None:
            raise NotFoundError("Item not found", code="ITEM_NOT_FOUND")
        return item

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        item_type: ItemType | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> tuple[list[Item], int]:
        return await self._items.list_(
            limit=limit,
            offset=offset,
            item_type=item_type,
            category=category,
            search=search,
        )

    async def update(
        self,
        item_id: uuid.UUID,
        payload: ItemUpdate,
        *,
        actor_id: uuid.UUID,
    ) -> Item:
        """Apply a partial update to an existing item.

        Only fields the client actually sent (``exclude_unset=True``) are
        applied — omitted fields are preserved. ``sku``, ``type``, and
        ``stock_quantity`` are not in :class:`ItemUpdate` at all, so
        attempts to send them yield a 422 at the schema layer.

        ``updated_by_user_id`` is overwritten on every successful update
        so the audit trail records *who* most recently touched the row.
        """
        item = await self.get(item_id)
        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(item, field, value)
        item.updated_by_user_id = actor_id
        await self._session.commit()
        # ``updated_at`` is server-managed via ``onupdate=func.now()``; SQLAlchemy
        # marks it stale on UPDATE so it can fetch the new server value back.
        # Refresh explicitly here so the next attribute read (Pydantic's
        # model_validate in the route) doesn't trigger a sync I/O outside
        # async context (MissingGreenlet).
        await self._session.refresh(item)
        logger.info(
            "item_updated",
            extra={
                "item_id": str(item.id),
                "fields": sorted(updates.keys()),
            },
        )
        return item
