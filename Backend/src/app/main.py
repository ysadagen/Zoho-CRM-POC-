"""FastAPI application factory for the Inventory Backend.

This module is intentionally small. Its only job is to wire together the
cross-cutting concerns (logging, exception handling, middleware) and
mount the API routers. Business logic and route handlers live elsewhere.
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

from app.api.v1.activities import router as activities_router
from app.api.v1.auth import router as auth_router
from app.api.v1.batches import router as batches_router
from app.api.v1.customer_targets import router as customer_targets_router
from app.api.v1.customers import router as customers_router
from app.api.v1.ingest import router as ingest_router
from app.api.v1.invoices import router as invoices_router
from app.api.v1.items import router as items_router
from app.api.v1.leads import router as leads_router
from app.api.v1.purchase_orders import router as purchase_orders_router
from app.api.v1.sales_orders import router as sales_orders_router
from app.api.v1.stock_movements import router as stock_movements_router
from app.api.v1.users import router as users_router
from app.api.v1.vendor_terms import router as vendor_terms_router
from app.api.v1.vendors import router as vendors_router
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AppError, ServiceUnavailableError
from app.core.logging import configure_logging
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.request_id import RequestIDMiddleware

logger = logging.getLogger(__name__)

# Allowed request headers under CORS. Enumerated rather than ``["*"]``
# because the wildcard is silently rejected by Chrome when
# ``allow_credentials=True``. Add to this list when a new client-set
# header is introduced.
_ALLOWED_CORS_HEADERS: list[str] = [
    "Authorization",
    "Content-Type",
    "X-Request-ID",
]


def _build_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str | None,
    details: Any = None,
) -> JSONResponse:
    """Build the canonical error envelope.

    The shape ``{"error": {"code", "message", "request_id"}}`` is the
    Backend's public contract for every non-2xx response. ``details``
    is optional and is currently used only by the validation handler
    to surface FastAPI's per-field error list — additive, so clients
    that ignore it continue to work.
    """
    body: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request_id,
    }
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


# Reused dependency alias for the readiness probe. Must live at MODULE
# scope (not inside ``create_app``) so ``get_type_hints`` can resolve it
# under ``from __future__ import annotations`` — local aliases are
# invisible to the resolver, and FastAPI silently degrades them to
# query parameters, which is a very confusing failure mode.
_ReadySession = Annotated[AsyncSession, Depends(get_db)]


def create_app() -> FastAPI:
    """Build and return a fully wired FastAPI application."""
    settings = get_settings()
    configure_logging(env=settings.app_env, level=settings.log_level)

    app = FastAPI(
        title="Inventory Backend",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "prod" else None,
        redoc_url=None,
    )

    # Middleware is LIFO in Starlette: the LAST one added is the OUTERMOST and
    # runs first on incoming requests. RequestIDMiddleware must run before
    # AccessLogMiddleware so the request_id is bound to the structlog context
    # by the time the access line is emitted. CORS sits OUTERMOST so the
    # preflight short-circuit happens before any of our middleware runs.
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=_ALLOWED_CORS_HEADERS,
            expose_headers=["X-Request-ID"],
        )
    else:
        # In non-dev environments an empty allow-list is almost certainly
        # misconfiguration — flag it loudly so it isn't discovered by the
        # frontend's first preflight request to staging or prod.
        log_method = logger.warning if settings.app_env != "dev" else logger.info
        log_method(
            "cors_origins_empty",
            extra={
                "env": settings.app_env,
                "hint": "Set CORS_ALLOWED_ORIGINS in the environment if a "
                "browser client needs to call this Backend.",
            },
        )

    # --- Exception handlers ---------------------------------------------------
    # All paths converge on the same `{error: {code, message, request_id}}`
    # envelope so the Frontend can parse one shape regardless of failure cause.

    @app.exception_handler(AppError)
    async def handle_app_exception(request: Request, exc: AppError) -> JSONResponse:
        request_id: str | None = getattr(request.state, "request_id", None)
        logger.warning(
            "app_exception",
            extra={
                "code": exc.code,
                "status_code": exc.status_code,
                "path": request.url.path,
            },
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
        """Map Pydantic / FastAPI validation failures to the project envelope.

        Adds ``details`` carrying FastAPI's native ``loc/msg/type`` list so
        the Frontend can attach errors to specific form fields without
        having to parse a custom format.
        """
        request_id: str | None = getattr(request.state, "request_id", None)
        raw_errors = exc.errors()
        # FastAPI's errors may include non-JSON-serialisable bits (e.g. ctx
        # holding exception instances). Strip to a safe, stable shape.
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
            # Starlette renamed HTTP_422_UNPROCESSABLE_ENTITY to
            # HTTP_422_UNPROCESSABLE_CONTENT (RFC 9110 wording). Keep the
            # new spelling so we don't emit a DeprecationWarning per
            # validation failure.
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="VALIDATION_ERROR",
            message=_format_validation_message(raw_errors),
            request_id=request_id,
            details=details,
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        """Last-resort handler — anything not explicitly caught becomes 500.

        Logged at ERROR with the exception chain so the cause is
        recoverable from logs by the ``request_id`` returned in the
        envelope. Message is deliberately generic so internal details
        (stack frames, library names) don't leak to clients.
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

    # --- Probes ---------------------------------------------------------------
    # /health is liveness: "is this process alive?" — answers fast, never
    # depends on a downstream. /ready is readiness: "should the orchestrator
    # send traffic to this pod?" — does a DB ping under a strict timeout.
    # k8s and similar use different probes for these; conflating them sends
    # traffic to half-broken pods.

    @app.get("/health", tags=["health"], summary="Liveness probe")
    async def health() -> dict[str, str]:
        """Return 200 OK if the process is running. No dependency checks."""
        return {"status": "ok"}

    @app.get("/ready", tags=["health"], summary="Readiness probe")
    async def ready(session: _ReadySession) -> dict[str, str]:
        """Return 200 only if the Backend can serve real traffic.

        Probes the database with ``SELECT 1`` under a 1-second timeout.
        Anything else (timeout, connection refused, auth failure) is a
        503 ``SERVICE_UNAVAILABLE`` so a k8s readiness probe routes
        traffic away from this pod until it recovers.
        """
        try:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=1.0)
        except (TimeoutError, SQLAlchemyError, OSError) as exc:
            logger.warning("readiness_probe_failed", extra={"error": str(exc)})
            raise ServiceUnavailableError("Database unreachable", code="DB_UNAVAILABLE") from exc
        return {"status": "ready"}

    # --- Routers --------------------------------------------------------------

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(items_router, prefix="/api/v1")
    app.include_router(customers_router, prefix="/api/v1")
    app.include_router(customer_targets_router, prefix="/api/v1")
    app.include_router(vendors_router, prefix="/api/v1")
    app.include_router(vendor_terms_router, prefix="/api/v1")
    app.include_router(stock_movements_router, prefix="/api/v1")
    app.include_router(batches_router, prefix="/api/v1")
    app.include_router(purchase_orders_router, prefix="/api/v1")
    app.include_router(sales_orders_router, prefix="/api/v1")
    app.include_router(leads_router, prefix="/api/v1")
    app.include_router(activities_router, prefix="/api/v1")
    app.include_router(invoices_router, prefix="/api/v1")
    app.include_router(ingest_router, prefix="/api/v1")

    logger.info("app_initialized", extra={"env": settings.app_env})
    return app


app = create_app()
