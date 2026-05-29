"""Tests for the ``/health`` liveness endpoint."""

from __future__ import annotations

from httpx import AsyncClient


async def test_health_returns_200_with_status_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
