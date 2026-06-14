"""Bulk-upload orchestration for ``POST /items/bulk-upload``.

Parses a CSV or XLSX file and creates one item (+ matching subtype
detail) per row via :class:`~app.services.item_service.ItemService`.
Each row is processed independently — a row failure is recorded in the
report rather than aborting the request. Only request-level structural
problems (bad file type, missing columns, etc.) abort the whole request
via the usual :class:`AppError` -> global-handler path.
"""

from __future__ import annotations

import logging
import uuid

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, ValidationError
from app.schemas.bulk_upload import BulkUploadResult, BulkUploadRowResult, BulkUploadRowStatus
from app.schemas.item import ItemCreate
from app.services.item_service import ItemService
from app.utils.bulk_upload import (
    MAX_BULK_UPLOAD_ROWS,
    REQUIRED_COLUMNS,
    SUPPORTED_EXTENSIONS,
    get_extension,
    iter_csv_rows,
    iter_xlsx_rows,
    row_to_item_payload_dict,
)

logger = logging.getLogger(__name__)


class BulkUploadService:
    """Parses an uploaded file and bulk-creates items, one row at a time."""

    def __init__(self, session: AsyncSession) -> None:
        self._items = ItemService(session)

    async def process_file(
        self, *, filename: str, content: bytes, actor_id: uuid.UUID
    ) -> BulkUploadResult:
        """Parse ``content`` and create one item per data row.

        Raises :class:`ValidationError` (422) for structural problems
        with the file itself — these abort before any row is processed.
        Per-row data problems are reported in the returned
        :class:`BulkUploadResult` instead.
        """
        if not content:
            raise ValidationError("Uploaded file is empty", code="EMPTY_FILE")

        extension = get_extension(filename)
        if extension not in SUPPORTED_EXTENSIONS:
            raise ValidationError(
                f"Unsupported file type {extension!r}. Supported types: "
                f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}",
                code="UNSUPPORTED_FILE_TYPE",
            )

        headers, rows = iter_csv_rows(content) if extension == ".csv" else iter_xlsx_rows(content)

        missing = sorted(REQUIRED_COLUMNS - set(headers))
        if missing:
            raise ValidationError(
                f"Missing required column(s): {', '.join(missing)}",
                code="MISSING_REQUIRED_COLUMNS",
            )

        if not rows:
            raise ValidationError("Uploaded file has no data rows", code="EMPTY_FILE")

        if len(rows) > MAX_BULK_UPLOAD_ROWS:
            raise ValidationError(
                f"Too many rows ({len(rows)}); the maximum is {MAX_BULK_UPLOAD_ROWS}",
                code="TOO_MANY_ROWS",
            )

        results = [
            await self._process_row(row, row_number=offset + 2, actor_id=actor_id)
            for offset, row in enumerate(rows)
        ]

        created_count = sum(1 for result in results if result.status == BulkUploadRowStatus.CREATED)
        failed_count = len(results) - created_count
        logger.info(
            "bulk_upload_completed",
            extra={
                "total_rows": len(results),
                "created_count": created_count,
                "failed_count": failed_count,
            },
        )
        return BulkUploadResult(
            total_rows=len(results),
            created_count=created_count,
            failed_count=failed_count,
            results=results,
        )

    async def _process_row(
        self, row: dict[str, str], *, row_number: int, actor_id: uuid.UUID
    ) -> BulkUploadRowResult:
        """Validate and create one row, never raising — failures are returned."""
        data = row_to_item_payload_dict(row)
        sku = data.get("sku")

        try:
            payload = ItemCreate(**data)
        except PydanticValidationError as exc:
            return BulkUploadRowResult(
                row_number=row_number,
                sku=sku,
                status=BulkUploadRowStatus.FAILED,
                error_code="ROW_VALIDATION_ERROR",
                error_message=_format_pydantic_error(exc),
            )

        # Deliberate exception to "services don't catch AppError": each row
        # is an independent unit of the batch, so a child operation's
        # ConflictError/ValidationError becomes part of the report rather
        # than aborting the remaining rows.
        try:
            item = await self._items.create(payload, actor_id=actor_id)
        except AppError as exc:
            return BulkUploadRowResult(
                row_number=row_number,
                sku=sku,
                status=BulkUploadRowStatus.FAILED,
                error_code=exc.code,
                error_message=exc.message,
            )

        return BulkUploadRowResult(
            row_number=row_number,
            sku=sku,
            status=BulkUploadRowStatus.CREATED,
            item_id=item.id,
        )


def _format_pydantic_error(exc: PydanticValidationError) -> str:
    """Compact one-line summary of the first validation error."""
    errors = exc.errors()
    if not errors:
        return "Validation failed"
    first = errors[0]
    loc = ".".join(str(part) for part in first["loc"])
    msg = first["msg"]
    return f"{loc}: {msg}" if loc else msg
