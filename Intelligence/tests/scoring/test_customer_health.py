"""Tests for customer health (§6) — Intelligence service."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.scoring.customer_health import (
    CustomerHealthInputs,
    aggregate_health,
    compute_customer_health,
)
from app.services.scoring.default_configs import CUSTOMER_HEALTH_V1
from tests.factories import make_customer

_PARAMS = CUSTOMER_HEALTH_V1
HEALTH_URL = "/api/v1/intelligence/customer-health"


def _score(**kwargs: object) -> object:
    inputs = CustomerHealthInputs(competitive_risk_level="NONE", **kwargs)  # type: ignore[arg-type]
    return compute_customer_health(inputs, _PARAMS)


# --- Unit ------------------------------------------------------------------


def test_ch1_canonical_vector() -> None:
    cps_components = {
        "volume_achievement": 80,
        "payment_discipline": 70,
        "engagement": 60,
        "growth_trend": 50,
        "margin_quality": 70,
    }
    crs_components = {
        "volume_decline": 40,
        "payment_risk": 30,
        "competitive_risk": 33,
        "engagement_gap": 31,
        "service_risk": 0,
    }
    cps, crs, health, classification, profile = aggregate_health(
        cps_components, crs_components, _PARAMS
    )
    assert cps == 68.00
    assert crs == 30.75
    assert health == 68.50
    assert classification == "STABLE"
    assert profile == "standard"


def test_normalization_maps_to_full_range() -> None:
    full_cps = dict.fromkeys(_PARAMS["cps_weights"], 100)
    zero_crs = dict.fromkeys(_PARAMS["crs_weights"], 0)
    zero_cps = dict.fromkeys(_PARAMS["cps_weights"], 0)
    full_crs = dict.fromkeys(_PARAMS["crs_weights"], 100)
    assert aggregate_health(full_cps, zero_crs, _PARAMS)[2] == 100.0
    assert aggregate_health(zero_cps, full_crs, _PARAMS)[2] == 0.0
    assert aggregate_health(zero_cps, zero_crs, _PARAMS)[2] == 40.0


def test_dso_band_edges() -> None:
    for days, expected in [(30, 100), (31, 75), (45, 75), (60, 50), (90, 25), (91, 0)]:
        assert _score(dso_days=float(days)).cps_components["payment_discipline"] == expected  # type: ignore[attr-defined]


def test_engagement_band_edges() -> None:
    for visits, expected in [(6, 100), (5, 75), (4, 75), (2, 50), (1, 25), (0, 0)]:
        assert _score(visit_meeting_count_90d=visits).cps_components["engagement"] == expected  # type: ignore[attr-defined]


def test_competitive_risk_mapping() -> None:
    for level, expected in [("NONE", 0), ("LOW", 33), ("MEDIUM", 66), ("HIGH", 100)]:
        result = compute_customer_health(
            CustomerHealthInputs(competitive_risk_level=level), _PARAMS
        )
        assert result.crs_components["competitive_risk"] == expected


def test_no_data_customer_applies_defaults() -> None:
    result = _score()
    assert set(result.defaults_applied) == {  # type: ignore[attr-defined]
        "volume_achievement",
        "payment_discipline",
        "growth_trend",
        "margin_quality",
        "volume_decline",
    }
    assert result.health_score == 58.90  # type: ignore[attr-defined]
    assert result.classification == "AT_RISK"  # type: ignore[attr-defined]


# --- Integration -----------------------------------------------------------


async def test_customer_health_live_detail_defaults(
    authenticated_client: tuple[AsyncClient, User], db_session: AsyncSession
) -> None:
    client, user = authenticated_client
    customer = make_customer(user.id, company_name="No Data Co")
    db_session.add(customer)
    await db_session.commit()

    resp = await client.get(f"{HEALTH_URL}/{customer.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["classification"] == "AT_RISK"
    assert body["health_score"] == 58.90
    assert body["history"] == []


async def test_customer_health_unknown_returns_404(
    authenticated_client: tuple[AsyncClient, User],
) -> None:
    client, _ = authenticated_client
    resp = await client.get(f"{HEALTH_URL}/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"


async def test_customer_health_list_filters_classification(
    authenticated_client: tuple[AsyncClient, User], db_session: AsyncSession
) -> None:
    client, user = authenticated_client
    db_session.add(make_customer(user.id, company_name="AR Co"))
    await db_session.commit()
    resp = await client.get(HEALTH_URL, params={"classification": "AT_RISK"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(i["classification"] == "AT_RISK" for i in body["items"])
