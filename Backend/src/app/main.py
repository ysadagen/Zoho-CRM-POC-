"""FastAPI application factory for the Inventory Backend.

This module is intentionally small. Its only job is to wire together the
cross-cutting concerns (logging, exception handling, middleware) and
mount the API routers. Business logic and route handlers live elsewhere.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request

from app.api.v1.auth import router as auth_router
from app.api.v1.customers import router as customers_router
from app.api.v1.items import router as items_router
from app.api.v1.users import router as users_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.request_id import RequestIDMiddleware

logger = logging.getLogger(__name__)


def _build_error_response(exc: AppError, request_id: str | None) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
            }
        },
    )


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
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )

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
        return _build_error_response(exc, request_id)

    @app.get("/health", tags=["health"], summary="Liveness probe")
    async def health() -> dict[str, str]:
        """Return 200 OK if the process is running.

        This endpoint does not check downstream dependencies. Deeper
        readiness checks (DB connectivity, Integration Layer reachability)
        belong on separate endpoints when they are added.
        """
        return {"status": "ok"}

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(items_router, prefix="/api/v1")
    app.include_router(customers_router, prefix="/api/v1")

    logger.info("app_initialized", extra={"env": settings.app_env})
    return app


app = create_app()
