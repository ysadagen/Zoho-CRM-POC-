"""Proves the first migration applied cleanly on the integration test DB.

The session-scoped ``_initialize_test_schema`` fixture has already run
``alembic upgrade head``; this test asserts the five A0 tables exist, making
the "migrations apply on integration_db" exit criterion an explicit check
rather than an implicit side effect of the bootstrap.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_EXPECTED_TABLES = {
    "zoho_tokens",
    "crm_mappings",
    "sync_logs",
    "idempotency_keys",
    "webhook_events",
}


async def test_all_a0_tables_exist(db_session: AsyncSession) -> None:
    rows = await db_session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    )
    present = {row[0] for row in rows}
    missing = _EXPECTED_TABLES - present
    assert not missing, f"missing tables after migration: {sorted(missing)}"
