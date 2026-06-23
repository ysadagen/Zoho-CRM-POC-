"""Response schemas for the health endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class HealthStatus(BaseModel):
    """Liveness response — the process is up."""

    status: str


class ZohoHealthStatus(BaseModel):
    """Zoho connectivity response — a valid access token was obtainable."""

    status: str
    zoho: str
