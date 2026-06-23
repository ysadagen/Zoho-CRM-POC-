"""Backend-client exception hierarchy.

Failures of the IL → Backend ingest calls. Raised inside ``clients/backend``
and translated by the ingest service into the ``core.exceptions`` family (or
into a PARKED/FAILED sync-log outcome). Routes never see these.
"""

from __future__ import annotations


class BackendError(Exception):
    """Base class for Backend ingest-call failures."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class BackendNotFoundError(BackendError):
    """The Backend reported a referenced entity does not exist (HTTP 404)."""


class BackendValidationError(BackendError):
    """The Backend rejected the payload (HTTP 422)."""


class BackendUnavailableError(BackendError):
    """The Backend was unreachable, 5xx, or ingest is disabled there (503)."""
