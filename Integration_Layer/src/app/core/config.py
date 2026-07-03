"""Application configuration loaded from ``.env`` via Pydantic Settings.

All configuration MUST flow through :class:`Settings`. Do not call
``os.getenv`` anywhere else in the codebase — that bypasses validation and
makes settings invisible to ``.env.example``.

``.env.example`` is the source of truth for which variables exist; every
field below has a matching entry there.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

EnvName = Literal["dev", "staging", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Strongly-typed settings for the Integration Layer.

    Values load from the process environment, falling back to ``.env`` in
    the current working directory. Unknown variables are ignored so a single
    ``.env`` shared between tools does not break boot.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_env: EnvName = "dev"
    log_level: LogLevel = "INFO"
    app_host: str = "0.0.0.0"
    app_port: int = 8001

    # Database (integration_db)
    database_url: str
    test_database_url: str

    # Inbound auth — shared secret the Backend sends as a header. Ingest reuses
    # this same secret when calling the Backend (the Backend validates it as
    # INTEGRATION_LAYER_API_KEY), so the two values MUST match.
    internal_api_key: str

    # Backend (ingest write-back, Track A). The IL POSTs resolved Zoho records
    # to the Backend's internal ingest endpoints; it never writes inventory_db.
    backend_base_url: str = "http://localhost:8000"

    # Master switch for pulling from Zoho. When false (default) an ingest run is
    # a no-op, so the AI engines stay deterministic until ingest is switched on.
    zoho_ingest_enabled: bool = False

    # Zoho CRM (outbound, OAuth 2.0 refresh-token flow)
    zoho_accounts_url: str
    zoho_api_base_url: str
    zoho_client_id: str
    zoho_client_secret: str
    # Bootstrap refresh token — used only until a token row exists in
    # ``zoho_tokens``; thereafter the persisted value is authoritative.
    zoho_refresh_token: str

    # Inbound webhook signature verification (Track B / webhooks — not used in A0).
    zoho_webhook_secret: str

    # Application-layer encryption for persisted OAuth tokens (AES via Fernet).
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    zoho_token_encryption_key: str

    # Outbound HTTP behaviour (Zoho client)
    http_timeout_seconds: int = 10
    http_max_retries: int = 3
    http_backoff_base_ms: int = 200

    # Idempotency (Track B push — table exists in A0, contract enforced later).
    idempotency_ttl_hours: int = 24


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton :class:`Settings` instance.

    The cache means ``.env`` is read exactly once per process. Tests that
    need to override values monkeypatch the environment before the first
    call, or clear the cache via ``get_settings.cache_clear()``.
    """
    return Settings()
