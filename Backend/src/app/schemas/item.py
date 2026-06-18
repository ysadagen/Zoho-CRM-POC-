"""Item-related Pydantic schemas.

Notable design choices:

- ``ItemCreate`` accepts ``stock_quantity`` (initial stock at creation
  time) but ``ItemUpdate`` does **not**. Once an item exists, every
  quantity change must go through the stock-movement ledger (Phase 6+).
- ``ItemUpdate`` is ``extra="forbid"`` so a client sending
  ``stock_quantity`` — or a typo like ``categry`` — gets a clean 422
  instead of a silent no-op.
- ``status`` is a **computed** field on ``ItemRead``. Never stored —
  derived state always drifts otherwise.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.item import ItemType, StorageCondition
from app.schemas.finished_item_detail import FinishedItemDetailIn, FinishedItemDetailRead
from app.schemas.raw_item_detail import RawItemDetailIn, RawItemDetailRead

__all__ = [
    "ItemCreate",
    "ItemCreated",
    "ItemList",
    "ItemRead",
    "ItemStatus",
    "ItemType",
    "ItemUpdate",
    "StorageCondition",
]


class ItemStatus(StrEnum):
    """Stock-level health, derived from quantity vs threshold.

    ``NO_STOCK`` is deliberately neutral (vs the more common
    "OUT_OF_STOCK"): we don't track whether stock ever existed, so the
    label shouldn't imply history. A brand-new item with zero stock and
    a sold-out item with zero stock are indistinguishable to this enum.
    """

    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"
    NO_STOCK = "NO_STOCK"


class ItemCreate(BaseModel):
    """Payload to create a new item.

    ``str_strip_whitespace`` normalises every incoming string field —
    " ITM-0001 " becomes "ITM-0001" so trailing-space typos don't
    create phantom-duplicate SKUs the UI can't distinguish.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    type: ItemType
    category: str = Field(min_length=1, max_length=64)
    unit_of_measure: str = Field(min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=1000)
    stock_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    reorder_threshold: Decimal | None = Field(default=None, ge=0)
    unit_price: Decimal = Field(ge=0)
    storage_condition: StorageCondition | None = None
    shelf_life_days: int | None = Field(default=None, ge=0)
    # Subtype detail — at most the block matching ``type`` (the service
    # rejects a mismatched block with 422 ITEM_DETAIL_TYPE_MISMATCH).
    raw_detail: RawItemDetailIn | None = None
    finished_detail: FinishedItemDetailIn | None = None


class ItemUpdate(BaseModel):
    """Partial update for an existing item.

    Every field is optional — omitted keys are left untouched.
    ``sku`` and ``type`` are deliberately not updatable; they're
    identity-shaped fields. ``stock_quantity`` is not updatable here;
    use the stock-movement endpoints in Phase 6+.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=64)
    unit_of_measure: str | None = Field(default=None, min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=1000)
    reorder_threshold: Decimal | None = Field(default=None, ge=0)
    unit_price: Decimal | None = Field(default=None, ge=0)
    storage_condition: StorageCondition | None = None
    shelf_life_days: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    # Partial-patch the matching subtype block; a mismatched block → 422.
    raw_detail: RawItemDetailIn | None = None
    finished_detail: FinishedItemDetailIn | None = None


class ItemRead(BaseModel):
    """Item as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    name: str
    type: ItemType
    category: str
    unit_of_measure: str
    description: str | None
    stock_quantity: Decimal
    reorder_threshold: Decimal | None
    unit_price: Decimal
    storage_condition: StorageCondition | None
    shelf_life_days: int | None
    is_active: bool
    created_by_user_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    # Exactly one is populated, matching ``type`` (the other is null).
    raw_detail: RawItemDetailRead | None = None
    finished_detail: FinishedItemDetailRead | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> ItemStatus:
        """Derived stock health — never stored."""
        if self.stock_quantity <= 0:
            return ItemStatus.NO_STOCK
        if self.reorder_threshold is not None and self.stock_quantity < self.reorder_threshold:
            return ItemStatus.LOW_STOCK
        return ItemStatus.IN_STOCK


class ItemList(BaseModel):
    """Paginated envelope for ``GET /items``.

    Shape mandated by ``CLAUDE.md §6``: ``{items, total, limit, offset}``.
    """

    items: list[ItemRead]
    total: int
    limit: int
    offset: int


class ItemCreated(BaseModel):
    """Minimal envelope returned by ``POST /items``.

    **Project-explicit deviation from the REST convention of returning
    the full resource on POST.** Rationale: the create response is
    primarily about confirming creation and enabling navigation. The
    full record (audit fields, stock figures, derived ``status``, etc.)
    is the consumer of ``GET /items/{id}``; including them all in the
    create response was noise the operator pointed out as unnecessary.

    Do NOT switch this back to :class:`ItemRead` without a deliberate
    project decision — the minimal shape is intentional.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    name: str
    created_at: datetime
