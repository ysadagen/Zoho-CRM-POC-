"""Tests for the scoring-config admin surface (§3.9, §9.5, §17)."""

from __future__ import annotations

import copy

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scoring_config import ScoringConfig, ScoringEngine
from app.models.user import User
from app.services.scoring.default_configs import DEFAULT_PARAMS_V1

CONFIGS_URL = "/api/v1/intelligence/configs"
_LEAD = "LEAD_SCORING"


async def test_seeded_v1_active_for_all_engines(admin_client: tuple[AsyncClient, User]) -> None:
    client, _ = admin_client
    resp = await client.get(CONFIGS_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4
    assert {c["engine"] for c in body["items"]} == {
        "LEAD_SCORING",
        "EFFORT_EFFICIENCY",
        "CUSTOMER_HEALTH",
        "BEAT_PLANNING",
    }
    assert all(c["version"] == 1 and c["is_active"] for c in body["items"])


async def test_list_configs_requires_admin(
    authenticated_client: tuple[AsyncClient, User],
) -> None:
    client, _ = authenticated_client
    resp = await client.get(CONFIGS_URL)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ADMIN_REQUIRED"


async def test_create_config_activates_new_version(admin_client: tuple[AsyncClient, User]) -> None:
    client, _ = admin_client
    params = copy.deepcopy(DEFAULT_PARAMS_V1[ScoringEngine.LEAD_SCORING])
    resp = await client.post(CONFIGS_URL, json={"engine": _LEAD, "params": params})
    assert resp.status_code == 201
    assert resp.json()["version"] == 2 and resp.json()["is_active"] is True

    listing = (await client.get(CONFIGS_URL, params={"engine": _LEAD})).json()
    assert listing["total"] == 2
    active = [c for c in listing["items"] if c["is_active"]]
    assert len(active) == 1 and active[0]["version"] == 2


async def test_create_config_weight_sum_not_one_422(admin_client: tuple[AsyncClient, User]) -> None:
    client, _ = admin_client
    params = copy.deepcopy(DEFAULT_PARAMS_V1[ScoringEngine.LEAD_SCORING])
    params["weights"] = {
        "urgency": 0.5,
        "location": 0.2,
        "contribution_margin": 0.1,
        "quantity": 0.1,
        "product_margin": 0.05,
    }
    resp = await client.post(CONFIGS_URL, json={"engine": _LEAD, "params": params})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_CONFIG_PARAMS"


async def test_create_config_unknown_key_422(admin_client: tuple[AsyncClient, User]) -> None:
    client, _ = admin_client
    params = copy.deepcopy(DEFAULT_PARAMS_V1[ScoringEngine.LEAD_SCORING])
    params["bogus"] = 1
    resp = await client.post(CONFIGS_URL, json={"engine": _LEAD, "params": params})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_CONFIG_PARAMS"


async def test_create_config_requires_admin(
    authenticated_client: tuple[AsyncClient, User],
) -> None:
    client, _ = authenticated_client
    params = copy.deepcopy(DEFAULT_PARAMS_V1[ScoringEngine.LEAD_SCORING])
    resp = await client.post(CONFIGS_URL, json={"engine": _LEAD, "params": params})
    assert resp.status_code == 403


async def test_one_active_config_per_engine_db_invariant(db_session: AsyncSession) -> None:
    dup = ScoringConfig(engine=ScoringEngine.LEAD_SCORING, version=999, params={}, is_active=True)
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.flush()
