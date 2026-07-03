"""Application configuration for the Intelligence service.

All configuration MUST flow through :class:`Settings`. Do not call
``os.getenv`` anywhere else — that bypasses validation and makes settings
invisible to ``.env.example``.

The service shares ``inventory_db`` with the Backend (read CRM data, own the
scoring tables) and validates the **same** JWTs, so ``jwt_secret_key`` /
``jwt_algorithm`` must match the Backend's values.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

EnvName = Literal["dev", "staging", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Strongly-typed settings loaded from the environment / ``.env``."""

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
    # 8000 = Backend, 8001 = Integration Layer (planned); Intelligence takes 8002.
    app_port: int = 8002

    # Database — the same Postgres database the Backend uses.
    database_url: str
    test_database_url: str

    # Auth (JWT) — must match the Backend so tokens issued there validate here.
    jwt_secret_key: str
    jwt_algorithm: Literal["HS256", "RS256"] = "HS256"

    # CORS
    cors_allowed_origins: str = ""

    @property
    def cors_origins(self) -> list[str]:
        """CORS origins as a list, splitting the comma-separated env value."""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton :class:`Settings` (``.env`` read once)."""
    return Settings()
