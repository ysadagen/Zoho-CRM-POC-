"""Per-request access-log middleware.

Emits one structured INFO log line per HTTP request once the response is
generated, capturing method, path, status code, and elapsed time. The
``request_id`` bound by :class:`RequestIDMiddleware` is merged in automatically
via structlog contextvars.

This middleware must run *inside* :class:`RequestIDMiddleware` so the request
id is already in the context when the line is emitted. See ``main.py`` for the
registration order.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log one line per HTTP request with method, path, status, and latency."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
