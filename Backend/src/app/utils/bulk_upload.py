"""Stateless parsing/normalization helpers for ``POST /items/bulk-upload``.

Kept free of any DB session so they're trivially unit-testable; the
session-owning orchestration lives in
:class:`app.services.bulk_upload_service.BulkUploadService`.
"""

from __future__ import annotations

import csv
import io
from itertools import zip_longest
from pathlib import Path
from typing import Any

import openpyxl

__all__ = [
    "FINISHED_DETAIL_COLUMNS",
    "MAX_BULK_UPLOAD_ROWS",
    "RAW_DETAIL_COLUMNS",
    "REQUIRED_COLUMNS",
    "SUPPORTED_EXTENSIONS",
    "get_extension",
    "iter_csv_rows",
    "iter_xlsx_rows",
    "normalize_headers",
    "row_to_item_payload_dict",
]

# Caps the number of data rows processed per request — bounds the
# request's runtime (each row does its own DB round-trip via
# ItemService.create) and memory footprint.
MAX_BULK_UPLOAD_ROWS = 500

SUPPORTED_EXTENSIONS = frozenset({".csv", ".xlsx"})

# Columns every row must provide — the rest of ItemCreate's fields are
# optional and fall back to schema defaults when the cell is empty.
REQUIRED_COLUMNS = frozenset({"sku", "name", "type", "category", "unit_of_measure", "unit_price"})

# Subtype-detail columns, only consumed for rows whose ``type`` matches.
RAW_DETAIL_COLUMNS = ("material_classification", "pharmacopoeia", "is_hazardous")
FINISHED_DETAIL_COLUMNS = (
    "generic_name",
    "brand_name",
    "strength",
    "dosage_form",
    "pack_size",
    "ingredients",
    "container_specification",
    "selling_price",
    "license_number",
    "registration_code",
    "mrp",
    "drug_schedule",
    "is_prescription_required",
)

# Columns whose values are validated against a StrEnum — normalize case
# so "raw"/"Raw"/"RAW" all map to the enum member "RAW".
_ENUM_COLUMNS = frozenset(
    {
        "type",
        "storage_condition",
        "material_classification",
        "pharmacopoeia",
        "dosage_form",
        "drug_schedule",
    }
)

# Common (type-independent) optional ItemCreate columns.
_COMMON_OPTIONAL_COLUMNS = (
    "description",
    "stock_quantity",
    "reorder_threshold",
    "shelf_life_days",
)


def get_extension(filename: str) -> str:
    """Return the lowercased file extension, e.g. ``".csv"``."""
    return Path(filename).suffix.lower()


def normalize_headers(headers: list[Any]) -> list[str]:
    """Lowercase + strip header cells for case-insensitive column matching."""
    return [str(header).strip().lower() for header in headers]


def iter_csv_rows(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Parse CSV bytes into ``(normalized_headers, rows)``.

    Decodes as ``utf-8-sig`` so a leading BOM doesn't get attached to the
    first header name. Blank lines are skipped.
    """
    text = content.decode("utf-8-sig")
    raw_rows = list(csv.reader(io.StringIO(text)))
    if not raw_rows:
        return [], []
    headers = normalize_headers(raw_rows[0])
    rows: list[dict[str, str]] = []
    for raw_row in raw_rows[1:]:
        if not any(cell.strip() for cell in raw_row):
            continue
        rows.append(dict(zip_longest(headers, raw_row, fillvalue="")))
    return headers, rows


def iter_xlsx_rows(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Parse XLSX bytes into ``(normalized_headers, rows)``.

    Reads the first (active) worksheet. Numeric cells are stringified —
    whole-number floats (as openpyxl returns for integer-looking cells)
    are rendered without a trailing ``.0`` so they parse cleanly as
    ``int`` fields (e.g. ``shelf_life_days``).
    """
    workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        sheet = workbook.active
        if sheet is None:
            return [], []
        rows_iter = sheet.iter_rows(values_only=True)
        try:
            header_row = next(rows_iter)
        except StopIteration:
            return [], []
        headers = normalize_headers(list(header_row))
        rows: list[dict[str, str]] = []
        for raw_row in rows_iter:
            if all(cell is None for cell in raw_row):
                continue
            values = [_cell_to_str(cell) for cell in raw_row]
            rows.append(dict(zip_longest(headers, values, fillvalue="")))
        return headers, rows
    finally:
        workbook.close()


def _cell_to_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _clean(raw: str | None) -> str | None:
    """Strip whitespace; treat an empty result as absent."""
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _clean_value(column: str, raw: str | None) -> str | None:
    value = _clean(raw)
    if value is not None and column in _ENUM_COLUMNS:
        value = value.upper()
    return value


def row_to_item_payload_dict(row: dict[str, str]) -> dict[str, Any]:
    """Map one normalized row to a nested dict suitable for ``ItemCreate(**data)``.

    Only the subtype-detail block matching the row's (normalized)
    ``type`` value is built — columns for the other subtype are ignored,
    so a single wide file covering both RAW and FINISHED rows doesn't
    trigger a spurious ``ITEM_DETAIL_TYPE_MISMATCH``.
    """
    data: dict[str, Any] = {}

    item_columns = (
        "sku",
        "name",
        "type",
        "category",
        "unit_of_measure",
        "unit_price",
        *_COMMON_OPTIONAL_COLUMNS,
    )
    for column in item_columns:
        value = _clean_value(column, row.get(column))
        if value is not None:
            data[column] = value

    item_type = data.get("type")
    if item_type == "RAW":
        detail = _build_detail_dict(row, RAW_DETAIL_COLUMNS)
        if detail:
            data["raw_detail"] = detail
    elif item_type == "FINISHED":
        detail = _build_detail_dict(row, FINISHED_DETAIL_COLUMNS)
        if detail:
            data["finished_detail"] = detail

    return data


def _build_detail_dict(row: dict[str, str], columns: tuple[str, ...]) -> dict[str, Any]:
    detail: dict[str, Any] = {}
    for column in columns:
        value = _clean_value(column, row.get(column))
        if value is not None:
            detail[column] = value
    return detail
