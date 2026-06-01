"""add items non-negative check constraints

Revision ID: 551b0348b93a
Revises: 83278f4256d2
Create Date: 2026-05-29 15:32:41.723313

Adds the three DB-level invariants the schema layer cannot enforce
when something writes ``items`` outside Pydantic (raw SQL, a future
internal service path, a forgotten guard). Names mirror those declared
in ``Item.__table_args__`` so a re-autogenerate wouldn't re-emit them.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "551b0348b93a"
down_revision: str | None = "83278f4256d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_items_stock_quantity_non_negative",
        "items",
        "stock_quantity >= 0",
    )
    op.create_check_constraint(
        "ck_items_reorder_threshold_non_negative",
        "items",
        "reorder_threshold IS NULL OR reorder_threshold >= 0",
    )
    op.create_check_constraint(
        "ck_items_unit_price_non_negative",
        "items",
        "unit_price >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_items_unit_price_non_negative", "items", type_="check")
    op.drop_constraint(
        "ck_items_reorder_threshold_non_negative", "items", type_="check"
    )
    op.drop_constraint(
        "ck_items_stock_quantity_non_negative", "items", type_="check"
    )
