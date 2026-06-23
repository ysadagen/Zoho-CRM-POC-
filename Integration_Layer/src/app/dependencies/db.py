"""Database dependency re-export.

Routes and other dependencies import :func:`get_db` from here so the wiring
point is uniform across the service, even though the implementation lives in
``core/database.py``.
"""

from __future__ import annotations

from app.core.database import get_db

__all__ = ["get_db"]
