"""Tests for Phase 2B.0 — scoring-config infrastructure (§3.9, §9.5, §17).

Covers: the migration seeds v1 active for all four engines; listing (admin
only); create-new-version activates and deactivates the prior; version
auto-increment; param validation (weight sum, unknown keys); and the DB-level
one-active-per-engine invariant (per CLAUDE.md §10.3 — exercised by a direct
insert that bypasses the API).
"""

from __future__ import annotations

import copy

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scoring_config import ScoringConfig, ScoringEngine
from app.services.scoring.default_configs import DEFAULT_PARAMS_V1

pytestmark = pytest.mark.asyncio

_LEAD = "LEAD_SCORING"


async def test_migration_seeds_v1_active_for_all_engines(
    admin_authenticated_client: AsyncClient,
) -> None:
    resp = await admin_authenticated_client.get("/api/v1/intelligence/configs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4
    engines = {c["engine"] for c in body["items"]}
    assert engines == {
        "LEAD_SCORING",
        "EFFORT_EFFICIENCY",
        "CUSTOMER_HEALTH",
        "BEAT_PLANNING",
    }
    for config in body["items"]:
        assert config["version"] == 1
        assert config["is_active"] is True
        assert config["params"]  # non-empty


async def test_list_configs_filter_by_engine(
    admin_authenticated_client: AsyncClient,
) -> None:
    resp = await admin_authenticated_client.get(
        "/api/v1/intelligence/configs", params={"engine": _LEAD}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["engine"] == _LEAD


async def test_list_configs_requires_admin(authenticated_client: AsyncClient) -> None:
    resp = await authenticated_client.get("/api/v1/intelligence/configs")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ADMIN_REQUIRED"


async def test_create_config_activates_new_version_and_deactivates_prior(
    admin_authenticated_client: AsyncClient,
) -> None:
    params = copy.deepcopy(DEFAULT_PARAMS_V1[ScoringEngine.LEAD_SCORING])
    resp = await admin_authenticated_client.post(
        "/api/v1/intelligence/configs",
        json={"engine": _LEAD, "params": params, "description": "tweak"},
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["version"] == 2
    assert created["is_active"] is True

    listing = (
        await admin_authenticated_client.get(
            "/api/v1/intelligence/configs", params={"engine": _LEAD}
        )
    ).json()
    assert listing["total"] == 2
    active = [c for c in listing["items"] if c["is_active"]]
    assert len(active) == 1
    assert active[0]["version"] == 2


async def test_create_config_version_auto_increments(
    admin_authenticated_client: AsyncClient,
) -> None:
    params = copy.deepcopy(DEFAULT_PARAMS_V1[ScoringEngine.BEAT_PLANNING])
    for expected_version in (2, 3):
        resp = await admin_authenticated_client.post(
            "/api/v1/intelligence/configs",
            json={"engine": "BEAT_PLANNING", "params": params},
        )
        assert resp.status_code == 201
        assert resp.json()["version"] == expected_version


async def test_create_config_weight_sum_not_one_returns_422(
    admin_authenticated_client: AsyncClient,
) -> None:
    params = copy.deepcopy(DEFAULT_PARAMS_V1[ScoringEngine.LEAD_SCORING])
    params["weights"] = {
        "urgency": 0.5,
        "location": 0.2,
        "contribution_margin": 0.1,
        "quantity": 0.1,
        "product_margin": 0.05,
    }  # sums to 0.95
    resp = await admin_authenticated_client.post(
        "/api/v1/intelligence/configs",
        json={"engine": _LEAD, "params": params},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_CONFIG_PARAMS"


async def test_create_config_unknown_key_returns_422(
    admin_authenticated_client: AsyncClient,
) -> None:
    params = copy.deepcopy(DEFAULT_PARAMS_V1[ScoringEngine.LEAD_SCORING])
    params["bogus_key"] = 1
    resp = await admin_authenticated_client.post(
        "/api/v1/intelligence/configs",
        json={"engine": _LEAD, "params": params},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_CONFIG_PARAMS"


async def test_create_config_non_monotonic_band_returns_422(
    admin_authenticated_client: AsyncClient,
) -> None:
    params = copy.deepcopy(DEFAULT_PARAMS_V1[ScoringEngine.LEAD_SCORING])
    # urgency_bands max_days must ascend; make them non-monotonic.
    params["urgency_bands"] = [
        {"max_days": 30, "score": 100},
        {"max_days": 6, "score": 70},
        {"max_days": None, "score": 20},
    ]
    resp = await admin_authenticated_client.post(
        "/api/v1/intelligence/configs",
        json={"engine": _LEAD, "params": params},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_CONFIG_PARAMS"


async def test_create_config_requires_admin(authenticated_client: AsyncClient) -> None:
    params = copy.deepcopy(DEFAULT_PARAMS_V1[ScoringEngine.LEAD_SCORING])
    resp = await authenticated_client.post(
        "/api/v1/intelligence/configs",
        json={"engine": _LEAD, "params": params},
    )
    assert resp.status_code == 403


async def test_one_active_config_per_engine_db_invariant(db_session: AsyncSession) -> None:
    """A direct insert of a second active config for an engine must be rejected
    by the partial unique index (the seed already has an active v1)."""
    dup = ScoringConfig(
        engine=ScoringEngine.LEAD_SCORING,
        version=999,
        params={},
        is_active=True,
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.flush()
