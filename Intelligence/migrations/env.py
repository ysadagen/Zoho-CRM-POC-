"""Alembic environment for the Intelligence service.

This service shares ``inventory_db`` with the Backend but owns only the
scoring tables. Two safeguards keep the two migration chains from colliding:

* a dedicated ``version_table`` (``alembic_version_intelligence``) so this
  service's revision pointer never overwrites the Backend's;
* an ``include_name`` filter so autogenerate only ever considers the scoring
  tables it owns — the Backend-owned CRM tables (which appear in
  ``Base.metadata`` as read models) are never proposed for create/drop.

The URL is read from ``app.core.config.Settings`` (single source of truth);
a caller may override via ``alembic -x url=...`` (the test harness does this).
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.models import Base  # registers every model with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_x_args = context.get_x_argument(as_dictionary=True)
_db_url = _x_args.get("url") or get_settings().database_url
config.set_main_option("sqlalchemy.url", _db_url)

target_metadata = Base.metadata

#: The only tables this service owns and migrates.
_OWNED_TABLES = {
    "scoring_configs",
    "lead_scores",
    "customer_health_scores",
    "effort_efficiency_scores",
    "visit_priority_scores",
}

_VERSION_TABLE = "alembic_version_intelligence"


def _include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    """Restrict autogenerate to the scoring tables this service owns."""
    if type_ == "table":
        return name in _OWNED_TABLES
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=_VERSION_TABLE,
        include_name=_include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table=_VERSION_TABLE,
        include_name=_include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    connectable = async_engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
