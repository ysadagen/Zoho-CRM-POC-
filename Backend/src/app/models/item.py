"""Item ORM model — raw materials and finished products in one table.

A single ``items`` table holds both kinds of inventory; the ``type``
enum distinguishes them. Stock is mutated **only** via stock-movement
flows (Phase 6+); direct edits via PATCH are deliberately disallowed
at the schema layer so the ``stock_movements`` ledger stays the
single source of truth for inventory changes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.finished_item_detail import FinishedItemDetail
from app.models.raw_item_detail import RawItemDetail


class ItemType(StrEnum):
    """Kind of inventory item."""

    RAW = "RAW"
    FINISHED = "FINISHED"


class StorageCondition(StrEnum):
    """Required storage environment for a product (pharma).

    A product-level property (the same for every lot of the item) — the
    *actual* shelf life of a physical lot is recorded on its ``batches``
    row via ``expiry_date``.
    """

    AMBIENT = "AMBIENT"
    COLD_CHAIN_2_8 = "COLD_CHAIN_2_8"
    FROZEN = "FROZEN"
    CONTROLLED = "CONTROLLED"


class Item(Base):
    """An inventoried item — either a raw material or a finished product."""

    __tablename__ = "items"
    __table_args__ = (
        # Last line of defence for the stock-never-negative invariant.
        # The schema layer (Pydantic) and the service layer (Phase 7/8
        # PO-receive / SO-create with FOR UPDATE) are the first two
        # lines; this CHECK guarantees no path can ever persist a
        # negative balance even via raw SQL or a buggy internal call.
        CheckConstraint(
            "stock_quantity >= 0",
            name="ck_items_stock_quantity_non_negative",
        ),
        # Same invariant applies to the reorder threshold — it would
        # never make sense as a negative number, and a NULL is allowed
        # to mean "no threshold configured".
        CheckConstraint(
            "reorder_threshold IS NULL OR reorder_threshold >= 0",
            name="ck_items_reorder_threshold_non_negative",
        ),
        # Currency cannot be negative either.
        CheckConstraint(
            "unit_price >= 0",
            name="ck_items_unit_price_non_negative",
        ),
        # Shelf life is a span of days; NULL means "not configured".
        CheckConstraint(
            "shelf_life_days IS NULL OR shelf_life_days >= 0",
            name="ck_items_shelf_life_days_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    sku: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[ItemType] = mapped_column(
        Enum(ItemType, name="item_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    unit_of_measure: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Decimal because inventory mixes whole-unit (pcs, rolls) and
    # fractional (kg, L) items. Numeric(20, 4) is generous for both
    # without ever losing precision to float rounding.
    stock_quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    reorder_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 4),
        nullable=True,
    )
    # Currency value; 2 decimal places is enough for INR-style pricing
    # (no fractional paise).
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Common-pharma attributes shared by RAW and FINISHED. Nullable so
    # pre-pharma rows (and create calls that omit them) stay valid; the
    # subtype-specific attributes live in raw_item_details /
    # finished_item_details, and per-lot expiry lives on batches.
    storage_condition: Mapped[StorageCondition | None] = mapped_column(
        Enum(
            StorageCondition,
            name="storage_condition",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    shelf_life_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # Audit attribution. ON DELETE RESTRICT because losing the
    # "who created this" trail on user deletion would defeat the
    # point of the audit field. Phase 1 has no user-delete flow
    # so this is never invoked in practice.
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

    # Subtype detail (Class-Table Inheritance) — exactly one is populated,
    # matching ``type``. ``lazy="selectin"`` eager-loads both on every item
    # query so reads never trigger lazy I/O (MissingGreenlet) and avoid N+1;
    # ``delete-orphan`` ties the detail's lifecycle to the parent item.
    raw_detail: Mapped[RawItemDetail | None] = relationship(
        "RawItemDetail",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    finished_detail: Mapped[FinishedItemDetail | None] = relationship(
        "FinishedItemDetail",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan",
    )
