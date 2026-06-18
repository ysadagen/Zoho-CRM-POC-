"""Tests for Phase 2B.2 — customer health (§6).

* **Unit** — canonical vector CH-1 (§6.3), the normalization identity
  (``health = raw + 100·W_R``), component band edges, and the no-data default
  path.
* **Integration** — the live read endpoints over a no-data customer.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient

from app.services.scoring.customer_health import (
    CustomerHealthInputs,
    aggregate_health,
    compute_customer_health,
)
from app.services.scoring.default_configs import CUSTOMER_HEALTH_V1

_PARAMS = CUSTOMER_HEALTH_V1

CUSTOMERS_URL = "/api/v1/customers"
HEALTH_URL = "/api/v1/intelligence/customer-health"


def _score(**kwargs: object) -> object:
    inputs = CustomerHealthInputs(competitive_risk_level="NONE", **kwargs)  # type: ignore[arg-type]
    return compute_customer_health(inputs, _PARAMS)


# ===========================================================================
# Unit — aggregation / normalization
# ===========================================================================


def test_ch1_canonical_vector() -> None:
    """§6.3: CPS 68.00, CRS 30.75 ⇒ health 68.50 STABLE."""
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

    assert aggregate_health(full_cps, zero_crs, _PARAMS)[2] == 100.0  # best
    assert aggregate_health(zero_cps, full_crs, _PARAMS)[2] == 0.0  # worst
    # All-zero components ⇒ raw 0 ⇒ health = 100·W_R = 40 (standard).
    assert aggregate_health(zero_cps, zero_crs, _PARAMS)[2] == 40.0


# ===========================================================================
# Unit — component band edges
# ===========================================================================


def test_volume_achievement_caps_at_100_and_defaults() -> None:
    capped = _score(target_quantity=Decimal("100"), dispatch_current_period=Decimal("150"))
    assert capped.cps_components["volume_achievement"] == 100  # type: ignore[attr-defined]
    partial = _score(target_quantity=Decimal("100"), dispatch_current_period=Decimal("80"))
    assert partial.cps_components["volume_achievement"] == 80  # type: ignore[attr-defined]
    no_target = _score()
    assert no_target.cps_components["volume_achievement"] == 50  # type: ignore[attr-defined]
    assert "volume_achievement" in no_target.defaults_applied  # type: ignore[attr-defined]


def test_dso_band_edges() -> None:
    for days, expected in [(30, 100), (31, 75), (45, 75), (60, 50), (90, 25), (91, 0)]:
        result = _score(dso_days=float(days))
        assert result.cps_components["payment_discipline"] == expected  # type: ignore[attr-defined]


def test_engagement_band_edges() -> None:
    for visits, expected in [(6, 100), (5, 75), (4, 75), (2, 50), (1, 25), (0, 0)]:
        result = _score(visit_meeting_count_90d=visits)
        assert result.cps_components["engagement"] == expected  # type: ignore[attr-defined]


def test_competitive_risk_mapping() -> None:
    for level, expected in [("NONE", 0), ("LOW", 33), ("MEDIUM", 66), ("HIGH", 100)]:
        inputs = CustomerHealthInputs(competitive_risk_level=level)
        result = compute_customer_health(inputs, _PARAMS)
        assert result.crs_components["competitive_risk"] == expected


def test_engagement_gap_never_is_max_risk() -> None:
    result = _score()  # comm_gap_days / activity_gap_days both None
    assert result.crs_components["engagement_gap"] == 100  # type: ignore[attr-defined]


def test_volume_decline_band() -> None:
    # avg monthly prior = 300/3 = 100; last 30d = 50 ⇒ 50% decline ⇒ 100.
    result = _score(dispatch_prior_90d=Decimal("300"), dispatch_last_30d=Decimal("50"))
    assert result.crs_components["volume_decline"] == 100  # type: ignore[attr-defined]


def test_payment_risk_band() -> None:
    result = _score(total_outstanding=Decimal("100"), overdue_outstanding=Decimal("75"))
    assert result.crs_components["payment_risk"] == 100  # type: ignore[attr-defined]
    none = _score()
    assert none.crs_components["payment_risk"] == 0  # type: ignore[attr-defined]


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


# ===========================================================================
# Integration
# ===========================================================================


async def _make_customer(client: AsyncClient, name: str) -> str:
    resp = await client.post(CUSTOMERS_URL, json={"company_name": name, "contact_person": "P"})
    return resp.json()["id"]


async def test_customer_health_live_detail_defaults(authenticated_client: AsyncClient) -> None:
    customer_id = await _make_customer(authenticated_client, "No Data Co")
    resp = await authenticated_client.get(f"{HEALTH_URL}/{customer_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["classification"] == "AT_RISK"
    assert body["health_score"] == 58.90
    assert set(body["defaults_applied"]) == {
        "volume_achievement",
        "payment_discipline",
        "growth_trend",
        "margin_quality",
        "volume_decline",
    }
    assert body["history"] == []  # no snapshots until recompute


async def test_customer_health_list_filters_classification(
    authenticated_client: AsyncClient,
) -> None:
    await _make_customer(authenticated_client, "AR Co")
    resp = await authenticated_client.get(HEALTH_URL, params={"classification": "AT_RISK"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(i["classification"] == "AT_RISK" for i in body["items"])


async def test_customer_health_unknown_returns_404(authenticated_client: AsyncClient) -> None:
    resp = await authenticated_client.get(f"{HEALTH_URL}/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"
