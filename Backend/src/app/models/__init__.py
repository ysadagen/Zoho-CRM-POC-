"""Models package — exposes :class:`Base` and registers every model.

Every ORM model in the project MUST be imported into this module.
Alembic's autogenerate walks ``Base.metadata`` to discover tables, and
SQLAlchemy only registers a mapped class once its module has been
imported. Forgetting to import a new model here is the most common
cause of autogenerate producing an empty revision.

The model imports below will look unused to linters — that is expected;
they exist for their import side effect of registering with the metadata.
"""

from app.core.database import Base
from app.models.batch import Batch
from app.models.customer import Customer
from app.models.finished_item_detail import FinishedItemDetail
from app.models.item import Item
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.raw_item_detail import RawItemDetail
from app.models.sales_order import SalesOrder, SalesOrderItem
from app.models.score_snapshot import LeadScore
from app.models.scoring_config import ScoringConfig
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.models.vendor import Vendor
from app.models.vendor_item_term import VendorItemTerm

__all__ = [
    "Base",
    "Batch",
    "Customer",
    "FinishedItemDetail",
    "Item",
    "LeadScore",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "RawItemDetail",
    "SalesOrder",
    "SalesOrderItem",
    "ScoringConfig",
    "StockMovement",
    "User",
    "Vendor",
    "VendorItemTerm",
]
