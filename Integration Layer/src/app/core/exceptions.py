"""Domain exception hierarchy for the Integration Layer.

All application-level errors inherit from :class:`AppError`. The global
exception handler in :mod:`app.main` maps these to a consistent JSON envelope.
Services raise these; routes never catch them.

Zoho-specific failures live in a separate, narrower hierarchy
(``clients/zoho/errors.py``); services translate those into the errors below
so route handlers never see a Zoho-specific exception.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all domain exceptions.

    Subclasses override :attr:`status_code` and :attr:`code`. The ``code``
    attribute is the stable, machine-readable identifier returned in the JSON
    envelope; consumers should branch on ``code``, not on the human-readable
    ``message``.
    """

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class NotFoundError(AppError):
    """The requested resource does not exist (HTTP 404).

    Examples: missing CRM mapping, missing sync log.
    """

    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    """The request conflicts with current state (HTTP 409).

    Example: idempotency conflict (same key, different payload).
    """

    status_code = 409
    code = "CONFLICT"


class ValidationError(AppError):
    """A business rule rejected the request (HTTP 422).

    Reserved for domain-level validation. Pydantic schema validation is
    handled by FastAPI directly and also surfaces as 422.
    """

    status_code = 422
    code = "VALIDATION_ERROR"


class AuthenticationError(AppError):
    """Caller is not authenticated (HTTP 401).

    Bad internal API key, or a webhook whose signature does not verify.
    """

    status_code = 401
    code = "AUTHENTICATION_ERROR"


class UpstreamError(AppError):
    """Zoho returned a non-retryable error we surface to the caller (HTTP 502)."""

    status_code = 502
    code = "UPSTREAM_ERROR"


class UpstreamUnavailableError(AppError):
    """Zoho is unreachable, rate-limited, or our client is circuit-broken (HTTP 503)."""

    status_code = 503
    code = "UPSTREAM_UNAVAILABLE"
