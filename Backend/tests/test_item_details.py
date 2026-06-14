"""Tests for the Phase-0 pharma additions on /api/v1/items.

Covers the common-pharma fields (``storage_condition`` / ``shelf_life_days``)
on the item create/read/update surface, and the 1:1 invariant that every
item owns exactly one subtype detail row.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finished_item_detail import FinishedItemDetail
from app.models.item import Item
from app.models.raw_item_detail import RawItemDetail

ITEMS_URL = "/api/v1/items"


def _raw_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "sku": f"RAW-{uuid.uuid4().hex[:8]}",
        "name": "Paracetamol API",
        "type": "RAW",
        "category": "Active",
        "unit_of_measure": "kg",
        "unit_price": "500.00",
    }
    base.update(overrides)
    return base


def _finished_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "sku": f"FIN-{uuid.uuid4().hex[:8]}",
        "name": "Paracetamol 500mg Tablet",
        "type": "FINISHED",
        "category": "Analgesic",
        "unit_of_measure": "strip",
        "unit_price": "20.00",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1:1 detail-row invariant
# ---------------------------------------------------------------------------


async def test_creating_raw_item_creates_one_raw_detail_row(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    resp = await authenticated_client.post(ITEMS_URL, json=_raw_payload())
    assert resp.status_code == 201, resp.text
    item_id = uuid.UUID(resp.json()["id"])

    raw = await db_session.scalar(select(RawItemDetail).where(RawItemDetail.item_id == item_id))
    finished = await db_session.scalar(
        select(FinishedItemDetail).where(FinishedItemDetail.item_id == item_id)
    )
    assert raw is not None
    assert raw.is_hazardous is False
    assert raw.material_classification is None  # unset until Phase 1
    assert finished is None  # never both


async def test_creating_finished_item_creates_one_finished_detail_row(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    resp = await authenticated_client.post(ITEMS_URL, json=_finished_payload())
    assert resp.status_code == 201, resp.text
    item_id = uuid.UUID(resp.json()["id"])

    finished = await db_session.scalar(
        select(FinishedItemDetail).where(FinishedItemDetail.item_id == item_id)
    )
    raw = await db_session.scalar(select(RawItemDetail).where(RawItemDetail.item_id == item_id))
    assert finished is not None
    assert finished.is_prescription_required is False
    assert raw is None


async def test_detail_row_audit_matches_creating_actor(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    resp = await authenticated_client.post(ITEMS_URL, json=_raw_payload())
    item_id = uuid.UUID(resp.json()["id"])

    item = await db_session.scalar(select(Item).where(Item.id == item_id))
    raw = await db_session.scalar(select(RawItemDetail).where(RawItemDetail.item_id == item_id))
    assert item is not None and raw is not None
    assert raw.created_by_user_id == item.created_by_user_id
    assert raw.updated_by_user_id == item.updated_by_user_id


# ---------------------------------------------------------------------------
# Common-pharma fields on the item surface
# ---------------------------------------------------------------------------


async def test_storage_condition_and_shelf_life_persist(
    authenticated_client: AsyncClient,
) -> None:
    payload = _finished_payload(storage_condition="COLD_CHAIN_2_8", shelf_life_days=365)
    create = await authenticated_client.post(ITEMS_URL, json=payload)
    assert create.status_code == 201, create.text
    item_id = create.json()["id"]

    body = (await authenticated_client.get(f"{ITEMS_URL}/{item_id}")).json()
    assert body["storage_condition"] == "COLD_CHAIN_2_8"
    assert body["shelf_life_days"] == 365


async def test_pharma_fields_default_to_null_when_omitted(
    authenticated_client: AsyncClient,
) -> None:
    create = await authenticated_client.post(ITEMS_URL, json=_raw_payload())
    item_id = create.json()["id"]

    body = (await authenticated_client.get(f"{ITEMS_URL}/{item_id}")).json()
    assert body["storage_condition"] is None
    assert body["shelf_life_days"] is None


async def test_patch_updates_pharma_fields(
    authenticated_client: AsyncClient,
) -> None:
    item_id = (await authenticated_client.post(ITEMS_URL, json=_raw_payload())).json()["id"]

    patch = await authenticated_client.patch(
        f"{ITEMS_URL}/{item_id}",
        json={"storage_condition": "AMBIENT", "shelf_life_days": 90},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["storage_condition"] == "AMBIENT"
    assert patch.json()["shelf_life_days"] == 90


async def test_negative_shelf_life_rejected_with_422(
    authenticated_client: AsyncClient,
) -> None:
    resp = await authenticated_client.post(ITEMS_URL, json=_raw_payload(shelf_life_days=-1))
    assert resp.status_code == 422


async def test_invalid_storage_condition_rejected_with_422(
    authenticated_client: AsyncClient,
) -> None:
    resp = await authenticated_client.post(
        ITEMS_URL, json=_raw_payload(storage_condition="DEEP_SPACE")
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Phase 1A — subtype detail blocks via the item API
# ---------------------------------------------------------------------------


async def test_create_raw_item_with_detail_persists_and_reads_back(
    authenticated_client: AsyncClient,
) -> None:
    payload = _raw_payload(
        raw_detail={"material_classification": "API", "pharmacopoeia": "IP", "is_hazardous": True}
    )
    create = await authenticated_client.post(ITEMS_URL, json=payload)
    assert create.status_code == 201, create.text

    body = (await authenticated_client.get(f"{ITEMS_URL}/{create.json()['id']}")).json()
    assert body["raw_detail"]["material_classification"] == "API"
    assert body["raw_detail"]["pharmacopoeia"] == "IP"
    assert body["raw_detail"]["is_hazardous"] is True
    assert body["finished_detail"] is None


async def test_create_finished_item_with_detail(
    authenticated_client: AsyncClient,
) -> None:
    payload = _finished_payload(
        finished_detail={
            "generic_name": "Paracetamol",
            "strength": "500 mg",
            "dosage_form": "TABLET",
            "selling_price": "18.00",
            "mrp": "25.00",
            "drug_schedule": "H",
            "is_prescription_required": True,
        }
    )
    create = await authenticated_client.post(ITEMS_URL, json=payload)
    assert create.status_code == 201, create.text

    detail = (await authenticated_client.get(f"{ITEMS_URL}/{create.json()['id']}")).json()[
        "finished_detail"
    ]
    assert detail["generic_name"] == "Paracetamol"
    assert detail["dosage_form"] == "TABLET"
    assert detail["drug_schedule"] == "H"
    assert detail["is_prescription_required"] is True
    assert Decimal(str(detail["mrp"])) == Decimal("25.00")
    assert Decimal(str(detail["selling_price"])) == Decimal("18.00")


async def test_create_with_mismatched_detail_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    resp = await authenticated_client.post(
        ITEMS_URL, json=_raw_payload(finished_detail={"generic_name": "Nope"})
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "ITEM_DETAIL_TYPE_MISMATCH"


async def test_create_with_invalid_detail_enum_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    resp = await authenticated_client.post(
        ITEMS_URL, json=_raw_payload(raw_detail={"material_classification": "PLUTONIUM"})
    )
    assert resp.status_code == 422


async def test_create_with_unknown_detail_field_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    resp = await authenticated_client.post(
        ITEMS_URL, json=_raw_payload(raw_detail={"made_up_field": "x"})
    )
    assert resp.status_code == 422


async def test_patch_detail_updates_fields(
    authenticated_client: AsyncClient,
) -> None:
    item_id = (await authenticated_client.post(ITEMS_URL, json=_raw_payload())).json()["id"]

    patch = await authenticated_client.patch(
        f"{ITEMS_URL}/{item_id}",
        json={"raw_detail": {"material_classification": "EXCIPIENT", "is_hazardous": True}},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["raw_detail"]["material_classification"] == "EXCIPIENT"
    assert patch.json()["raw_detail"]["is_hazardous"] is True


async def test_patch_detail_is_partial(
    authenticated_client: AsyncClient,
) -> None:
    item_id = (
        await authenticated_client.post(
            ITEMS_URL,
            json=_raw_payload(raw_detail={"material_classification": "API", "is_hazardous": True}),
        )
    ).json()["id"]

    await authenticated_client.patch(
        f"{ITEMS_URL}/{item_id}", json={"raw_detail": {"is_hazardous": False}}
    )

    detail = (await authenticated_client.get(f"{ITEMS_URL}/{item_id}")).json()["raw_detail"]
    assert detail["material_classification"] == "API"  # untouched
    assert detail["is_hazardous"] is False  # changed


async def test_patch_mismatched_detail_returns_422(
    authenticated_client: AsyncClient,
) -> None:
    item_id = (await authenticated_client.post(ITEMS_URL, json=_raw_payload())).json()["id"]

    patch = await authenticated_client.patch(
        f"{ITEMS_URL}/{item_id}", json={"finished_detail": {"generic_name": "Nope"}}
    )
    assert patch.status_code == 422
    assert patch.json()["error"]["code"] == "ITEM_DETAIL_TYPE_MISMATCH"


async def test_list_items_includes_matching_detail_only(
    authenticated_client: AsyncClient,
) -> None:
    await authenticated_client.post(
        ITEMS_URL, json=_raw_payload(raw_detail={"material_classification": "API"})
    )
    await authenticated_client.post(
        ITEMS_URL, json=_finished_payload(finished_detail={"dosage_form": "SYRUP"})
    )

    items = (await authenticated_client.get(ITEMS_URL)).json()["items"]
    assert len(items) == 2
    for it in items:
        if it["type"] == "RAW":
            assert it["raw_detail"] is not None and it["finished_detail"] is None
        else:
            assert it["finished_detail"] is not None and it["raw_detail"] is None
