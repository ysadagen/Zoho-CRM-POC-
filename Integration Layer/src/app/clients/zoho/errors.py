"""Zoho-specific exception hierarchy.

A narrow hierarchy for failures of Zoho HTTP traffic, raised inside
``clients/zoho`` and translated by services into the ``core.exceptions``
``AppError`` family. Route handlers never see these.
"""

from __future__ import annotations


class ZohoError(Exception):
    """Base class for all Zoho client failures.

    ``status_code`` is the HTTP status Zoho returned (``None`` for transport
    failures); ``zoho_code`` is Zoho's machine-readable error code when the
    response body carried one.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        zoho_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.zoho_code = zoho_code


class ZohoAuthError(ZohoError):
    """Authentication/authorisation failure (HTTP 401/403, or token refresh failed)."""


class ZohoRateLimitError(ZohoError):
    """Zoho rate limit hit (HTTP 429).

    ``retry_after`` is the server-advised wait in seconds when present.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = 429,
        zoho_code: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, zoho_code=zoho_code)
        self.retry_after = retry_after


class ZohoNotFoundError(ZohoError):
    """A requested Zoho resource does not exist (HTTP 404)."""


class ZohoServerError(ZohoError):
    """Zoho returned 5xx, or the request never completed (timeout/connection error)."""


class ZohoAPIError(ZohoError):
    """A non-retryable Zoho client error (other 4xx) not covered by a subclass."""
