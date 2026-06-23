"""Security primitives — internal API-key verification.

This service has no user accounts. Inbound authentication for ``/sync`` and
``/admin`` routes is a single shared secret the Backend sends in a header;
webhook routes authenticate by HMAC signature instead (added with the webhook
endpoint in a later phase).

Nothing here knows about HTTP or FastAPI — it is a thin, unit-testable
boundary. The FastAPI ``Depends`` wrapper lives in ``dependencies/auth.py``.
"""

from __future__ import annotations

import hmac

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

INTERNAL_API_KEY_HEADER = "X-Internal-API-Key"


def verify_internal_api_key(provided: str | None) -> None:
    """Validate the inbound internal API key, raising on mismatch.

    Uses :func:`hmac.compare_digest` for a constant-time comparison so a
    caller cannot infer the secret from response timing. Raises
    :class:`AuthenticationError` (401) when the header is missing or wrong.
    """
    expected = get_settings().internal_api_key
    if not provided or not hmac.compare_digest(provided, expected):
        raise AuthenticationError("Invalid or missing internal API key", code="INVALID_API_KEY")
