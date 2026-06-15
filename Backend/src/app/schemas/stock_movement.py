"""Stock-movement Pydantic schemas.

Only **one input schema** (``AdjustmentCreate``) — the only direct
write path through the API. PURCHASE and SALE movements arrive
internally via Phase 7/8 services calling
``StockMovementService.record_movement`` and don't need a request body
schema.

``StockMovementRead`` exposes a computed ``signed_quantity`` so the
UI can render ``+500`` / ``-120`` without doing the math itself.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.stock_movement import MovementDirection, MovementReason

__all__ = [
    "AdjustmentCreate",
    "MovementDirection",
    "MovementReason",
    "StockMovementList",
    "StockMovementRead",
]


class AdjustmentCreate(BaseModel):
    """Payload for ``POST /stock-movements/adjustments``.

    ``remarks`` is **required** — it's the accountability gate for a
    write that has no other paper trail (no PO, no SO). Empty or
    whitespace-only remarks fail with 422.

    ``batch_id`` is optional (#8). When given, the adjustment also moves
    that lot's quantity by the same amount, keeping the lot figures in
    step with the item total; when omitted, only the item aggregate moves.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    item_id: uuid.UUID
    direction: MovementDirection
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    remarks: str = Field(min_length=1, max_length=500)
    batch_id: uuid.UUID | None = None


class StockMovementRead(BaseModel):
    """A row of the ledger as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    direction: MovementDirection
    reason: MovementReason
    quantity: Decimal
    stock_before: Decimal
    stock_after: Decimal
    reference_type: str | None
    reference_id: uuid.UUID | None
    batch_id: uuid.UUID | None
    remarks: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def signed_quantity(self) -> Decimal:
        """``quantity`` with the direction's sign applied.

        Lets the UI render ``+500`` / ``-120`` without doing the math.
        Never stored — derived state only.
        """
        if self.direction == MovementDirection.OUT:
            return -self.quantity
        return self.quantity


class StockMovementList(BaseModel):
    """Paginated envelope for ``GET /stock-movements`` (CLAUDE.md §6)."""

    items: list[StockMovementRead]
    total: int
    limit: int
    offset: int
