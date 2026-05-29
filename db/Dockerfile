# ---------------------------------------------------------------------------
# Dev-only Postgres image for the Inventory CRM POC.
#
# Why a custom image instead of `image: postgres:16-alpine` + a bind mount?
#   - Bind mounts for init scripts are unreliable on Windows (path translation
#     and file-permission quirks with Docker Desktop). Baking the scripts in
#     removes the bind mount entirely.
#   - Reproducible: the image is identical on every dev machine and in CI.
#   - Scope: this image is for local dev only. Production uses managed
#     Postgres (RDS / Cloud SQL) and provisions databases via IaC, not init
#     scripts.
#
# Init scripts in /docker-entrypoint-initdb.d/ run once, on a fresh data
# volume. To re-run them, wipe the volume: `docker compose down -v`.
# ---------------------------------------------------------------------------

FROM postgres:16-alpine

COPY init/ /docker-entrypoint-initdb.d/
