"""FinishedItemDetail ORM model — FINISHED-specific attributes (1:1).

Class-Table Inheritance sibling of :mod:`app.models.raw_item_detail`:
``items`` holds the common columns, this table the ones that only make
sense for a **finished pharmaceutical product** (dosage form, strength,
MRP, regulatory codes, …).

Same ownership semantics as ``raw_item_details``: PK == FK to
``items.id``, ``ON DELETE CASCADE`` (part-of relationship). Two DB CHECK
constraints guard the money columns (CLAUDE.md §10.3).
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


class DosageForm(StrEnum):
    """Physical form the finished product is dispensed in."""

    TABLET = "TABLET"
    CAPSULE = "CAPSULE"
    SYRUP = "SYRUP"
    SUSPENSION = "SUSPENSION"
    INJECTION = "INJECTION"
    OINTMENT = "OINTMENT"
    CREAM = "CREAM"
    GEL = "GEL"
    DROPS = "DROPS"
    POWDER = "POWDER"
    INHALER = "INHALER"
    OTHER = "OTHER"


class DrugSchedule(StrEnum):
    """Regulatory schedule (controlled-substance class).

    A minimal starter set — add values (``G``, ``C``, ``J``, …) via an
    additive ``ALTER TYPE ... ADD VALUE`` migration when needed.
    """

    NONE = "NONE"
    H = "H"
    H1 = "H1"
    X = "X"


class FinishedItemDetail(Base):
    """FINISHED-product-specific attributes for an item (1:1 with ``items``)."""

    __tablename__ = "finished_item_details"
    __table_args__ = (
        CheckConstraint(
            "selling_price IS NULL OR selling_price >= 0",
            name="ck_finished_item_details_selling_price_non_negative",
        ),
        CheckConstraint(
            "mrp IS NULL OR mrp >= 0",
            name="ck_finished_item_details_mrp_non_negative",
        ),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # All subtype attributes nullable for the same backfill reason as
    # raw_item_details.
    generic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    brand_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    strength: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dosage_form: Mapped[DosageForm | None] = mapped_column(
        Enum(
            DosageForm,
            name="dosage_form",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    pack_size: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ingredients: Mapped[str | None] = mapped_column(Text, nullable=True)
    container_specification: Mapped[str | None] = mapped_column(String(255), nullable=True)
    selling_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    registration_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    drug_schedule: Mapped[DrugSchedule | None] = mapped_column(
        Enum(
            DrugSchedule,
            name="drug_schedule",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    is_prescription_required: Mapped[bool] = mapped_column(
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
