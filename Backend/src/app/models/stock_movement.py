"""Stock movement ORM model — the append-only audit ledger.

**Every** quantity change in the system writes a row here. No rows are
ever updated or deleted; corrections are made by inserting a new
movement that nets the previous one (typically an ``ADJUSTMENT`` with
opposite ``direction``).

Three DB-level CHECK constraints (CLAUDE.md §10.3) are the last line of
defence below the service layer:

1. ``quantity > 0`` — direction carries the sign; zero/negative is
   a foot-gun that should never reach storage.
2. ``stock_after >= 0`` — stock can never go negative, period.
3. **Reference consistency** — ``reference_type`` and ``reference_id``
   are both NULL or both NOT NULL; a dangling pair is meaningless.

The ``reference_type`` / ``reference_id`` pair is a **soft FK** — it
can point at ``purchase_orders``, ``sales_orders``, or future
references. We don't add a real FK because the target table varies.
For manual adjustments both fields are NULL and ``remarks`` carries
the audit explanation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MovementDirection(StrEnum):
    """Which way stock moved."""

    IN = "IN"
    OUT = "OUT"


class MovementReason(StrEnum):
    """Why the movement happened (business cause).

    PRODUCTION is intentionally not included — manufacturing flows are
    out of Phase 1 scope. Add as a new enum value when needed; the
    Alembic migration will need to ``ALTER TYPE ... ADD VALUE``.
    """

    PURCHASE = "PURCHASE"
    SALE = "SALE"
    ADJUSTMENT = "ADJUSTMENT"


# Constants for the soft-FK ``reference_type`` column. Code that writes
# a movement linked to a PO/SO uses these values to avoid string drift.
REFERENCE_TYPE_PURCHASE_ORDER = "PURCHASE_ORDER"
REFERENCE_TYPE_SALES_ORDER = "SALES_ORDER"


class StockMovement(Base):
    """A single row in the append-only stock ledger."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_stock_movements_quantity_positive"),
        CheckConstraint(
            "stock_after >= 0",
            name="ck_stock_movements_stock_after_non_negative",
        ),
        CheckConstraint(
            "(reference_type IS NULL AND reference_id IS NULL) "
            "OR (reference_type IS NOT NULL AND reference_id IS NOT NULL)",
            name="ck_stock_movements_reference_consistency",
        ),
        # The most common ledger query: "movements for this item, newest
        # first". One composite index serves both the filter and the sort.
        Index("ix_stock_movements_item_id_created_at", "item_id", "created_at"),
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
    direction: Mapped[MovementDirection] = mapped_column(
        Enum(
            MovementDirection,
            name="movement_direction",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        index=True,
    )
    reason: Mapped[MovementReason] = mapped_column(
        Enum(
            MovementReason,
            name="movement_reason",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    stock_before: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    stock_after: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)

    # Soft polymorphic reference. NOT a DB FK because the target table
    # varies (purchase_orders, sales_orders, …). Validity is enforced
    # by the reference-consistency CHECK constraint above + service-
    # layer rules in Phases 7/8.
    reference_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Append-only: no ``updated_at`` and no ``updated_by_user_id``.
    # The act of writing here is the only mutation; the row is then
    # immutable. Audit fields use the same RESTRICT FK pattern as the
    # rest of the codebase so a user with movements cannot be hard-
    # deleted (audit trail integrity).
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
