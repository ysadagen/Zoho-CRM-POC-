"""Schemas for ``POST /items/bulk-upload``.

The endpoint returns ``200`` with a per-row report even when some rows
fail — only request-level structural problems (bad file type, missing
required columns, etc.) are rejected with the standard error envelope.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel

__all__ = ["BulkUploadResult", "BulkUploadRowResult", "BulkUploadRowStatus"]


class BulkUploadRowStatus(StrEnum):
    """Outcome of processing a single row."""

    CREATED = "CREATED"
    FAILED = "FAILED"


class BulkUploadRowResult(BaseModel):
    """Outcome for a single row in the uploaded file.

    ``row_number`` is 1-based and counts the header row as row 1, so it
    matches the row a user sees when the file is open in a spreadsheet.
    """

    row_number: int
    sku: str | None = None
    status: BulkUploadRowStatus
    item_id: uuid.UUID | None = None
    error_code: str | None = None
    error_message: str | None = None


class BulkUploadResult(BaseModel):
    """Response envelope for ``POST /items/bulk-upload``."""

    total_rows: int
    created_count: int
    failed_count: int
    results: list[BulkUploadRowResult]
