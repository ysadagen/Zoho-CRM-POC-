"""Local↔Zoho id resolution (ingest + push).

A thin orchestration wrapper over :class:`CrmMappingRepository` so services
ask "what local id does this Zoho record map to?" without touching SQL. For
ingest the mapping is also the dedupe key — an existing mapping means the
record was already brought across, so we update instead of re-creating.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm_mapping import MappingEntityType
from app.repositories.crm_mapping_repo import CrmMappingRepository


class MappingService:
    """Resolve and record local↔Zoho id mappings."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = CrmMappingRepository(session)

    async def local_for_zoho(self, entity_type: MappingEntityType, zoho_id: str) -> str | None:
        """Return the local id mapped to ``zoho_id``, or ``None`` if unseen."""
        mapping = await self._repo.get_by_zoho_id(entity_type, zoho_id)
        return mapping.local_id if mapping is not None else None

    async def record(
        self, entity_type: MappingEntityType, zoho_id: str, local_id: str
    ) -> None:
        """Persist (or refresh) the mapping ``zoho_id → local_id`` (flush only)."""
        await self._repo.upsert(entity_type=entity_type, zoho_id=zoho_id, local_id=local_id)

    async def zoho_for_local(
        self, entity_type: MappingEntityType, local_id: str
    ) -> str | None:
        """Return the Zoho id mapped to ``local_id``, or ``None`` if not yet pushed."""
        mapping = await self._repo.get_by_local_id(entity_type, local_id)
        return mapping.zoho_id if mapping is not None else None

    async def record_push(
        self, entity_type: MappingEntityType, local_id: str, zoho_id: str
    ) -> None:
        """Persist (or refresh) the mapping ``local_id → zoho_id`` (flush only)."""
        await self._repo.upsert_by_local_id(
            entity_type=entity_type, local_id=local_id, zoho_id=zoho_id
        )
