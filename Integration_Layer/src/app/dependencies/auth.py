"""Inbound authentication dependency — the shared internal API key.

The Backend (and a scheduled ingest trigger) authenticate to this service
with a shared secret in the ``X-Internal-API-Key`` header. This dependency
guards ``/sync``, ``/ingest``, and ``/admin`` routes as they are added;
webhook routes authenticate by HMAC signature instead. Health probes are
public, mirroring the Backend's liveness/readiness probes.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Header

from app.core.security import INTERNAL_API_KEY_HEADER, verify_internal_api_key


async def require_internal_api_key(
    x_internal_api_key: Annotated[str | None, Header(alias=INTERNAL_API_KEY_HEADER)] = None,
) -> None:
    """Reject the request unless it carries the correct internal API key (401)."""
    verify_internal_api_key(x_internal_api_key)
