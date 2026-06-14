"""Application configuration loaded from ``.env`` via Pydantic Settings.

All configuration MUST flow through :class:`Settings`. Do not call
``os.getenv`` anywhere else in the codebase — that bypasses validation
and makes settings invisible to ``.env.example``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

EnvName = Literal["dev", "staging", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Values are loaded from the process environment, falling back to
    ``.env`` in the current working directory. Unknown variables are
    ignored so a single ``.env`` shared between tools does not break boot.
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
    app_port: int = 8000

    # Database
    database_url: str
    test_database_url: str

    # Auth (JWT)
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    # There is no /refresh endpoint by design — re-login is the only
    # renewal path. Tune via .env if a longer (or shorter) session
    # better fits the operating model.
    access_token_expire_minutes: int = 60

    # Integration Layer
    integration_layer_base_url: str
    integration_layer_api_key: str
    integration_layer_timeout_seconds: int = 10

    # CORS
    cors_allowed_origins: str = ""

    @property
    def cors_origins(self) -> list[str]:
        """Return CORS origins as a list, splitting the comma-separated env value."""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton :class:`Settings` instance.

    The cache means the ``.env`` file is read exactly once per process.
    Tests that need to override values should monkeypatch the environment
    before the first call, or clear the cache via ``get_settings.cache_clear()``.
    """
    return Settings()
