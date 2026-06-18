"""Domain exception hierarchy for the Backend.

All application-level errors inherit from :class:`AppError`. The global
exception handler in :mod:`app.main` maps these to a consistent JSON envelope.
Services raise these; routes never catch them.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all domain exceptions.

    Subclasses override :attr:`status_code` and :attr:`code`. The ``code``
    attribute is the stable, machine-readable identifier returned in the
    JSON envelope; consumers should branch on ``code``, not on
    human-readable ``message``.
    """

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class NotFoundError(AppError):
    """The requested resource does not exist (HTTP 404)."""

    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    """The request conflicts with current state (HTTP 409).

    Examples: duplicate unique key, idempotency conflict, insufficient stock.
    """

    status_code = 409
    code = "CONFLICT"


class ValidationError(AppError):
    """A business rule rejected the request (HTTP 422).

    Reserved for domain-level validation. Pydantic schema validation
    is handled by FastAPI directly and also surfaces as 422.
    """

    status_code = 422
    code = "VALIDATION_ERROR"


class AuthenticationError(AppError):
    """Caller is not authenticated (HTTP 401)."""

    status_code = 401
    code = "AUTHENTICATION_ERROR"


class AuthorizationError(AppError):
    """Caller is authenticated but not permitted (HTTP 403)."""

    status_code = 403
    code = "AUTHORIZATION_ERROR"


class ServiceUnavailableError(AppError):
    """A downstream dependency we need is unreachable (HTTP 503).

    Raised by the readiness probe when the database fails a quick
    health query. Distinct from 500 ``INTERNAL_ERROR`` because it
    signals "retry later, the *thing* is fine but a dep is down" —
    important for orchestrators (k8s readiness probe routes traffic
    away on 503; on 500 the pod stays in rotation).
    """

    status_code = 503
    code = "SERVICE_UNAVAILABLE"
