"""Tests for the ingest API surface (auth + the disabled no-op path)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.security import INTERNAL_API_KEY_HEADER


@pytest.fixture
def internal_headers() -> dict[str, str]:
    return {INTERNAL_API_KEY_HEADER: get_settings().internal_api_key}


@pytest.fixture
def ingest_disabled() -> Iterator[None]:
    settings = get_settings()
    original = settings.zoho_ingest_enabled
    settings.zoho_ingest_enabled = False
    try:
        yield
    finally:
        settings.zoho_ingest_enabled = original


async def test_run_requires_internal_api_key(client_with_db: AsyncClient) -> None:
    response = await client_with_db.post("/api/v1/ingest/run")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_API_KEY"


async def test_run_disabled_returns_noop_summary(
    client_with_db: AsyncClient, internal_headers: dict[str, str], ingest_disabled: None
) -> None:
    response = await client_with_db.post("/api/v1/ingest/run", headers=internal_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["leads_created"] == 0


async def test_status_returns_recent_feed(
    client_with_db: AsyncClient, internal_headers: dict[str, str]
) -> None:
    response = await client_with_db.get("/api/v1/ingest/status", headers=internal_headers)
    assert response.status_code == 200
    assert "recent" in response.json()
