"""Data-access layer for ``crm_mappings`` — the local↔Zoho bridge.

For ingest the natural key is ``(entity_type, zoho_id)``: a re-pull resolves
the existing mapping and updates rather than inserting (idempotency, CLAUDE.md
§19). The reverse lookup ``(entity_type, local_id)`` backs push and the
Frontend reference badge.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm_mapping import CrmMapping, MappingEntityType


class CrmMappingRepository:
    """Read and upsert local↔Zoho id mappings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_zoho_id(
        self, entity_type: MappingEntityType, zoho_id: str
    ) -> CrmMapping | None:
        """Resolve a Zoho id → mapping (the ingest dedupe lookup)."""
        stmt = select(CrmMapping).where(
            CrmMapping.entity_type == entity_type,
            CrmMapping.zoho_id == zoho_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_local_id(
        self, entity_type: MappingEntityType, local_id: str
    ) -> CrmMapping | None:
        """Resolve a local id → mapping (the push dedup lookup)."""
        stmt = select(CrmMapping).where(
            CrmMapping.entity_type == entity_type,
            CrmMapping.local_id == local_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def upsert_by_local_id(
        self,
        *,
        entity_type: MappingEntityType,
        local_id: str,
        zoho_id: str,
    ) -> CrmMapping:
        """Create or update the mapping for ``(entity_type, local_id)``.

        Used by Track B push to record the Zoho id after a successful create/update.
        """
        mapping = await self.get_by_local_id(entity_type, local_id)
        if mapping is None:
            mapping = CrmMapping(entity_type=entity_type, local_id=local_id, zoho_id=zoho_id)
            self._session.add(mapping)
        else:
            mapping.zoho_id = zoho_id
        await self._session.flush()
        return mapping

    async def upsert(
        self,
        *,
        entity_type: MappingEntityType,
        zoho_id: str,
        local_id: str | None,
    ) -> CrmMapping:
        """Create or update the mapping for ``(entity_type, zoho_id)``.

        Flushes so the row is queryable within the transaction; the calling
        service owns the commit.
        """
        mapping = await self.get_by_zoho_id(entity_type, zoho_id)
        if mapping is None:
            mapping = CrmMapping(entity_type=entity_type, zoho_id=zoho_id, local_id=local_id)
            self._session.add(mapping)
        elif local_id is not None:
            mapping.local_id = local_id

        await self._session.flush()
        return mapping
