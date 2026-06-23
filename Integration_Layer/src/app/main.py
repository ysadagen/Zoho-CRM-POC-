"""FastAPI application factory for the Integration Layer.

Intentionally small: it wires the cross-cutting concerns (logging, exception
handling, middleware) and mounts the API routers. Business logic and route
handlers live elsewhere.

There is no CORS configuration — this service has no browser clients. Its
callers are the Backend, a scheduled ingest trigger, and Zoho's webhook
delivery, all server-to-server.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.api.v1.health import router as health_router
from app.api.v1.ingest import router as ingest_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.request_id import RequestIDMiddleware

logger = logging.getLogger(__name__)


def _build_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str | None,
    details: Any = None,
) -> JSONResponse:
    """Build the canonical error envelope.

    The shape ``{"error": {"code", "message", "request_id"}}`` is this
    service's contract for every non-2xx response, identical to the Backend's
    so the caller parses one shape regardless of which service answered.
    """
    body: dict[str, Any] = {"code": code, "message": message, "request_id": request_id}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status_code, content={"error": body})


def _format_validation_message(errors: Sequence[Mapping[str, Any]]) -> str:
    """Compose a short, human-readable summary from Pydantic errors."""
    if not errors:
        return "Request validation failed"
    first = errors[0]
    loc = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query", "path"))
    msg = first.get("msg", "Validation failed")
    return f"{loc}: {msg}" if loc else msg


def create_app() -> FastAPI:
    """Build and return a fully wired FastAPI application."""
    settings = get_settings()
    configure_logging(env=settings.app_env, level=settings.log_level)

    app = FastAPI(
        title="Zoho Integration Layer",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "prod" else None,
        redoc_url=None,
    )

    # Middleware is LIFO in Starlette: the LAST added is OUTERMOST and runs
    # first on incoming requests. RequestIDMiddleware must run before
    # AccessLogMiddleware so the request_id is bound to the structlog context
    # by the time the access line is emitted.
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # --- Exception handlers ---------------------------------------------------
    # All paths converge on the same `{error: {code, message, request_id}}`
    # envelope so the caller parses one shape regardless of failure cause.

    @app.exception_handler(AppError)
    async def handle_app_exception(request: Request, exc: AppError) -> JSONResponse:
        request_id: str | None = getattr(request.state, "request_id", None)
        logger.warning(
            "app_exception",
            extra={"code": exc.code, "status_code": exc.status_code, "path": request.url.path},
        )
        return _build_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Map Pydantic / FastAPI validation failures to the project envelope."""
        request_id: str | None = getattr(request.state, "request_id", None)
        raw_errors = exc.errors()
        details = [
            {
                "loc": list(err.get("loc", [])),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in raw_errors
        ]
        logger.info(
            "validation_error",
            extra={"path": request.url.path, "error_count": len(details)},
        )
        return _build_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="VALIDATION_ERROR",
            message=_format_validation_message(raw_errors),
            request_id=request_id,
            details=details,
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        """Last-resort handler — anything not explicitly caught becomes 500.

        Logged at ERROR with the exception chain so the cause is recoverable
        from logs by the ``request_id`` in the envelope. Message is generic so
        internal details never leak to clients.
        """
        request_id: str | None = getattr(request.state, "request_id", None)
        logger.error(
            "unhandled_exception",
            exc_info=exc,
            extra={"path": request.url.path, "request_id": request_id},
        )
        return _build_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            request_id=request_id,
        )

    # --- Routers --------------------------------------------------------------
    # Health probes mount at the root (/health, /health/zoho), not under
    # /api/v1 — they are infrastructure, not part of the versioned API surface.
    app.include_router(health_router)
    app.include_router(ingest_router, prefix="/api/v1")

    logger.info("app_initialized", extra={"env": settings.app_env})
    return app


app = create_app()
