"""Models package — exposes :class:`Base` and registers every model.

Two groups share one ``Base.metadata``:

* **Read models** for the Backend-owned CRM tables this service consumes
  (``users``, ``customers``, ``items``, ``leads``, ``sales_orders`` (+ items),
  ``sales_activities``, ``customer_targets``).
  In production these tables already exist (the Backend owns them); this
  service only SELECTs from them. In the test schema they are materialised by
  ``Base.metadata.create_all`` so tests can set up fixtures directly.
* **Owned models** — the scoring tables this service owns and migrates
  (``scoring_configs`` + the four snapshot tables).

The imports look unused to linters — they exist for their registration side
effect (Alembic / ``create_all`` walk ``Base.metadata``).
"""

from app.core.database import Base
from app.models.customer import Customer
from app.models.customer_target import CustomerTarget
# DISABLED — Invoice/Payment moving onto SalesOrder (see INVOICE_TO_SALES_ORDER_MIGRATION_PLAN.md)
# from app.models.invoice import Invoice, Payment
from app.models.item import Item
from app.models.lead import Lead, LeadStageHistory
from app.models.sales_activity import SalesActivity
from app.models.sales_order import SalesOrder, SalesOrderItem
from app.models.score_snapshot import (
    CustomerHealthScore,
    EffortEfficiencyScore,
    LeadScore,
    VisitPriorityScore,
)
from app.models.scoring_config import ScoringConfig
from app.models.user import User

__all__ = [
    "Base",
    "Customer",
    "CustomerHealthScore",
    "CustomerTarget",
    "EffortEfficiencyScore",
    # "Invoice",  # DISABLED
    "Item",
    "Lead",
    "LeadScore",
    "LeadStageHistory",
    # "Payment",  # DISABLED
    "SalesActivity",
    "SalesOrder",
    "SalesOrderItem",
    "ScoringConfig",
    "User",
    "VisitPriorityScore",
]
