"""DB-level invariant tests for the ``batches`` table and the new
``stock_movements.batch_id`` link (CLAUDE.md §10.3 — every invariant is
paired with a test that bypasses the API and asserts the database itself
enforces it).

These tests construct ORM rows directly against ``db_session`` (no API
path exists yet — batch CRUD is Phase 1) and assert the CHECK / UNIQUE /
NOT NULL / FK constraints fire.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import Batch, BatchStatus
from app.models.item import Item
from app.models.stock_movement import MovementDirection, MovementReason, StockMovement

ITEMS_URL = "/api/v1/items"


async def _seed_item(client: AsyncClient, db_session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Create an item via the API and return ``(item_id, actor_user_id)``.

    Piggybacks on the authenticated client so the audit FK user exists;
    the batch rows reuse that user for their own audit columns.
    """
    resp = await client.post(
        ITEMS_URL,
        json={
            "sku": f"RAW-{uuid.uuid4().hex[:8]}",
            "name": "Amoxicillin API",
            "type": "RAW",
            "category": "Active",
            "unit_of_measure": "kg",
            "unit_price": "750.00",
        },
    )
    assert resp.status_code == 201, resp.text
    item_id = uuid.UUID(resp.json()["id"])
    item = await db_session.scalar(select(Item).where(Item.id == item_id))
    assert item is not None
    return item_id, item.created_by_user_id


def _batch(item_id: uuid.UUID, actor_id: uuid.UUID, **overrides: object) -> Batch:
    base: dict[str, object] = {
        "item_id": item_id,
        "batch_number": "B-0001",
        "expiry_date": date(2030, 1, 1),
        "quantity": Decimal("100"),
        "initial_quantity": Decimal("100"),
        "created_by_user_id": actor_id,
        "updated_by_user_id": actor_id,
    }
    base.update(overrides)
    return Batch(**base)


# ---------------------------------------------------------------------------
# batches constraints
# ---------------------------------------------------------------------------


async def test_batch_status_defaults_to_quarantine(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    item_id, actor_id = await _seed_item(authenticated_client, db_session)
    batch = _batch(item_id, actor_id)
    db_session.add(batch)
    await db_session.flush()
    await db_session.refresh(batch)
    assert batch.batch_status is BatchStatus.QUARANTINE


async def test_duplicate_batch_number_per_item_rejected(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    item_id, actor_id = await _seed_item(authenticated_client, db_session)
    db_session.add(_batch(item_id, actor_id, batch_number="LOT-A"))
    await db_session.flush()

    db_session.add(_batch(item_id, actor_id, batch_number="LOT-A"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_negative_batch_quantity_rejected(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    item_id, actor_id = await _seed_item(authenticated_client, db_session)
    db_session.add(_batch(item_id, actor_id, quantity=Decimal("-1")))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_expiry_before_manufacturing_rejected(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    item_id, actor_id = await _seed_item(authenticated_client, db_session)
    db_session.add(
        _batch(
            item_id,
            actor_id,
            manufacturing_date=date(2030, 6, 1),
            expiry_date=date(2029, 1, 1),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_expiry_date_is_required(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    item_id, actor_id = await _seed_item(authenticated_client, db_session)
    # expiry_date is NOT NULL — pharma must always know a lot's expiry.
    db_session.add(_batch(item_id, actor_id, expiry_date=None))
    with pytest.raises(IntegrityError):
        await db_session.flush()


# ---------------------------------------------------------------------------
# stock_movements.batch_id
# ---------------------------------------------------------------------------


def _movement(item_id: uuid.UUID, actor_id: uuid.UUID, **overrides: object) -> StockMovement:
    base: dict[str, object] = {
        "item_id": item_id,
        "direction": MovementDirection.IN,
        "reason": MovementReason.ADJUSTMENT,
        "quantity": Decimal("1"),
        "stock_before": Decimal("0"),
        "stock_after": Decimal("1"),
        "created_by_user_id": actor_id,
    }
    base.update(overrides)
    return StockMovement(**base)


async def test_movement_batch_id_accepts_null(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Non-breaking: a movement without a batch is still valid (every
    pre-pharma movement is exactly this)."""
    item_id, actor_id = await _seed_item(authenticated_client, db_session)
    movement = _movement(item_id, actor_id)  # batch_id defaults to None
    db_session.add(movement)
    await db_session.flush()
    await db_session.refresh(movement)
    assert movement.batch_id is None


async def test_movement_rejects_unknown_batch_id(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    item_id, actor_id = await _seed_item(authenticated_client, db_session)
    db_session.add(_movement(item_id, actor_id, batch_id=uuid.uuid4()))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_movement_accepts_valid_batch_id(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    item_id, actor_id = await _seed_item(authenticated_client, db_session)
    batch = _batch(item_id, actor_id)
    db_session.add(batch)
    await db_session.flush()

    db_session.add(_movement(item_id, actor_id, batch_id=batch.id))
    await db_session.flush()  # no error == FK satisfied


# ---------------------------------------------------------------------------
# QC status transitions (#7) — release / reject / recall, via the API
# ---------------------------------------------------------------------------

BATCHES_URL = "/api/v1/batches"


async def _api_lot(
    client: AsyncClient,
    *,
    batch_status: str = "QUARANTINE",
    qty: str = "100",
) -> tuple[str, str]:
    """Create an item (with stock) + a lot via the API → ``(item_id, lot_id)``."""
    item = await client.post(
        ITEMS_URL,
        json={
            "sku": f"FIN-{uuid.uuid4().hex[:8]}",
            "name": "Lot Item",
            "type": "FINISHED",
            "category": "Bottle",
            "unit_of_measure": "pcs",
            "unit_price": "10.00",
            "stock_quantity": qty,
        },
    )
    item_id = item.json()["id"]
    lot = await client.post(
        BATCHES_URL,
        json={
            "item_id": item_id,
            "batch_number": "LOT-1",
            "expiry_date": "2035-01-01",
            "quantity": qty,
            "batch_status": batch_status,
        },
    )
    assert lot.status_code == 201, lot.text
    return item_id, lot.json()["id"]


async def test_change_status_requires_auth_returns_401(client_with_db: AsyncClient) -> None:
    resp = await client_with_db.post(
        f"{BATCHES_URL}/{uuid.uuid4()}/status", json={"status": "RELEASED"}
    )
    assert resp.status_code == 401


async def test_release_quarantined_lot(authenticated_client: AsyncClient) -> None:
    _, lot_id = await _api_lot(authenticated_client)
    resp = await authenticated_client.post(
        f"{BATCHES_URL}/{lot_id}/status", json={"status": "RELEASED"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["batch_status"] == "RELEASED"


async def test_reject_quarantined_lot(authenticated_client: AsyncClient) -> None:
    _, lot_id = await _api_lot(authenticated_client)
    resp = await authenticated_client.post(
        f"{BATCHES_URL}/{lot_id}/status", json={"status": "REJECTED"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["batch_status"] == "REJECTED"


async def test_recall_released_lot(authenticated_client: AsyncClient) -> None:
    _, lot_id = await _api_lot(authenticated_client, batch_status="RELEASED")
    resp = await authenticated_client.post(
        f"{BATCHES_URL}/{lot_id}/status", json={"status": "RECALLED"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["batch_status"] == "RECALLED"


async def test_illegal_transition_returns_409(authenticated_client: AsyncClient) -> None:
    """QUARANTINE can't jump straight to RECALLED — only RELEASED/REJECTED."""
    _, lot_id = await _api_lot(authenticated_client)
    resp = await authenticated_client.post(
        f"{BATCHES_URL}/{lot_id}/status", json={"status": "RECALLED"}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVALID_BATCH_TRANSITION"


async def test_transition_out_of_terminal_state_returns_409(
    authenticated_client: AsyncClient,
) -> None:
    """A REJECTED lot is terminal — it can't be released."""
    _, lot_id = await _api_lot(authenticated_client)
    await authenticated_client.post(f"{BATCHES_URL}/{lot_id}/status", json={"status": "REJECTED"})
    resp = await authenticated_client.post(
        f"{BATCHES_URL}/{lot_id}/status", json={"status": "RELEASED"}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVALID_BATCH_TRANSITION"


async def test_change_status_unknown_lot_returns_404(authenticated_client: AsyncClient) -> None:
    resp = await authenticated_client.post(
        f"{BATCHES_URL}/{uuid.uuid4()}/status", json={"status": "RELEASED"}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "BATCH_NOT_FOUND"
