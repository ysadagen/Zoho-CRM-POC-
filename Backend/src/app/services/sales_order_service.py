"""Sales-order business logic — the OUT counterpart to Phase 7.

:meth:`SalesOrderService.ship_so` composes
:class:`StockMovementService.record_movement` (from Phase 6) in one
outer transaction. This is the first place the
``SELECT ... FOR UPDATE`` lock on the ``items`` row built in Phase 6
actually pays for itself — concurrent SOs trying to ship the same
item will serialise, and any line that would push stock below zero
raises 409 ``INSUFFICIENT_STOCK``, rolling back the *entire* receive
(including earlier lines that would have fit).

Atomicity guarantee:

1. ``SELECT ... FOR UPDATE`` the SO row (idempotency lock).
2. 404 if missing; 409 ``SO_NOT_DRAFT`` if status != DRAFT.
3. For each line, in ``item_id``-sorted order (deadlock avoidance
   when two SOs share items, and when SOs interleave with POs):
   ``record_movement(OUT, SALE, reference_type='SALES_ORDER',
   reference_id=so.id, quantity=line.quantity)``.
4. Flip ``status=SHIPPED``, stamp ``shipped_date=today`` and
   ``updated_by_user_id``.
5. Commit once. Refresh per CLAUDE.md §10.1.

Pricing in Phase 1 has no per-customer table; the create flow uses
either an explicit line ``unit_price`` or, when omitted, the item's
catalog ``unit_price``. The ``customers.is_privileged`` flag is
reserved for future use and is intentionally not wired to pricing yet.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.sales_order import SalesOrder, SalesOrderItem, SalesOrderStatus
from app.models.stock_movement import (
    REFERENCE_TYPE_SALES_ORDER,
    MovementDirection,
    MovementReason,
)
from app.repositories.customer_repo import CustomerRepository
from app.repositories.item_repo import ItemRepository
from app.repositories.sales_order_repo import SalesOrderRepository
from app.schemas.sales_order import SalesOrderCreate
from app.services.stock_movement_service import StockMovementService

logger = logging.getLogger(__name__)

_MONEY = Decimal("0.01")


class SalesOrderService:
    """Orchestrates SO create / read / ship flows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._sos = SalesOrderRepository(session)
        self._customers = CustomerRepository(session)
        self._items = ItemRepository(session)
        self._movements = StockMovementService(session)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_so(
        self,
        payload: SalesOrderCreate,
        *,
        actor_id: uuid.UUID,
    ) -> SalesOrder:
        """Create a DRAFT sales order with its line items.

        Validates: customer exists & is active, every line's item
        exists & is active, no duplicate items in the payload. Each
        line's ``unit_price`` defaults to ``items.unit_price`` when
        omitted. No stock pre-check at create time — that's enforced
        at ship.
        """
        customer = await self._customers.get_by_id(payload.customer_id)
        if customer is None or not customer.is_active:
            raise NotFoundError("Customer not found", code="CUSTOMER_NOT_FOUND")

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

        resolved_lines: list[SalesOrderItem] = []
        subtotal = Decimal("0.00")
        for line in payload.items:
            item = await self._items.get_by_id(line.item_id)
            if item is None or not item.is_active:
                raise NotFoundError(
                    f"Item not found: {line.item_id}",
                    code="ITEM_NOT_FOUND",
                )

            # Phase 1 pricing: explicit > item.unit_price. No
            # customer-specific pricing table exists yet.
            unit_price = line.unit_price if line.unit_price is not None else item.unit_price
            unit_price = unit_price.quantize(_MONEY, rounding=ROUND_HALF_UP)
            line_total = (line.quantity * unit_price).quantize(_MONEY, rounding=ROUND_HALF_UP)
            subtotal += line_total

            resolved_lines.append(
                SalesOrderItem(
                    item_id=line.item_id,
                    quantity=line.quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )

        so_number = await self._sos.next_so_number()
        so = SalesOrder(
            so_number=so_number,
            customer_id=payload.customer_id,
            expected_delivery_date=payload.expected_delivery_date,
            status=SalesOrderStatus.DRAFT,
            subtotal=subtotal,
            total=subtotal,
            notes=payload.notes,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
            items=resolved_lines,
        )

        try:
            so = await self._sos.add(so)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                "Database constraint violation creating sales order",
                code="DUPLICATE_SALES_ORDER",
            ) from exc

        await self._session.refresh(so)
        logger.info(
            "sales_order_created",
            extra={
                "so_id": str(so.id),
                "so_number": so.so_number,
                "customer_id": str(so.customer_id),
                "line_count": len(resolved_lines),
                "subtotal": str(subtotal),
            },
        )
        return so

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_so(self, so_id: uuid.UUID) -> SalesOrder:
        so = await self._sos.get_by_id(so_id)
        if so is None:
            raise NotFoundError(
                "Sales order not found",
                code="SALES_ORDER_NOT_FOUND",
            )
        return so

    async def list_sos(
        self,
        *,
        limit: int,
        offset: int,
        customer_id: uuid.UUID | None = None,
        status: SalesOrderStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[SalesOrder], int]:
        return await self._sos.list_(
            limit=limit,
            offset=offset,
            customer_id=customer_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )

    # ------------------------------------------------------------------
    # Ship — the keystone
    # ------------------------------------------------------------------

    async def ship_so(
        self,
        so_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
    ) -> SalesOrder:
        """Transition DRAFT → SHIPPED, atomically applying stock OUT.

        Behaviour:

        1. ``SELECT ... FOR UPDATE`` the SO (idempotency lock).
        2. 404 if missing; 409 ``SO_NOT_DRAFT`` if status != DRAFT.
        3. For each line (ordered by ``item_id``):
           ``record_movement(OUT, SALE, reference_type='SALES_ORDER',
           reference_id=so.id, quantity=line.quantity, remarks='SO {n}')``.
           ``record_movement`` raises 409 ``INSUFFICIENT_STOCK`` if
           a line would push stock below zero — that propagates and
           rolls back **all** prior lines plus the SO header change.
        4. Update SO header.
        5. Single commit. Refresh.
        """
        so = await self._sos.get_by_id_for_update(so_id)
        if so is None:
            raise NotFoundError(
                "Sales order not found",
                code="SALES_ORDER_NOT_FOUND",
            )
        if so.status != SalesOrderStatus.DRAFT:
            raise ConflictError(
                f"Sales order is in status {so.status.value}, only DRAFT SOs can be shipped",
                code="SO_NOT_DRAFT",
            )

        # Deterministic lock ordering — two SOs sharing items will
        # always lock them in the same sequence and cannot deadlock,
        # including against concurrent PO receives.
        lines_sorted = sorted(so.items, key=lambda li: li.item_id)
        remarks = f"SO {so.so_number}"

        # Atomicity guard: any failure between the first record_movement
        # flush and the final commit (typically INSUFFICIENT_STOCK from
        # a later line) must roll back **every** prior line's pending
        # writes — the SO must either ship completely or not at all.
        # We can't rely on the caller's session context manager to do
        # this; the service owns the contract.
        try:
            for line in lines_sorted:
                await self._movements.record_movement(
                    item_id=line.item_id,
                    direction=MovementDirection.OUT,
                    reason=MovementReason.SALE,
                    quantity=line.quantity,
                    actor_id=actor_id,
                    reference_type=REFERENCE_TYPE_SALES_ORDER,
                    reference_id=so.id,
                    remarks=remarks,
                )

            so.status = SalesOrderStatus.SHIPPED
            so.shipped_date = date.today()
            so.updated_by_user_id = actor_id

            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        # CLAUDE.md §10.1 — refresh after commit so server-onupdate
        # ``updated_at`` doesn't trip a sync attribute fetch.
        await self._session.refresh(so)
        logger.info(
            "sales_order_shipped",
            extra={
                "so_id": str(so.id),
                "so_number": so.so_number,
                "line_count": len(lines_sorted),
                "actor_id": str(actor_id),
            },
        )
        return so
