"""Tests for recompute + snapshots (§8) — Intelligence service."""

from __future__ import annotations

import copy

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.score_snapshot import CustomerHealthScore
from app.models.scoring_config import ScoringConfig, ScoringEngine
from app.models.user import User
from app.services.scoring.default_configs import CUSTOMER_HEALTH_V1
from tests.factories import make_customer, make_lead

RECOMPUTE_URL = "/api/v1/intelligence/recompute"
CONFIGS_URL = "/api/v1/intelligence/configs"


async def test_recompute_all_engines_returns_counts_and_duration(
    admin_client: tuple[AsyncClient, User], db_session: AsyncSession
) -> None:
    client, admin = admin_client
    db_session.add(make_customer(admin.id, company_name="RC Co"))
    db_session.add(make_lead(admin.id, admin.id))
    await db_session.commit()

    resp = await client.post(RECOMPUTE_URL, json={"engine": None})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["results"]) == {
        "LEAD_SCORING",
        "CUSTOMER_HEALTH",
        "EFFORT_EFFICIENCY",
        "BEAT_PLANNING",
    }
    assert body["results"]["LEAD_SCORING"] >= 1
    assert body["results"]["CUSTOMER_HEALTH"] >= 1
    assert body["results"]["EFFORT_EFFICIENCY"] >= 1
    assert isinstance(body["duration_ms"], int | float)


async def test_recompute_single_engine(admin_client: tuple[AsyncClient, User]) -> None:
    client, _ = admin_client
    resp = await client.post(RECOMPUTE_URL, json={"engine": "CUSTOMER_HEALTH"})
    assert resp.status_code == 200
    assert set(resp.json()["results"]) == {"CUSTOMER_HEALTH"}


async def test_recompute_requires_admin(authenticated_client: tuple[AsyncClient, User]) -> None:
    client, _ = authenticated_client
    resp = await client.post(RECOMPUTE_URL, json={"engine": None})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ADMIN_REQUIRED"


async def test_recompute_snapshot_carries_new_config_version(
    admin_client: tuple[AsyncClient, User], db_session: AsyncSession
) -> None:
    client, admin = admin_client
    customer = make_customer(admin.id, company_name="Versioned")
    db_session.add(customer)
    await db_session.commit()

    await client.post(RECOMPUTE_URL, json={"engine": "CUSTOMER_HEALTH"})

    params = copy.deepcopy(CUSTOMER_HEALTH_V1)
    v2 = await client.post(CONFIGS_URL, json={"engine": "CUSTOMER_HEALTH", "params": params})
    v2_config_id = v2.json()["id"]
    assert v2.json()["version"] == 2
    await client.post(RECOMPUTE_URL, json={"engine": "CUSTOMER_HEALTH"})

    snapshots = (
        (
            await db_session.execute(
                select(CustomerHealthScore).where(CustomerHealthScore.customer_id == customer.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(snapshots) == 2
    assert v2_config_id in {str(s.config_id) for s in snapshots}
    active = (
        await db_session.execute(
            select(ScoringConfig).where(
                ScoringConfig.engine == ScoringEngine.CUSTOMER_HEALTH,
                ScoringConfig.is_active.is_(True),
            )
        )
    ).scalar_one()
    assert str(active.id) == v2_config_id
