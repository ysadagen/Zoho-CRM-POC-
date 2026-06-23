"""Alembic migrations environment for the Integration Layer.

Reads the database URL from the application :class:`Settings` (single source
of truth) and uses :data:`app.models.Base.metadata` as the autogenerate
target. Runs in async mode against the same dialect the app uses at runtime
(``asyncpg``).
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.models import Base  # imports register every model with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the live URL — alembic.ini's sqlalchemy.url is deliberately empty.
# A caller may override via ``alembic -x url=postgresql+asyncpg://...`` (the
# test harness does this to point at the test DB instead of the dev DB
# without having to mutate environment variables for the whole process).
_x_args = context.get_x_argument(as_dictionary=True)
_db_url = _x_args.get("url") or get_settings().database_url
config.set_main_option("sqlalchemy.url", _db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it against a live DB."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against the live async engine."""
    section = config.get_section(config.config_ini_section) or {}
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
