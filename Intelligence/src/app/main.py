"""FastAPI application factory for the Intelligence service.

Wires cross-cutting concerns (logging, the error envelope, request-id +
access-log middleware, CORS) and mounts the single ``/intelligence`` router.
Business logic lives in ``services/``; route handlers stay thin.

The service shares ``inventory_db`` with the Backend — it reads CRM data and
owns the scoring tables — and validates the Backend's JWTs.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from typing import Annotated, Any

from fastapi import Depends, FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request

from app.api.v1.intelligence import router as intelligence_router
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AppError, ServiceUnavailableError
from app.core.logging import configure_logging
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.request_id import RequestIDMiddleware

logger = logging.getLogger(__name__)

_ALLOWED_CORS_HEADERS: list[str] = ["Authorization", "Content-Type", "X-Request-ID"]


def _build_error_response(
    *, status_code: int, code: str, message: str, request_id: str | None, details: Any = None
) -> JSONResponse:
    """Build the canonical ``{"error": {code, message, request_id}}`` envelope."""
    body: dict[str, Any] = {"code": code, "message": message, "request_id": request_id}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status_code, content={"error": body})


def _format_validation_message(errors: Sequence[Mapping[str, Any]]) -> str:
    if not errors:
        return "Request validation failed"
    first = errors[0]
    loc = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query", "path"))
    msg = first.get("msg", "Validation failed")
    return f"{loc}: {msg}" if loc else msg


_ReadySession = Annotated[AsyncSession, Depends(get_db)]


def create_app() -> FastAPI:
    """Build and return a fully wired FastAPI application."""
    settings = get_settings()
    configure_logging(env=settings.app_env, level=settings.log_level)

    app = FastAPI(
        title="Intelligence Service",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "prod" else None,
        redoc_url=None,
    )

    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=_ALLOWED_CORS_HEADERS,
            expose_headers=["X-Request-ID"],
        )

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
            "validation_error", extra={"path": request.url.path, "error_count": len(details)}
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

    @app.get("/health", tags=["health"], summary="Liveness probe")
    async def health() -> dict[str, str]:
        """Return 200 OK if the process is running. No dependency checks."""
        return {"status": "ok"}

    @app.get("/ready", tags=["health"], summary="Readiness probe")
    async def ready(session: _ReadySession) -> dict[str, str]:
        """Return 200 only if the shared database is reachable under 1s."""
        try:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=1.0)
        except (TimeoutError, SQLAlchemyError, OSError) as exc:
            logger.warning("readiness_probe_failed", extra={"error": str(exc)})
            raise ServiceUnavailableError("Database unreachable", code="DB_UNAVAILABLE") from exc
        return {"status": "ready"}

    app.include_router(intelligence_router, prefix="/api/v1")

    logger.info("intelligence_app_initialized", extra={"env": settings.app_env})
    return app


app = create_app()
