"""initial integration schema

Revision ID: 86e5805cbb3d
Revises:
Create Date: 2026-06-19 14:45:57.666806

Creates the five A0 tables (zoho_tokens, crm_mappings, sync_logs,
idempotency_keys, webhook_events) plus the CLAUDE.md §10 indexes.

The PostgreSQL ENUM types are created explicitly (``checkfirst=True``) before
the tables and dropped after them. ``mapping_entity_type`` is shared by
``crm_mappings`` and ``sync_logs``; letting ``create_table`` auto-create it
would emit ``CREATE TYPE`` twice and fail. Declaring each enum with
``create_type=False`` and creating it once is the deterministic fix.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "86e5805cbb3d"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Enum types are managed explicitly (create_type=False) so the shared
# mapping_entity_type is created exactly once, before any table references it.
mapping_entity_type = postgresql.ENUM(
    "CUSTOMER",
    "VENDOR",
    "ITEM",
    "SALES_ORDER",
    "PURCHASE_ORDER",
    "LEAD",
    "ACTIVITY",
    "DEAL",
    "USER",
    name="mapping_entity_type",
    create_type=False,
)
sync_direction = postgresql.ENUM("PUSH", "INGEST", name="sync_direction", create_type=False)
sync_status = postgresql.ENUM(
    "PENDING",
    "SUCCESS",
    "FAILED",
    "FAILED_PERMANENT",
    "RATE_LIMITED",
    "PARKED",
    name="sync_status",
    create_type=False,
)
webhook_status = postgresql.ENUM(
    "PENDING", "PROCESSED", "FAILED", name="webhook_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    mapping_entity_type.create(bind, checkfirst=True)
    sync_direction.create(bind, checkfirst=True)
    sync_status.create(bind, checkfirst=True)
    webhook_status.create(bind, checkfirst=True)

    op.create_table(
        "zoho_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("token_type", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("api_domain", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider"),
    )

    op.create_table(
        "crm_mappings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("entity_type", mapping_entity_type, nullable=False),
        sa.Column("local_id", sa.String(length=255), nullable=True),
        sa.Column("zoho_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type", "local_id", name="uq_crm_mappings_entity_local_id"),
        sa.UniqueConstraint("entity_type", "zoho_id", name="uq_crm_mappings_entity_zoho_id"),
    )

    op.create_table(
        "sync_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("direction", sync_direction, nullable=False),
        sa.Column("entity_type", mapping_entity_type, nullable=True),
        sa.Column("local_id", sa.String(length=255), nullable=True),
        sa.Column("zoho_id", sa.String(length=255), nullable=True),
        sa.Column("operation", sa.String(length=100), nullable=True),
        sa.Column("status", sync_status, nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("zoho_status_code", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sync_logs_entity_type_local_id_created_at",
        "sync_logs",
        ["entity_type", "local_id", "created_at"],
        unique=False,
    )
    op.create_index(op.f("ix_sync_logs_status"), "sync_logs", ["status"], unique=False)

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("module", sa.String(length=100), nullable=True),
        sa.Column("operation", sa.String(length=100), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", webhook_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(op.f("ix_webhook_events_status"), "webhook_events", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_webhook_events_status"), table_name="webhook_events")
    op.drop_table("webhook_events")
    op.drop_table("idempotency_keys")
    op.drop_index(op.f("ix_sync_logs_status"), table_name="sync_logs")
    op.drop_index("ix_sync_logs_entity_type_local_id_created_at", table_name="sync_logs")
    op.drop_table("sync_logs")
    op.drop_table("crm_mappings")
    op.drop_table("zoho_tokens")

    bind = op.get_bind()
    webhook_status.drop(bind, checkfirst=True)
    sync_status.drop(bind, checkfirst=True)
    sync_direction.drop(bind, checkfirst=True)
    mapping_entity_type.drop(bind, checkfirst=True)
