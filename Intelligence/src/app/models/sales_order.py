"""Sales-order read-models — header + line items, the subset the scoring
engines consume (dispatch, revenue, realized margin).

Read-only here. The operator-chosen ``batch_id`` lot wiring lives in the
Backend and is intentionally absent (the engines never read it).
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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SalesOrderStatus(StrEnum):
    """Lifecycle states an SO can occupy."""

    DRAFT = "DRAFT"
    SHIPPED = "SHIPPED"


class SalesOrder(Base):
    """Header for a sales order placed by a customer (read-only here)."""

    __tablename__ = "sales_orders"
    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="ck_sales_orders_subtotal_non_negative"),
        CheckConstraint("total >= 0", name="ck_sales_orders_total_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    so_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    shipped_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[SalesOrderStatus] = mapped_column(
        Enum(
            SalesOrderStatus,
            name="sales_order_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        index=True,
        default=SalesOrderStatus.DRAFT,
        server_default=SalesOrderStatus.DRAFT.value,
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

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

    items: Mapped[list[SalesOrderItem]] = relationship(
        "SalesOrderItem", back_populates="sales_order", lazy="selectin"
    )


class SalesOrderItem(Base):
    """A single line on a sales order (read-only here)."""

    __tablename__ = "sales_order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sales_order_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_sales_order_items_unit_price_non_negative"),
        CheckConstraint("line_total >= 0", name="ck_sales_order_items_line_total_non_negative"),
        UniqueConstraint(
            "sales_order_id", "item_id", name="uq_sales_order_items_sales_order_id_item_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sales_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sales_order: Mapped[SalesOrder] = relationship("SalesOrder", back_populates="items")
