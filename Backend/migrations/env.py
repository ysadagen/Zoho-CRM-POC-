"""Alembic migrations environment for the Inventory Backend.

Uses :data:`app.models.Base.metadata` as the autogenerate target and runs in
async mode against the same dialect the app uses at runtime (``asyncpg``).

Intentional design choice: this file does NOT call ``get_settings()`` from
``app.core.config``. The full application settings may require secrets that
are irrelevant at migration time. A minimal ``_MigrationSettings`` class reads
only what Alembic needs so that ``alembic upgrade head`` works without a
fully-populated ``.env``.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.models import Base  # imports register every model with Base.metadata


class _MigrationSettings(BaseSettings):
    """Minimal settings for Alembic — only the database URL is required."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the live URL — alembic.ini's sqlalchemy.url is deliberately empty.
# A caller may override via ``alembic -x url=postgresql+asyncpg://...`` (the
# test harness does this to point at the test DB instead of the dev DB
# without having to mutate environment variables for the whole process).
_x_args = context.get_x_argument(as_dictionary=True)
_db_url = _x_args.get("url") or _MigrationSettings().database_url
config.set_main_option("sqlalchemy.url", _db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it against a live DB.

    Useful for generating SQL scripts to hand to a DBA. Not used in the
    normal dev workflow.
    """
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
