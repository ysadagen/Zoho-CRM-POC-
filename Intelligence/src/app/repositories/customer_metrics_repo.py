"""Aggregate metric queries backing the customer-health and beat engines.

These are cross-table read-only aggregates (dispatch, revenue, realized
margin, DSO, AR exposure, activity recency/counts) that don't belong to a
single entity repository. Kept here so the scoring orchestrators stay free of
SQL. All windows are half-open ``[start, end)`` and relative to the
computation date, which the caller resolves.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer

# DISABLED — Invoice/Payment moving onto SalesOrder (see INVOICE_TO_SALES_ORDER_MIGRATION_PLAN.md)
# from app.models.invoice import Invoice, Payment
from app.models.item import Item
from app.models.lead import Lead
from app.models.sales_activity import ActivityType, SalesActivity
from app.models.sales_order import SalesOrder, SalesOrderItem, SalesOrderStatus


class CustomerMetricsRepository:
    """Read-only aggregate metrics for a customer, as of a date."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- dispatch / revenue / margin (SHIPPED sales orders) --------------

    async def dispatch_in_period(self, customer_id: uuid.UUID, start: date, end: date) -> Decimal:
        """Σ shipped quantity (dispatch) in ``[start, end)`` by ``shipped_date``."""
        stmt = (
            select(func.coalesce(func.sum(SalesOrderItem.quantity), 0))
            .select_from(SalesOrderItem)
            .join(SalesOrder, SalesOrder.id == SalesOrderItem.sales_order_id)
            .where(
                SalesOrder.customer_id == customer_id,
                SalesOrder.status == SalesOrderStatus.SHIPPED,
                SalesOrder.shipped_date >= start,
                SalesOrder.shipped_date < end,
            )
        )
        return Decimal((await self._session.execute(stmt)).scalar_one())

    async def revenue_in_period(self, customer_id: uuid.UUID, start: date, end: date) -> Decimal:
        """Σ shipped SO totals (revenue) in ``[start, end)`` by ``shipped_date``."""
        stmt = select(func.coalesce(func.sum(SalesOrder.total), 0)).where(
            SalesOrder.customer_id == customer_id,
            SalesOrder.status == SalesOrderStatus.SHIPPED,
            SalesOrder.shipped_date >= start,
            SalesOrder.shipped_date < end,
        )
        return Decimal((await self._session.execute(stmt)).scalar_one())

    async def realized_margin_pct(
        self, customer_id: uuid.UUID, start: date, end: date
    ) -> float | None:
        """Realized margin % over shipped lines (in window) whose item carries a
        ``standard_cost``: ``sum(line_total - qty*cost) / sum(line_total) * 100``.
        None when there are no costed shipped lines (-> default)."""
        stmt = (
            select(
                func.coalesce(func.sum(SalesOrderItem.line_total), 0),
                func.coalesce(func.sum(SalesOrderItem.quantity * Item.standard_cost), 0),
            )
            .select_from(SalesOrderItem)
            .join(SalesOrder, SalesOrder.id == SalesOrderItem.sales_order_id)
            .join(Item, Item.id == SalesOrderItem.item_id)
            .where(
                SalesOrder.customer_id == customer_id,
                SalesOrder.status == SalesOrderStatus.SHIPPED,
                SalesOrder.shipped_date >= start,
                SalesOrder.shipped_date < end,
                Item.standard_cost.is_not(None),
            )
        )
        line_total, cost_total = (await self._session.execute(stmt)).one()
        line_total = Decimal(line_total)
        if line_total == 0:
            return None
        return float(line_total - Decimal(cost_total)) / float(line_total) * 100

    async def last_shipped_date(self, customer_id: uuid.UUID) -> date | None:
        stmt = select(func.max(SalesOrder.shipped_date)).where(
            SalesOrder.customer_id == customer_id,
            SalesOrder.status == SalesOrderStatus.SHIPPED,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    # --- accounts receivable (DSO / overdue) -----------------------------

    async def dso_days(self, customer_id: uuid.UUID, *, since: date, as_of: date) -> float | None:
        """Average order-to-shipment days for SHIPPED orders in [since, as_of).

        Replaces invoice-based DSO (invoices removed). Faster fulfillment = lower
        value = healthier score. Returns None when no shipped orders exist so the
        scoring engine falls back to its configured default.
        """
        # PostgreSQL: DATE - DATE returns integer days directly.
        stmt = select(
            func.avg(cast(SalesOrder.shipped_date - SalesOrder.order_date, Float))
        ).where(
            SalesOrder.customer_id == customer_id,
            SalesOrder.status == SalesOrderStatus.SHIPPED,
            SalesOrder.shipped_date >= since,
            SalesOrder.shipped_date <= as_of,
        )
        result = (await self._session.execute(stmt)).scalar()
        return float(result) if result is not None else None

    async def outstanding_totals(
        self, customer_id: uuid.UUID, as_of: date
    ) -> tuple[Decimal, Decimal]:
        # DISABLED — Invoice/Payment removed; will be rewritten against SalesOrder.paid_amount/paid_date
        # per INVOICE_TO_SALES_ORDER_MIGRATION_PLAN.md. Returns zeros so scoring engine uses its default.
        #
        # paid = (
        #     select(
        #         Payment.invoice_id.label("invoice_id"),
        #         func.sum(Payment.amount).label("paid_sum"),
        #     )
        #     .group_by(Payment.invoice_id)
        #     .subquery()
        # )
        # outstanding = Invoice.amount - func.coalesce(paid.c.paid_sum, 0)
        # total_expr = func.coalesce(func.sum(case((outstanding > 0, outstanding), else_=0)), 0)
        # overdue_expr = func.coalesce(
        #     func.sum(
        #         case(
        #             (and_(outstanding > 0, Invoice.due_date < as_of), outstanding),
        #             else_=0,
        #         )
        #     ),
        #     0,
        # )
        # stmt = (
        #     select(total_expr, overdue_expr)
        #     .select_from(Invoice)
        #     .outerjoin(paid, paid.c.invoice_id == Invoice.id)
        #     .where(Invoice.customer_id == customer_id)
        # )
        # total, overdue = (await self._session.execute(stmt)).one()
        # return Decimal(total), Decimal(overdue)
        return Decimal(0), Decimal(0)

    # --- beat planning: handled customers --------------------------------

    async def handled_customers(self, rep_id: uuid.UUID, since: date) -> list[Customer]:
        """Active customers "handled by" ``rep_id`` since ``since`` (§7.1): at
        least one activity by the rep, or linked to a lead assigned to the rep.
        """
        by_activity = select(SalesActivity.customer_id).where(
            SalesActivity.rep_user_id == rep_id,
            SalesActivity.customer_id.is_not(None),
            SalesActivity.occurred_at >= since,
        )
        by_lead = select(Lead.customer_id).where(
            Lead.assigned_to_user_id == rep_id,
            Lead.customer_id.is_not(None),
            Lead.created_at >= since,
        )
        handled_ids = by_activity.union(by_lead).subquery()
        stmt = (
            select(Customer)
            .where(
                Customer.id.in_(select(handled_ids.c.customer_id)),
                Customer.is_active.is_(True),
            )
            .order_by(Customer.company_name)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    # --- activity recency / counts ---------------------------------------

    async def activity_count(
        self, customer_id: uuid.UUID, since: date, types: Sequence[ActivityType]
    ) -> int:
        stmt = select(func.count()).where(
            SalesActivity.customer_id == customer_id,
            SalesActivity.type.in_(types),
            SalesActivity.occurred_at >= since,
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def last_activity_date(
        self, customer_id: uuid.UUID, types: Sequence[ActivityType]
    ) -> date | None:
        stmt = select(func.max(SalesActivity.occurred_at)).where(
            SalesActivity.customer_id == customer_id,
            SalesActivity.type.in_(types),
        )
        last: datetime | None = (await self._session.execute(stmt)).scalar_one_or_none()
        return last.date() if last is not None else None

    # ------------------------------------------------------------------
    # Bulk variants — all customers in one query (beat planning)
    # ------------------------------------------------------------------

    async def revenue_in_period_bulk(
        self, customer_ids: list[uuid.UUID], start: date, end: date
    ) -> dict[uuid.UUID, Decimal]:
        """Revenue for ALL customers in a single query."""
        if not customer_ids:
            return {}
        stmt = (
            select(
                SalesOrder.customer_id,
                func.coalesce(func.sum(SalesOrder.total), 0),
            )
            .where(
                SalesOrder.customer_id.in_(customer_ids),
                SalesOrder.status == SalesOrderStatus.SHIPPED,
                SalesOrder.shipped_date >= start,
                SalesOrder.shipped_date < end,
            )
            .group_by(SalesOrder.customer_id)
        )
        result = {cid: Decimal(0) for cid in customer_ids}
        for customer_id, total in (await self._session.execute(stmt)).all():
            result[customer_id] = Decimal(total)
        return result

    async def last_activity_date_bulk(
        self, customer_ids: list[uuid.UUID], types: Sequence[ActivityType]
    ) -> dict[uuid.UUID, date | None]:
        """Most recent activity date for ALL customers in a single query."""
        if not customer_ids:
            return {}
        stmt = (
            select(
                SalesActivity.customer_id,
                func.max(SalesActivity.occurred_at),
            )
            .where(
                SalesActivity.customer_id.in_(customer_ids),
                SalesActivity.type.in_(types),
            )
            .group_by(SalesActivity.customer_id)
        )
        result: dict[uuid.UUID, date | None] = {cid: None for cid in customer_ids}
        for customer_id, last in (await self._session.execute(stmt)).all():
            result[customer_id] = last.date() if last is not None else None
        return result
