"""Cross-reference between local entity ids and their Zoho record ids.

This is the only place the local↔Zoho link lives (Decision D-1 — no
``zoho_*`` columns on Backend tables). It serves both tracks:

* **Push (Track B):** one local row → one Zoho record (resolve ``local_id`` →
  ``zoho_id``).
* **Ingest (Track A):** one Zoho record → one local row, and the dedupe key on
  re-pull (resolve ``zoho_id`` → ``local_id``; an unmatched/parked record may
  have a null ``local_id``).

Both ``(entity_type, local_id)`` and ``(entity_type, zoho_id)`` are unique.
The Zoho-side uniqueness is what makes ingest idempotent on re-pull (CLAUDE.md
§19); it strengthens §10's plain ``(entity_type, zoho_id)`` index, which it
also satisfies. Both id columns are nullable, and Postgres treats NULLs as
distinct, so a push mid-flight (zoho_id not yet assigned) and a parked ingest
(local_id unresolved) never collide.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import Enum, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class MappingEntityType(StrEnum):
    """The kinds of entity that can be mapped local↔Zoho.

    Push entities (Track B) and ingest entities (Track A) share one table.
    """

    CUSTOMER = "CUSTOMER"
    VENDOR = "VENDOR"
    ITEM = "ITEM"
    SALES_ORDER = "SALES_ORDER"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    LEAD = "LEAD"
    ACTIVITY = "ACTIVITY"
    DEAL = "DEAL"
    USER = "USER"


class CrmMapping(Base, TimestampMixin):
    """A bridge row linking a local entity to its Zoho counterpart."""

    __tablename__ = "crm_mappings"
    __table_args__ = (
        UniqueConstraint("entity_type", "local_id", name="uq_crm_mappings_entity_local_id"),
        UniqueConstraint("entity_type", "zoho_id", name="uq_crm_mappings_entity_zoho_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[MappingEntityType] = mapped_column(
        Enum(
            MappingEntityType,
            name="mapping_entity_type",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    local_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zoho_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
