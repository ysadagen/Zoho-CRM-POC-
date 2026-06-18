"""Read-only data access for the ``items`` table (item price/cost lookup)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item


class ItemRepository:
    """Read-only repository for :class:`Item`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, item_id: uuid.UUID) -> Item | None:
        stmt = select(Item).where(Item.id == item_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()
