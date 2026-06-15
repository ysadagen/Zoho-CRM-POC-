"""Data-access layer for the ``items`` table.

All SQL touching items is here. Services compose this repository;
routes never use it directly.

The repo deliberately exposes no ``update`` method. SQLAlchemy tracks
attribute changes on managed instances; the service mutates fields and
commits via the session. Adding an ``update`` would just duplicate that.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item, ItemType


class ItemRepository:
    """Repository for :class:`Item`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, item_id: uuid.UUID) -> Item | None:
        stmt = select(Item).where(Item.id == item_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_sku(self, sku: str) -> Item | None:
        stmt = select(Item).where(Item.sku == sku)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

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
        """Return ``(items_page, total_matching)``.

        ``total`` reflects the full count after filters but before
        pagination — that's what the UI needs to render pager controls.
        Soft-deleted items (``is_active = false``) are excluded unless
        ``include_inactive`` is set.
        """
        filtered: Select[tuple[Item]] = select(Item)
        if not include_inactive:
            filtered = filtered.where(Item.is_active.is_(True))
        if item_type is not None:
            filtered = filtered.where(Item.type == item_type)
        if category is not None:
            filtered = filtered.where(Item.category == category)
        if search:
            term = f"%{search.lower()}%"
            filtered = filtered.where(
                or_(func.lower(Item.sku).like(term), func.lower(Item.name).like(term))
            )

        # Count from the same filtered set, then page.
        count_stmt = select(func.count()).select_from(filtered.subquery())
        page_stmt = filtered.order_by(Item.created_at.desc()).limit(limit).offset(offset)

        total = (await self._session.execute(count_stmt)).scalar_one()
        page = list((await self._session.execute(page_stmt)).scalars().all())
        return page, int(total)

    async def add(self, item: Item) -> Item:
        """Persist a new item. Flush so server-side defaults populate."""
        self._session.add(item)
        await self._session.flush()
        await self._session.refresh(item)
        return item
