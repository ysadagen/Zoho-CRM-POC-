"""Batch ORM model — a physical lot of an item (1:N from items).

Pharma inventory is lot-governed: each receipt of a product is a distinct
**batch** with its own manufacturing/expiry dates and its own on-hand
quantity. ``items`` stays the *product* (stable SKU, referenced by POs,
SOs, movements, vendor terms); ``batches`` are the lots beneath it.

Stock model (Phase 0): ``items.stock_quantity`` remains the authoritative
aggregate; ``batches.quantity`` is the per-lot figure maintained alongside
it by the batch-aware flows added in later phases. The reconciliation
invariant is ``items.stock_quantity == Σ(batches.quantity)`` for
batch-tracked items.

DB-level invariants (CLAUDE.md §10.3 — the safety net below the service):

- ``quantity >= 0`` and ``initial_quantity >= 0``
- ``unit_cost`` NULL or ``>= 0``
- ``expiry_date >= manufacturing_date`` when a manufacturing date is set
- ``UNIQUE (item_id, batch_number)`` — a lot number is unique per product
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BatchStatus(StrEnum):
    """QC lifecycle state of a lot.

    ``QUARANTINE`` is the default on receipt — incoming stock is not
    sellable until quality control releases it. The full release
    *workflow* is a later phase; this column records the state now.
    """

    QUARANTINE = "QUARANTINE"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    RECALLED = "RECALLED"


class Batch(Base):
    """A single physical lot of an item."""

    __tablename__ = "batches"
    __table_args__ = (
        UniqueConstraint(
            "item_id",
            "batch_number",
            name="uq_batches_item_id_batch_number",
        ),
        CheckConstraint("quantity >= 0", name="ck_batches_quantity_non_negative"),
        CheckConstraint(
            "initial_quantity >= 0",
            name="ck_batches_initial_quantity_non_negative",
        ),
        CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="ck_batches_unit_cost_non_negative",
        ),
        CheckConstraint(
            "manufacturing_date IS NULL OR expiry_date >= manufacturing_date",
            name="ck_batches_expiry_after_manufacture",
        ),
        # FEFO selection: "lots of this item, earliest expiry first".
        Index("ix_batches_item_id_expiry_date", "item_id", "expiry_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    batch_number: Mapped[str] = mapped_column(String(64), nullable=False)
    batch_status: Mapped[BatchStatus] = mapped_column(
        Enum(
            BatchStatus,
            name="batch_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        index=True,
        default=BatchStatus.QUARANTINE,
        server_default=BatchStatus.QUARANTINE.value,
    )
    batch_received_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    manufacturing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Pharma must always know a lot's expiry — required, and indexed so the
    # "expiring in N days" report is cheap.
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    initial_quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    storage_location: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Provenance — nullable: an opening-balance lot may have neither a
    # supplier nor an originating PO recorded.
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    received_via_po_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
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
