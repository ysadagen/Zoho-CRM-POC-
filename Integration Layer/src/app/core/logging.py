"""Structured logging configuration.

Bridges stdlib :mod:`logging` to :mod:`structlog` so application code can keep
using ``logger = logging.getLogger(__name__)`` while producing structured
output. In ``dev`` the output is a human-readable console renderer; otherwise
it is JSON suitable for a log aggregator.

A redaction processor masks the secret-bearing keys this service handles
(access/refresh tokens, client secret, webhook secret, auth headers) before
any line is rendered — CLAUDE.md §8 requires these never reach the logs.

:func:`configure_logging` is idempotent and is called from the application
factory in :mod:`app.main`.
"""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.types import EventDict, Processor, WrappedLogger

# Substrings that, if present in an event-dict key, mean the value is a secret
# and must never be rendered. Matched case-insensitively against each key.
_SENSITIVE_KEY_PARTS: tuple[str, ...] = (
    "access_token",
    "refresh_token",
    "client_secret",
    "webhook_secret",
    "authorization",
    "api_key",
    "secret",
    "password",
)

_REDACTED = "***REDACTED***"


def _redact_sensitive(_logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
    """Replace the value of any secret-bearing key with a fixed placeholder."""
    for key in list(event_dict.keys()):
        lowered = key.lower()
        if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
            event_dict[key] = _REDACTED
    return event_dict


def configure_logging(*, env: str, level: str) -> None:
    """Configure stdlib logging and structlog for the whole process."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.ExtraAdder(),
        _redact_sensitive,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Processor = (
        structlog.dev.ConsoleRenderer(colors=True)
        if env == "dev"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Reduce noise from third-party loggers in dev. Adjust as needed.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
