"""Tests for /api/v1/items/bulk-upload — CSV/XLSX bulk item creation."""

from __future__ import annotations

import csv
import io
from decimal import Decimal

import openpyxl
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finished_item_detail import FinishedItemDetail
from app.models.item import Item
from app.models.raw_item_detail import RawItemDetail
from app.utils.bulk_upload import MAX_BULK_UPLOAD_ROWS

ITEMS_URL = "/api/v1/items"
BULK_UPLOAD_URL = "/api/v1/items/bulk-upload"

ALL_COLUMNS = [
    "sku",
    "name",
    "type",
    "category",
    "unit_of_measure",
    "unit_price",
    "description",
    "stock_quantity",
    "reorder_threshold",
    "storage_condition",
    "shelf_life_days",
    "material_classification",
    "pharmacopoeia",
    "is_hazardous",
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
]


def _raw_row(**overrides: str) -> dict[str, str]:
    base: dict[str, str] = {
        "sku": "BULK-RAW-0001",
        "name": "Bulk Raw Pellets",
        "type": "RAW",
        "category": "Polymer",
        "unit_of_measure": "kg",
        "unit_price": "82.00",
        "material_classification": "API",
        "pharmacopoeia": "IP",
        "is_hazardous": "true",
    }
    base.update(overrides)
    return base


def _finished_row(**overrides: str) -> dict[str, str]:
    base: dict[str, str] = {
        "sku": "BULK-FIN-0001",
        "name": "Bulk Finished Bottle",
        "type": "FINISHED",
        "category": "Beverage",
        "unit_of_measure": "pcs",
        "unit_price": "18.50",
        "dosage_form": "TABLET",
        "mrp": "25.00",
    }
    base.update(overrides)
    return base


def _csv_bytes(
    rows: list[dict[str, str]], headers: list[str] | None = None, *, bom: bool = False
) -> bytes:
    """Build CSV bytes with the given header row, populated from ``rows``.

    Each row dict's keys are matched case-insensitively against
    ``headers`` so callers can pass uppercase/mixed-case headers while
    using the lowercase row builders above.
    """
    canonical_headers = headers if headers is not None else ALL_COLUMNS
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(canonical_headers)
    for row in rows:
        writer.writerow([row.get(header.lower(), "") for header in canonical_headers])
    encoded = buffer.getvalue().encode("utf-8")
    return b"\xef\xbb\xbf" + encoded if bom else encoded


def _xlsx_bytes(rows: list[dict[str, str]], headers: list[str] | None = None) -> bytes:
    canonical_headers = headers if headers is not None else ALL_COLUMNS
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(canonical_headers)
    for row in rows:
        sheet.append([row.get(header.lower(), "") for header in canonical_headers])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def test_bulk_upload_requires_auth_returns_401(client_with_db: AsyncClient) -> None:
    content = _csv_bytes([_raw_row()])
    response = await client_with_db.post(
        BULK_UPLOAD_URL, files={"file": ("items.csv", content, "text/csv")}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_bulk_upload_csv_creates_raw_and_finished_items(
    authenticated_client: AsyncClient, db_session: AsyncSession
) -> None:
    content = _csv_bytes([_raw_row(), _finished_row()])

    response = await authenticated_client.post(
        BULK_UPLOAD_URL, files={"file": ("items.csv", content, "text/csv")}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 2
    assert body["created_count"] == 2
    assert body["failed_count"] == 0
    for result in body["results"]:
        assert result["status"] == "CREATED"
        assert result["item_id"] is not None

    raw_item = await db_session.scalar(select(Item).where(Item.sku == "BULK-RAW-0001"))
    assert raw_item is not None
    raw_detail = await db_session.scalar(
        select(RawItemDetail).where(RawItemDetail.item_id == raw_item.id)
    )
    assert raw_detail is not None
    assert raw_detail.material_classification == "API"
    assert raw_detail.pharmacopoeia == "IP"
    assert raw_detail.is_hazardous is True

    finished_item = await db_session.scalar(select(Item).where(Item.sku == "BULK-FIN-0001"))
    assert finished_item is not None
    finished_detail = await db_session.scalar(
        select(FinishedItemDetail).where(FinishedItemDetail.item_id == finished_item.id)
    )
    assert finished_detail is not None
    assert finished_detail.dosage_form == "TABLET"
    assert Decimal(str(finished_detail.mrp)) == Decimal("25.00")


async def test_bulk_upload_csv_handles_utf8_bom(authenticated_client: AsyncClient) -> None:
    content = _csv_bytes([_raw_row(sku="BULK-BOM-0001")], bom=True)

    response = await authenticated_client.post(
        BULK_UPLOAD_URL, files={"file": ("items.csv", content, "text/csv")}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created_count"] == 1
    assert body["results"][0]["sku"] == "BULK-BOM-0001"
    assert body["results"][0]["status"] == "CREATED"


async def test_bulk_upload_normalizes_enum_casing(authenticated_client: AsyncClient) -> None:
    row = _raw_row(
        sku="BULK-CASE-0001",
        type="raw",
        storage_condition="ambient",
        material_classification="api",
        pharmacopoeia="ip",
    )
    content = _csv_bytes([row])

    response = await authenticated_client.post(
        BULK_UPLOAD_URL, files={"file": ("items.csv", content, "text/csv")}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created_count"] == 1
    assert body["results"][0]["status"] == "CREATED"


async def test_bulk_upload_normalizes_empty_optional_fields(
    authenticated_client: AsyncClient, db_session: AsyncSession
) -> None:
    row = _raw_row(
        sku="BULK-EMPTY-0001", description="", reorder_threshold="", storage_condition=""
    )
    content = _csv_bytes([row])

    response = await authenticated_client.post(
        BULK_UPLOAD_URL, files={"file": ("items.csv", content, "text/csv")}
    )

    assert response.status_code == 200
    assert response.json()["created_count"] == 1

    item = await db_session.scalar(select(Item).where(Item.sku == "BULK-EMPTY-0001"))
    assert item is not None
    assert item.description is None
    assert item.reorder_threshold is None
    assert item.storage_condition is None


async def test_bulk_upload_xlsx_creates_items(authenticated_client: AsyncClient) -> None:
    content = _xlsx_bytes([_raw_row(sku="BULK-XLSX-0001"), _finished_row(sku="BULK-XLSX-0002")])

    response = await authenticated_client.post(
        BULK_UPLOAD_URL,
        files={
            "file": (
                "items.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 2
    assert body["created_count"] == 2
    assert body["failed_count"] == 0


# ---------------------------------------------------------------------------
# Mixed success/failure
# ---------------------------------------------------------------------------


async def test_bulk_upload_mixed_success_and_failure_rows(
    authenticated_client: AsyncClient,
) -> None:
    rows = [
        _raw_row(sku="BULK-MIX-OK"),
        _raw_row(sku="BULK-MIX-NOPRICE", unit_price=""),
        _raw_row(sku="BULK-MIX-BADTYPE", type="WIDGET"),
    ]
    content = _csv_bytes(rows)

    response = await authenticated_client.post(
        BULK_UPLOAD_URL, files={"file": ("items.csv", content, "text/csv")}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 3
    assert body["created_count"] == 1
    assert body["failed_count"] == 2

    by_sku = {result["sku"]: result for result in body["results"]}

    assert by_sku["BULK-MIX-OK"]["status"] == "CREATED"
    assert by_sku["BULK-MIX-OK"]["item_id"] is not None

    assert by_sku["BULK-MIX-NOPRICE"]["status"] == "FAILED"
    assert by_sku["BULK-MIX-NOPRICE"]["error_code"] == "ROW_VALIDATION_ERROR"
    assert by_sku["BULK-MIX-NOPRICE"]["item_id"] is None

    assert by_sku["BULK-MIX-BADTYPE"]["status"] == "FAILED"
    assert by_sku["BULK-MIX-BADTYPE"]["error_code"] == "ROW_VALIDATION_ERROR"
    assert by_sku["BULK-MIX-BADTYPE"]["item_id"] is None


async def test_bulk_upload_continues_after_conflict_with_existing_item(
    authenticated_client: AsyncClient,
) -> None:
    existing = _raw_row(sku="BULK-DUP-EXISTING")
    create_response = await authenticated_client.post(
        ITEMS_URL,
        json={
            "sku": existing["sku"],
            "name": existing["name"],
            "type": existing["type"],
            "category": existing["category"],
            "unit_of_measure": existing["unit_of_measure"],
            "unit_price": existing["unit_price"],
        },
    )
    assert create_response.status_code == 201

    content = _csv_bytes([_raw_row(sku="BULK-DUP-EXISTING"), _raw_row(sku="BULK-DUP-FRESH")])

    response = await authenticated_client.post(
        BULK_UPLOAD_URL, files={"file": ("items.csv", content, "text/csv")}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created_count"] == 1
    assert body["failed_count"] == 1

    by_sku = {result["sku"]: result for result in body["results"]}
    assert by_sku["BULK-DUP-EXISTING"]["status"] == "FAILED"
    assert by_sku["BULK-DUP-EXISTING"]["error_code"] == "SKU_ALREADY_EXISTS"
    assert by_sku["BULK-DUP-FRESH"]["status"] == "CREATED"


async def test_bulk_upload_duplicate_sku_within_same_file(
    authenticated_client: AsyncClient,
) -> None:
    content = _csv_bytes(
        [_raw_row(sku="BULK-DUP-SAME"), _raw_row(sku="BULK-DUP-SAME", name="Second Row")]
    )

    response = await authenticated_client.post(
        BULK_UPLOAD_URL, files={"file": ("items.csv", content, "text/csv")}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created_count"] == 1
    assert body["failed_count"] == 1
    assert body["results"][0]["status"] == "CREATED"
    assert body["results"][1]["status"] == "FAILED"
    assert body["results"][1]["error_code"] == "SKU_ALREADY_EXISTS"


# ---------------------------------------------------------------------------
# Request-level rejections
# ---------------------------------------------------------------------------


async def test_bulk_upload_rejects_unsupported_extension(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(
        BULK_UPLOAD_URL, files={"file": ("items.txt", b"sku,name\n", "text/plain")}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    assert "results" not in body


async def test_bulk_upload_rejects_empty_file(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post(
        BULK_UPLOAD_URL, files={"file": ("items.csv", b"", "text/csv")}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EMPTY_FILE"


async def test_bulk_upload_rejects_header_only_csv(authenticated_client: AsyncClient) -> None:
    content = _csv_bytes([])

    response = await authenticated_client.post(
        BULK_UPLOAD_URL, files={"file": ("items.csv", content, "text/csv")}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EMPTY_FILE"


async def test_bulk_upload_rejects_missing_required_columns(
    authenticated_client: AsyncClient,
) -> None:
    headers = [header for header in ALL_COLUMNS if header != "unit_price"]
    content = _csv_bytes([_raw_row()], headers=headers)

    response = await authenticated_client.post(
        BULK_UPLOAD_URL, files={"file": ("items.csv", content, "text/csv")}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "MISSING_REQUIRED_COLUMNS"
    assert "unit_price" in body["error"]["message"]


async def test_bulk_upload_rejects_too_many_rows(authenticated_client: AsyncClient) -> None:
    rows = [_raw_row(sku=f"BULK-MANY-{i:04d}") for i in range(MAX_BULK_UPLOAD_ROWS + 1)]
    content = _csv_bytes(rows)

    response = await authenticated_client.post(
        BULK_UPLOAD_URL, files={"file": ("items.csv", content, "text/csv")}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TOO_MANY_ROWS"


# ---------------------------------------------------------------------------
# Header case-insensitivity
# ---------------------------------------------------------------------------


async def test_bulk_upload_accepts_uppercase_or_mixed_case_headers(
    authenticated_client: AsyncClient,
) -> None:
    headers = [header.upper() for header in ALL_COLUMNS]
    content = _csv_bytes([_raw_row(sku="BULK-CASE-HEADER")], headers=headers)

    response = await authenticated_client.post(
        BULK_UPLOAD_URL, files={"file": ("items.csv", content, "text/csv")}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created_count"] == 1
    assert body["results"][0]["status"] == "CREATED"
