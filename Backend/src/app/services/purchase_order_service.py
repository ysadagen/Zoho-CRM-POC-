"""Purchase-order business logic.

The headline operation is :meth:`PurchaseOrderService.receive_po`,
which is the **only** legal way to transition a PO out of DRAFT.
``receive_po`` composes :class:`StockMovementService.record_movement`
from Phase 6 inside one outer transaction:

1. ``SELECT ... FOR UPDATE`` the PO row (idempotency lock).
2. If the PO isn't in DRAFT, raise 409 ``PO_NOT_DRAFT``.
3. For each line, in ``item_id``-sorted order (deadlock avoidance
   when two POs share items), call ``record_movement`` with
   ``direction=IN, reason=PURCHASE, reference_type='PURCHASE_ORDER',
   reference_id=po.id``. ``record_movement`` locks the item row, mutates
   ``items.stock_quantity``, and inserts the ledger row in the SAME
   session — no separate commits.
4. Flip ``status=RECEIVED``, stamp ``received_date=today`` and
   ``updated_by_user_id``.
5. Commit once. Refresh per CLAUDE.md §10.1 so ``updated_at`` is fresh.

Any failure mid-loop aborts the whole transaction: no partial stock,
no partial ledger.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.batch import Batch
from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
)
from app.models.stock_movement import (
    REFERENCE_TYPE_PURCHASE_ORDER,
    MovementDirection,
    MovementReason,
)
from app.models.vendor_item_term import VendorItemTerm
from app.repositories.batch_repo import BatchRepository
from app.repositories.item_repo import ItemRepository
from app.repositories.purchase_order_repo import PurchaseOrderRepository
from app.repositories.vendor_repo import VendorRepository
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderReceive,
    PurchaseOrderReceiveLine,
)
from app.services.stock_movement_service import StockMovementService

logger = logging.getLogger(__name__)

_MONEY = Decimal("0.01")


class PurchaseOrderService:
    """Orchestrates PO create / read / receive flows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._pos = PurchaseOrderRepository(session)
        self._vendors = VendorRepository(session)
        self._items = ItemRepository(session)
        self._batches = BatchRepository(session)
        self._movements = StockMovementService(session)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_po(
        self,
        payload: PurchaseOrderCreate,
        *,
        actor_id: uuid.UUID,
    ) -> PurchaseOrder:
        """Create a DRAFT purchase order with its line items.

        Validates: vendor exists & is active, every line's item exists
        & is active, no duplicate items in the payload, every line has
        either an explicit ``unit_price`` or an active
        ``vendor_item_term`` to source one from.
        """
        vendor = await self._vendors.get_by_id(payload.vendor_id)
        if vendor is None or not vendor.is_active:
            raise NotFoundError("Vendor not found", code="VENDOR_NOT_FOUND")

        # Reject duplicate item_ids early — the UNIQUE constraint on
        # (purchase_order_id, item_id) is the DB-side backstop.
        duplicates = [
            item_id
            for item_id, count in Counter(line.item_id for line in payload.items).items()
            if count > 1
        ]
        if duplicates:
            raise ConflictError(
                f"Duplicate item_id in payload: {duplicates[0]}",
                code="DUPLICATE_LINE_ITEM",
            )

        resolved_lines: list[PurchaseOrderItem] = []
        subtotal = Decimal("0.00")
        for line in payload.items:
            item = await self._items.get_by_id(line.item_id)
            if item is None or not item.is_active:
                raise NotFoundError(
                    f"Item not found: {line.item_id}",
                    code="ITEM_NOT_FOUND",
                )

            unit_price = line.unit_price
            if unit_price is None:
                unit_price = await self._lookup_effective_price(
                    vendor_id=payload.vendor_id,
                    item_id=line.item_id,
                )
                if unit_price is None:
                    raise ValidationError(
                        f"No unit_price given and no active vendor term for item {line.item_id}",
                        code="PRICE_UNAVAILABLE",
                    )

            line_total = (line.quantity * unit_price).quantize(_MONEY, rounding=ROUND_HALF_UP)
            subtotal += line_total

            resolved_lines.append(
                PurchaseOrderItem(
                    item_id=line.item_id,
                    quantity=line.quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )

        po_number = await self._pos.next_po_number()
        po = PurchaseOrder(
            po_number=po_number,
            vendor_id=payload.vendor_id,
            expected_delivery_date=payload.expected_delivery_date,
            status=PurchaseOrderStatus.DRAFT,
            subtotal=subtotal,
            total=subtotal,  # Phase 1: no tax/header discount
            notes=payload.notes,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
            items=resolved_lines,
        )

        try:
            po = await self._pos.add(po)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            # Most likely cause: race producing a duplicate po_number
            # (vanishingly small with a sequence but defensive) or a
            # CHECK violation we missed in service-layer validation.
            raise ConflictError(
                "Database constraint violation creating purchase order",
                code="DUPLICATE_PURCHASE_ORDER",
            ) from exc

        await self._session.refresh(po)
        logger.info(
            "purchase_order_created",
            extra={
                "po_id": str(po.id),
                "po_number": po.po_number,
                "vendor_id": str(po.vendor_id),
                "line_count": len(resolved_lines),
                "subtotal": str(subtotal),
            },
        )
        return po

    async def _lookup_effective_price(
        self,
        *,
        vendor_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> Decimal | None:
        """Return the effective unit price from the most recent active term.

        ``effective_from <= today`` and either ``effective_to IS NULL``
        or ``effective_to >= today``. The newest matching row wins,
        ranked by ``effective_from DESC``. Returns ``None`` when no
        term applies; the caller turns that into 422 ``PRICE_UNAVAILABLE``.

        The effective price is ``rate * (1 - discount_percent / 100)``
        quantized to 2 dp HALF_UP — the price the vendor actually
        charges after their standing discount.
        """
        today = date.today()
        stmt = (
            select(VendorItemTerm)
            .where(
                VendorItemTerm.vendor_id == vendor_id,
                VendorItemTerm.item_id == item_id,
                VendorItemTerm.is_active.is_(True),
                VendorItemTerm.effective_from <= today,
            )
            .order_by(VendorItemTerm.effective_from.desc())
        )
        result = await self._session.execute(stmt)
        for term in result.scalars():
            if term.effective_to is None or term.effective_to >= today:
                effective = term.rate * (Decimal("1") - term.discount_percent / Decimal("100"))
                return effective.quantize(_MONEY, rounding=ROUND_HALF_UP)
        return None

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_po(self, po_id: uuid.UUID) -> PurchaseOrder:
        po = await self._pos.get_by_id(po_id)
        if po is None:
            raise NotFoundError(
                "Purchase order not found",
                code="PURCHASE_ORDER_NOT_FOUND",
            )
        return po

    async def list_pos(
        self,
        *,
        limit: int,
        offset: int,
        vendor_id: uuid.UUID | None = None,
        status: PurchaseOrderStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[PurchaseOrder], int]:
        return await self._pos.list_(
            limit=limit,
            offset=offset,
            vendor_id=vendor_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )

    # ------------------------------------------------------------------
    # Receive — the keystone
    # ------------------------------------------------------------------

    async def receive_po(
        self,
        po_id: uuid.UUID,
        payload: PurchaseOrderReceive,
        *,
        actor_id: uuid.UUID,
    ) -> PurchaseOrder:
        """Transition DRAFT → RECEIVED, creating a lot per line.

        Behaviour, in this exact order:

        1. ``SELECT ... FOR UPDATE`` the PO (idempotency lock).
        2. 404 if missing; 409 ``PO_NOT_DRAFT`` if status != DRAFT.
        3. Validate the batch entries cover **exactly** the PO's lines
           (one per line, matched by ``item_id``) → 422 otherwise.
        4. Pre-check each batch number is free for its item → 409
           ``DUPLICATE_BATCH`` otherwise.
        5. For each line (ordered by ``item_id`` for deadlock safety):
           create a ``batches`` row (quantity = line quantity, cost = line
           unit price, provenance = this PO + its vendor) and call
           ``record_movement(IN, PURCHASE, batch_id=<new lot>, ...)`` —
           which locks the item, bumps ``stock_quantity`` and inserts the
           ledger row.
        6. Update PO header. Single commit. Refresh.

        Any failure aborts the whole transaction — no partial stock, no
        partial lots, no partial ledger.
        """
        po = await self._pos.get_by_id_for_update(po_id)
        if po is None:
            raise NotFoundError(
                "Purchase order not found",
                code="PURCHASE_ORDER_NOT_FOUND",
            )
        if po.status != PurchaseOrderStatus.DRAFT:
            raise ConflictError(
                f"Purchase order is in status {po.status.value}, only DRAFT POs can be received",
                code="PO_NOT_DRAFT",
            )

        entries = self._batch_entries_by_item(payload, po)

        # Fail fast on a duplicate lot number before writing anything.
        for line in po.items:
            entry = entries[line.item_id]
            existing = await self._batches.get_by_item_and_number(line.item_id, entry.batch_number)
            if existing is not None:
                raise ConflictError(
                    f"Batch '{entry.batch_number}' already exists for item {line.item_id}",
                    code="DUPLICATE_BATCH",
                )

        # Deterministic lock ordering: two POs that share items will
        # always lock them in the same sequence and cannot deadlock.
        lines_sorted = sorted(po.items, key=lambda li: li.item_id)
        remarks = f"PO {po.po_number}"
        today = date.today()
        try:
            for line in lines_sorted:
                entry = entries[line.item_id]
                batch = await self._batches.add(
                    Batch(
                        item_id=line.item_id,
                        batch_number=entry.batch_number,
                        expiry_date=entry.expiry_date,
                        manufacturing_date=entry.manufacturing_date,
                        storage_location=entry.storage_location,
                        quantity=line.quantity,
                        initial_quantity=line.quantity,
                        unit_cost=line.unit_price,
                        vendor_id=po.vendor_id,
                        received_via_po_id=po.id,
                        batch_received_date=today,
                        created_by_user_id=actor_id,
                        updated_by_user_id=actor_id,
                    )
                )
                await self._movements.record_movement(
                    item_id=line.item_id,
                    direction=MovementDirection.IN,
                    reason=MovementReason.PURCHASE,
                    quantity=line.quantity,
                    actor_id=actor_id,
                    reference_type=REFERENCE_TYPE_PURCHASE_ORDER,
                    reference_id=po.id,
                    remarks=remarks,
                    batch_id=batch.id,
                )

            po.status = PurchaseOrderStatus.RECEIVED
            po.received_date = today
            po.updated_by_user_id = actor_id
            await self._session.commit()
        except IntegrityError as exc:
            # Race backstop for the unique (item_id, batch_number) constraint.
            await self._session.rollback()
            raise ConflictError(
                "A lot with that batch number already exists for one of the items",
                code="DUPLICATE_BATCH",
            ) from exc

        # CLAUDE.md §10.1 — server-onupdate ``updated_at`` needs a
        # refresh before Pydantic touches the instance.
        await self._session.refresh(po)
        logger.info(
            "purchase_order_received",
            extra={
                "po_id": str(po.id),
                "po_number": po.po_number,
                "line_count": len(lines_sorted),
                "batches_created": len(lines_sorted),
                "actor_id": str(actor_id),
            },
        )
        return po

    @staticmethod
    def _batch_entries_by_item(
        payload: PurchaseOrderReceive,
        po: PurchaseOrder,
    ) -> dict[uuid.UUID, PurchaseOrderReceiveLine]:
        """Map each batch entry to its PO line by ``item_id``.

        Requires the entries to cover exactly the PO's lines — no missing
        line, no entry for an item not on the PO, no duplicates. Raises
        422 ``RECEIVE_LINES_MISMATCH`` otherwise.
        """
        entries: dict[uuid.UUID, PurchaseOrderReceiveLine] = {}
        for entry in payload.lines:
            if entry.item_id in entries:
                raise ValidationError(
                    f"Duplicate batch entry for item {entry.item_id}",
                    code="RECEIVE_LINES_MISMATCH",
                )
            entries[entry.item_id] = entry

        po_item_ids = {line.item_id for line in po.items}
        if set(entries) != po_item_ids:
            missing = po_item_ids - set(entries)
            extra = set(entries) - po_item_ids
            raise ValidationError(
                "Receive must provide one batch per PO line "
                f"(missing: {sorted(map(str, missing))}, "
                f"unexpected: {sorted(map(str, extra))})",
                code="RECEIVE_LINES_MISMATCH",
            )
        return entries
