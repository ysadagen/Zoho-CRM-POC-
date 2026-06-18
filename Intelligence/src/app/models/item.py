"""Item read-model — the subset of the Backend ``items`` table the scoring
engines consume.

This service does not own or write items; it maps only the columns the
engines read (selling price, cost basis, type) plus the identity/audit columns
needed to materialise the table in the test schema. The pharma subtype detail
tables and per-lot batch wiring live in the Backend and are intentionally
absent here.
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
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ItemType(StrEnum):
    """Kind of inventory item."""

    RAW = "RAW"
    FINISHED = "FINISHED"


class Item(Base):
    """An inventoried item (read-only here)."""

    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="ck_items_stock_quantity_non_negative"),
        CheckConstraint("unit_price >= 0", name="ck_items_unit_price_non_negative"),
        CheckConstraint(
            "standard_cost IS NULL OR standard_cost >= 0",
            name="ck_items_standard_cost_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[ItemType] = mapped_column(
        Enum(ItemType, name="item_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    unit_of_measure: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    stock_quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Cost basis — drives lead product-margin and customer-health margin quality.
    standard_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
