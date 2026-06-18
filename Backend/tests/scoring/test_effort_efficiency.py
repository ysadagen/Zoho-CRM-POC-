"""Tests for Phase 2B.3 — effort & efficiency (§5).

* **Unit** — canonical vector EE-1 (§5.4); cohort edges (single rep, zero
  activity, zero won, zero assigned); inverted time-to-close; utilization; and
  the band/quadrant boundaries.
* **Integration** — the live cohort + detail endpoints.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient

from app.services.scoring.default_configs import EFFORT_EFFICIENCY_V1
from app.services.scoring.effort_efficiency import (
    RepEffortInputs,
    _band,
    _quadrant,
    compute_effort_efficiency,
)

_PARAMS = EFFORT_EFFICIENCY_V1

CUSTOMERS_URL = "/api/v1/customers"
EE_URL = "/api/v1/intelligence/effort-efficiency"


def _rep(email: str, **kwargs: object) -> RepEffortInputs:
    return RepEffortInputs(rep_user_id=uuid.uuid4(), rep_email=email, **kwargs)  # type: ignore[arg-type]


# ===========================================================================
# Unit
# ===========================================================================


def test_ee1_canonical_vector() -> None:
    """§5.4: R1 effort_raw 86 / cohort max 120 ⇒ effort_score 71.67;
    efficiency 55.55 ⇒ needs improvement, HIGH_EFFORT_LOW_EFFICIENCY."""
    r1 = _rep(
        "r1@x.io",
        visits=10,
        meetings=4,
        follow_ups=6,
        calls=8,
        hours_logged=20.0,
        assigned_leads=20,
        leads_progressed=12,  # 60%
        leads_won=5,  # 25%
        won_value_sum=Decimal("1200000"),
        avg_time_to_close=28.0,
        hot_lead_effort_points=55.0,
        all_lead_effort_points=100.0,
    )
    # Cohort benchmarks: rep_b sets effort max 120 and revenue-eff max 20000;
    # rep_b/rep_c set the time-to-close max 45 / min 20.
    rep_b = _rep(
        "b@x.io",
        hours_logged=120.0,
        assigned_leads=1,
        leads_won=1,
        won_value_sum=Decimal("2400000"),
        avg_time_to_close=45.0,
    )
    rep_c = _rep(
        "c@x.io",
        visits=1,
        assigned_leads=1,
        leads_won=1,
        won_value_sum=Decimal("1000"),
        avg_time_to_close=20.0,
    )
    results = compute_effort_efficiency([r1, rep_b, rep_c], _PARAMS)
    out = results[0]
    assert out.effort_raw == 86.0
    assert out.effort_score == 71.67
    assert out.efficiency_components == {
        "stage_change_rate": 60.0,
        "won_rate": 25.0,
        "revenue_efficiency": 69.77,
        "time_to_close": 68.0,
        "lead_score_utilization": 55.0,
    }
    assert out.efficiency_score == 55.55
    assert out.efficiency_band == "needs improvement"
    assert out.quadrant == "HIGH_EFFORT_LOW_EFFICIENCY"


def test_single_rep_cohort_is_the_benchmark() -> None:
    solo = _rep(
        "solo@x.io",
        visits=5,
        assigned_leads=4,
        leads_progressed=2,
        leads_won=1,
        won_value_sum=Decimal("100"),
        avg_time_to_close=30.0,
    )
    out = compute_effort_efficiency([solo], _PARAMS)[0]
    assert out.effort_score == 100.0  # only member is the benchmark
    assert out.efficiency_components["time_to_close"] == 100.0  # single → top
    assert out.efficiency_components["revenue_efficiency"] == 100.0


def test_zero_activity_rep_scores_zero_effort() -> None:
    active = _rep("a@x.io", visits=10)
    idle = _rep("idle@x.io")
    results = compute_effort_efficiency([active, idle], _PARAMS)
    assert results[1].effort_raw == 0.0
    assert results[1].effort_score == 0.0


def test_zero_won_zeros_revenue_and_time_to_close() -> None:
    rep = _rep("nw@x.io", visits=5, assigned_leads=10, leads_progressed=4, leads_won=0)
    out = compute_effort_efficiency([rep], _PARAMS)[0]
    assert out.efficiency_components["revenue_efficiency"] == 0.0
    assert out.efficiency_components["time_to_close"] == 0.0
    assert out.efficiency_components["won_rate"] == 0.0


def test_zero_assigned_zeros_rate_components() -> None:
    rep = _rep("za@x.io", visits=3, assigned_leads=0)
    out = compute_effort_efficiency([rep], _PARAMS)[0]
    assert out.efficiency_components["stage_change_rate"] == 0.0
    assert out.efficiency_components["won_rate"] == 0.0
    assert out.efficiency_components["lead_score_utilization"] == 0.0


def test_utilization_uses_lead_effort_points_only() -> None:
    rep = _rep(
        "u@x.io",
        visits=99,  # non-lead effort should not affect utilization
        assigned_leads=2,
        hot_lead_effort_points=30.0,
        all_lead_effort_points=40.0,
    )
    out = compute_effort_efficiency([rep], _PARAMS)[0]
    assert out.efficiency_components["lead_score_utilization"] == 75.0


def test_band_edges() -> None:
    assert _band(80, _PARAMS) == "highly efficient"
    assert _band(60, _PARAMS) == "efficient"
    assert _band(40, _PARAMS) == "needs improvement"
    assert _band(39.99, _PARAMS) == "inefficient"


def test_quadrant_edges() -> None:
    assert _quadrant(60, 60, _PARAMS) == "HIGH_EFFORT_HIGH_EFFICIENCY"
    assert _quadrant(60, 59, _PARAMS) == "HIGH_EFFORT_LOW_EFFICIENCY"
    assert _quadrant(59, 60, _PARAMS) == "LOW_EFFORT_HIGH_EFFICIENCY"
    assert _quadrant(59, 59, _PARAMS) == "LOW_EFFORT_LOW_EFFICIENCY"


# ===========================================================================
# Integration
# ===========================================================================


async def _auth_user_id(client: AsyncClient) -> str:
    cust = await client.post(CUSTOMERS_URL, json={"company_name": "EE Co", "contact_person": "P"})
    return cust.json()["created_by_user_id"]


async def test_effort_efficiency_list_includes_active_rep(
    authenticated_client: AsyncClient,
) -> None:
    user_id = await _auth_user_id(authenticated_client)
    resp = await authenticated_client.get(EE_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert "period_start" in body and "period_end" in body
    me = next((i for i in body["items"] if i["rep_user_id"] == user_id), None)
    assert me is not None
    # No activity logged → bottom-left quadrant.
    assert me["effort_score"] == 0.0
    assert me["quadrant"] == "LOW_EFFORT_LOW_EFFICIENCY"


async def test_effort_efficiency_detail_for_rep(authenticated_client: AsyncClient) -> None:
    user_id = await _auth_user_id(authenticated_client)
    resp = await authenticated_client.get(f"{EE_URL}/{user_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["rep_user_id"] == user_id
    assert body["history"] == []  # no snapshots until recompute


async def test_effort_efficiency_detail_unknown_user_404(
    authenticated_client: AsyncClient,
) -> None:
    resp = await authenticated_client.get(f"{EE_URL}/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "EFFORT_SCORE_NOT_FOUND"
