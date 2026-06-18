"""Tests for Phase 2B.5 — recompute + snapshots (§8).

Covers: per-engine and all-engine sweeps return entity counts + duration;
admin-only; and config versioning — a snapshot taken after activating a new
config version carries that new ``config_id`` (CLAUDE.md §12.7).
"""

from __future__ import annotations

import copy

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.score_snapshot import CustomerHealthScore
from app.models.scoring_config import ScoringConfig, ScoringEngine
from app.services.scoring.default_configs import CUSTOMER_HEALTH_V1

CUSTOMERS_URL = "/api/v1/customers"
LEADS_URL = "/api/v1/leads"
RECOMPUTE_URL = "/api/v1/intelligence/recompute"
CONFIGS_URL = "/api/v1/intelligence/configs"


async def _seed_lead(client: AsyncClient) -> None:
    cust = (
        await client.post(CUSTOMERS_URL, json={"company_name": "RC Co", "contact_person": "P"})
    ).json()
    await client.post(
        LEADS_URL,
        json={
            "contact_name": "RC Lead",
            "source": "OTHER",
            "assigned_to_user_id": cust["created_by_user_id"],
        },
    )


async def test_recompute_all_engines_returns_counts_and_duration(
    admin_authenticated_client: AsyncClient,
) -> None:
    await _seed_lead(admin_authenticated_client)
    resp = await admin_authenticated_client.post(RECOMPUTE_URL, json={"engine": None})
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
    assert body["results"]["EFFORT_EFFICIENCY"] >= 1  # the admin user is a rep
    assert isinstance(body["duration_ms"], int | float)


async def test_recompute_single_engine_runs_only_that_engine(
    admin_authenticated_client: AsyncClient,
) -> None:
    await admin_authenticated_client.post(
        CUSTOMERS_URL, json={"company_name": "Solo", "contact_person": "P"}
    )
    resp = await admin_authenticated_client.post(RECOMPUTE_URL, json={"engine": "CUSTOMER_HEALTH"})
    assert resp.status_code == 200
    assert set(resp.json()["results"]) == {"CUSTOMER_HEALTH"}


async def test_recompute_requires_admin(authenticated_client: AsyncClient) -> None:
    resp = await authenticated_client.post(RECOMPUTE_URL, json={"engine": None})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ADMIN_REQUIRED"


async def test_recompute_snapshot_carries_new_config_version(
    admin_authenticated_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    cust = (
        await admin_authenticated_client.post(
            CUSTOMERS_URL, json={"company_name": "Versioned", "contact_person": "P"}
        )
    ).json()
    customer_id = cust["id"]

    # First sweep against the seeded v1 config.
    await admin_authenticated_client.post(RECOMPUTE_URL, json={"engine": "CUSTOMER_HEALTH"})

    # Activate a v2 config, then sweep again.
    params = copy.deepcopy(CUSTOMER_HEALTH_V1)
    v2 = await admin_authenticated_client.post(
        CONFIGS_URL, json={"engine": "CUSTOMER_HEALTH", "params": params}
    )
    v2_config_id = v2.json()["id"]
    assert v2.json()["version"] == 2
    await admin_authenticated_client.post(RECOMPUTE_URL, json={"engine": "CUSTOMER_HEALTH"})

    snapshots = (
        (
            await db_session.execute(
                select(CustomerHealthScore).where(CustomerHealthScore.customer_id == customer_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(snapshots) == 2
    # The post-activation snapshot carries the new (v2) config_id.
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
