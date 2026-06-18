"""RawItemDetail ORM model — RAW-specific attributes (1:1 with items).

Class-Table Inheritance: ``items`` holds the columns common to every
inventory item; this table holds the columns that only make sense for a
**raw material**. The primary key *is* the foreign key to ``items.id``,
which both enforces the 1:1 relationship and shares the parent's id.

``ON DELETE CASCADE`` (not RESTRICT like the transactional FKs) because a
detail row is a *part-of* extension of the item — if the parent item were
ever removed, its detail row should go with it. Phase 1 has no hard-delete
flow, so this is never invoked in practice.

The 1:1 invariant ("a RAW item has exactly one ``raw_item_details`` row
and no ``finished_item_details`` row") is maintained by
:class:`~app.services.item_service.ItemService` on create and by the
Phase-0 backfill migration for pre-existing rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MaterialClassification(StrEnum):
    """What kind of raw material this is."""

    API = "API"  # Active Pharmaceutical Ingredient
    EXCIPIENT = "EXCIPIENT"
    SOLVENT = "SOLVENT"
    REAGENT = "REAGENT"
    PACKAGING = "PACKAGING"


class Pharmacopoeia(StrEnum):
    """Standards body the material conforms to."""

    IP = "IP"
    BP = "BP"
    USP = "USP"
    EP = "EP"
    JP = "JP"
    NONE = "NONE"


class RawItemDetail(Base):
    """RAW-material-specific attributes for an item (1:1 with ``items``)."""

    __tablename__ = "raw_item_details"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # All subtype attributes are nullable: the Phase-0 backfill creates a
    # row per existing RAW item with these unset, to be filled in later.
    material_classification: Mapped[MaterialClassification | None] = mapped_column(
        Enum(
            MaterialClassification,
            name="material_classification",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    pharmacopoeia: Mapped[Pharmacopoeia | None] = mapped_column(
        Enum(
            Pharmacopoeia,
            name="pharmacopoeia",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    is_hazardous: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # Audit attribution per CLAUDE.md §10.2.
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
