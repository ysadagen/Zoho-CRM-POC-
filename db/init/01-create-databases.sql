-- ---------------------------------------------------------------------------
-- Postgres init script for the Inventory CRM POC.
--
-- This file runs ONCE, the first time the postgres container boots against
-- an empty data volume. It is executed by the official postgres image from
-- /docker-entrypoint-initdb.d/.
--
-- Re-running this script after the volume already exists is a no-op (the
-- image only runs init scripts on a fresh data dir). To re-trigger it, you
-- must destroy the volume:  docker compose down -v
--
-- We only create the databases here. Schemas (tables, columns, indexes) are
-- owned by each service's Alembic migrations — never put DDL here.
--
-- The `*_test_db` databases are dev-only — they exist so each service's
-- pytest suite has an isolated database to apply migrations against and
-- drop between sessions. Production environments do NOT need them.
-- ---------------------------------------------------------------------------

CREATE DATABASE inventory_db;
CREATE DATABASE integration_db;
CREATE DATABASE inventory_test_db;
CREATE DATABASE integration_test_db;
