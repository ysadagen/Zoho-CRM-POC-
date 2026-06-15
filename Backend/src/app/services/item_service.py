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

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.finished_item_detail import FinishedItemDetail
from app.models.item import Item, ItemType
from app.models.raw_item_detail import RawItemDetail
from app.repositories.item_repo import ItemRepository
from app.schemas.finished_item_detail import FinishedItemDetailIn
from app.schemas.item import ItemCreate, ItemUpdate
from app.schemas.raw_item_detail import RawItemDetailIn

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
        # Reject a detail block that doesn't match the item's type before
        # we touch the DB (single source of truth for this rule — §7 422).
        self._reject_mismatched_detail(
            payload.type, raw=payload.raw_detail, finished=payload.finished_detail
        )

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
            storage_condition=payload.storage_condition,
            shelf_life_days=payload.shelf_life_days,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        # Attach the matching 1:1 detail via the relationship so it cascades
        # on save and the invariant (every item owns exactly one detail row)
        # holds. Subtype attributes the client sent are applied; the rest
        # fall back to column defaults.
        if payload.type == ItemType.RAW:
            item.raw_detail = self._new_raw_detail(payload.raw_detail, actor_id=actor_id)
        else:
            item.finished_detail = self._new_finished_detail(
                payload.finished_detail, actor_id=actor_id
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

        detail_table = "raw_item_details" if item.type == ItemType.RAW else "finished_item_details"
        logger.info(
            "item_created",
            extra={
                "item_id": str(item.id),
                "sku": item.sku,
                "type": item.type.value,
                "detail_table": detail_table,
            },
        )
        return item

    @staticmethod
    def _reject_mismatched_detail(
        item_type: ItemType,
        *,
        raw: object | None,
        finished: object | None,
    ) -> None:
        """Raise 422 if a detail block doesn't match the item's type."""
        if item_type == ItemType.RAW and finished is not None:
            raise ValidationError(
                "finished_detail is not valid for a RAW item",
                code="ITEM_DETAIL_TYPE_MISMATCH",
            )
        if item_type == ItemType.FINISHED and raw is not None:
            raise ValidationError(
                "raw_detail is not valid for a FINISHED item",
                code="ITEM_DETAIL_TYPE_MISMATCH",
            )

    @staticmethod
    def _new_raw_detail(payload: RawItemDetailIn | None, *, actor_id: uuid.UUID) -> RawItemDetail:
        data = payload.model_dump(exclude_unset=True) if payload is not None else {}
        return RawItemDetail(created_by_user_id=actor_id, updated_by_user_id=actor_id, **data)

    @staticmethod
    def _new_finished_detail(
        payload: FinishedItemDetailIn | None, *, actor_id: uuid.UUID
    ) -> FinishedItemDetail:
        data = payload.model_dump(exclude_unset=True) if payload is not None else {}
        return FinishedItemDetail(created_by_user_id=actor_id, updated_by_user_id=actor_id, **data)

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
        include_inactive: bool = False,
    ) -> tuple[list[Item], int]:
        return await self._items.list_(
            limit=limit,
            offset=offset,
            item_type=item_type,
            category=category,
            search=search,
            include_inactive=include_inactive,
        )

    async def soft_delete(self, item_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        """Deactivate an item (soft delete) — sets ``is_active = false``.

        We never hard-delete: items are referenced by movements, POs, SOs and
        batches (all ``ON DELETE RESTRICT``), and that history must survive.
        A deactivated item drops out of the default item list and can no
        longer be added to new orders (create flows reject inactive items),
        while every past record that points at it stays intact. Idempotent —
        deactivating an already-inactive item is a no-op. 404 if unknown.
        """
        item = await self.get(item_id)
        if item.is_active:
            item.is_active = False
            item.updated_by_user_id = actor_id
            await self._session.commit()
        logger.info("item_deactivated", extra={"item_id": str(item.id), "sku": item.sku})

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
        attempts to send them yield a 422 at the schema layer. A subtype
        detail block (``raw_detail`` / ``finished_detail``) that doesn't
        match the item's type yields a 422 ``ITEM_DETAIL_TYPE_MISMATCH``.

        ``updated_by_user_id`` is overwritten on every successful update
        so the audit trail records *who* most recently touched the row.
        """
        item = await self.get(item_id)
        updates = payload.model_dump(exclude_unset=True)
        # Pull the nested detail patches out of the scalar update loop.
        raw_detail = updates.pop("raw_detail", None)
        finished_detail = updates.pop("finished_detail", None)
        self._reject_mismatched_detail(item.type, raw=raw_detail, finished=finished_detail)

        for field, value in updates.items():
            setattr(item, field, value)
        detail_patched = self._patch_detail(
            item, raw=raw_detail, finished=finished_detail, actor_id=actor_id
        )
        item.updated_by_user_id = actor_id
        await self._session.commit()
        logger.info(
            "item_updated",
            extra={
                "item_id": str(item.id),
                "fields": sorted(updates.keys()),
                "detail_patched": detail_patched,
            },
        )
        # Re-fetch through ``get`` so the response carries the server-managed
        # ``updated_at`` and the eager-loaded (selectin) detail relationship —
        # avoids a sync attribute fetch outside async context (MissingGreenlet).
        return await self.get(item_id)

    def _patch_detail(
        self,
        item: Item,
        *,
        raw: dict[str, object] | None,
        finished: dict[str, object] | None,
        actor_id: uuid.UUID,
    ) -> bool:
        """Apply the matching detail patch in place. Returns whether it ran.

        ``_reject_mismatched_detail`` has already guaranteed at most the
        block matching ``item.type`` is present.
        """
        if item.type == ItemType.RAW:
            data = raw
            if data is None:
                return False
            target: RawItemDetail | FinishedItemDetail | None = item.raw_detail
            if target is None:  # defensive — every item gets a detail row on create
                target = RawItemDetail(created_by_user_id=actor_id, updated_by_user_id=actor_id)
                item.raw_detail = target
        else:
            data = finished
            if data is None:
                return False
            target = item.finished_detail
            if target is None:
                target = FinishedItemDetail(
                    created_by_user_id=actor_id, updated_by_user_id=actor_id
                )
                item.finished_detail = target

        for field, value in data.items():
            setattr(target, field, value)
        target.updated_by_user_id = actor_id
        return True
