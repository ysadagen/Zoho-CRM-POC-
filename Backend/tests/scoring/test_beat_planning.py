"""Tests for Phase 2B.4 — beat planning & visit prioritization (§7).

* **Unit** — canonical vector BP-1 (§7.4); visit-gap band edges (incl. NULL
  district → LDS 0 and never-visited → 100); customer-type mapping; the
  cluster-opportunity threshold; max_visits truncation; priority bands.
* **Integration** — the live beat-plan endpoint.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient

from app.services.scoring.beat_planning import (
    BeatCustomerInput,
    _priority,
    _visit_gap_score,
    compute_beat_plan,
)
from app.services.scoring.default_configs import BEAT_PLANNING_V1

_PARAMS = BEAT_PLANNING_V1

CUSTOMERS_URL = "/api/v1/customers"
ACTIVITIES_URL = "/api/v1/activities"
BEAT_URL = "/api/v1/intelligence/beat-plan"


def _cust(
    name: str,
    district: str | None,
    ctype: str,
    revenue: str,
    days_since_visit: int | None,
) -> BeatCustomerInput:
    return BeatCustomerInput(
        customer_id=uuid.uuid4(),
        company_name=name,
        district=district,
        customer_type=ctype,
        revenue_90d=Decimal(revenue),
        days_since_last_visit=days_since_visit,
    )


# ===========================================================================
# Unit
# ===========================================================================


def test_bp1_canonical_vector() -> None:
    """§7.4: DEALER in Jajpur, 12/40 cluster, rev 340k of 400k max, visited
    25d ago ⇒ VPS 68.25 HIGH."""
    cohort: list[BeatCustomerInput] = []
    # 11 other Jajpur customers (with C → 12 in Jajpur of 40 total).
    for i in range(11):
        cohort.append(_cust(f"Jaj{i}", "Jajpur", "RETAILER", "0", None))
    target = _cust("C", "Jajpur", "DEALER", "340000", 25)
    cohort.append(target)
    # Cohort revenue max = 400,000 (a non-Jajpur customer).
    cohort.append(_cust("Max", "Cuttack", "RETAILER", "400000", None))
    for i in range(27):
        cohort.append(_cust(f"Other{i}", "Cuttack", "RETAILER", "0", None))
    assert len(cohort) == 40

    plan = compute_beat_plan(cohort, _PARAMS, max_visits=12)
    c = next(r for r in plan.all_customers if r.customer_id == target.customer_id)
    assert c.revenue_score == 85
    assert c.visit_gap_score == 50
    assert c.customer_type_score == 100
    assert c.location_density_score == 30
    assert c.vps == 68.25
    assert c.priority == "HIGH"


def test_visit_gap_band_edges() -> None:
    for days, expected in [(14, 25), (15, 50), (29, 50), (30, 75), (44, 75), (45, 100)]:
        assert _visit_gap_score(days, _PARAMS) == expected
    assert _visit_gap_score(None, _PARAMS) == 100  # never visited


def test_customer_type_mapping() -> None:
    cohort = [
        _cust("D", "X", "DEALER", "0", None),
        _cust("S", "X", "SUB_DEALER", "0", None),
        _cust("R", "X", "RETAILER", "0", None),
    ]
    scores = {
        r.company_name: r.customer_type_score
        for r in compute_beat_plan(cohort, _PARAMS, max_visits=12).all_customers
    }
    assert scores == {"D": 100, "S": 80, "R": 70}


def test_null_district_gives_zero_location_density() -> None:
    cohort = [
        _cust("NoDist", None, "DEALER", "100", None),
        _cust("Has", "X", "DEALER", "100", None),
    ]
    plan = compute_beat_plan(cohort, _PARAMS, max_visits=12)
    no_dist = next(r for r in plan.all_customers if r.company_name == "NoDist")
    assert no_dist.location_density_score == 0


def test_cluster_opportunity_threshold() -> None:
    # 3 of 4 in one district ⇒ LDS 0.75 > 0.50 ⇒ opportunity.
    cohort = [
        _cust("A", "Dense", "RETAILER", "0", None),
        _cust("B", "Dense", "RETAILER", "0", None),
        _cust("C", "Dense", "RETAILER", "0", None),
        _cust("D", "Sparse", "RETAILER", "0", None),
    ]
    clusters = {c.district: c for c in compute_beat_plan(cohort, _PARAMS, max_visits=12).clusters}
    assert clusters["Dense"].lds == 0.75
    assert clusters["Dense"].cluster_opportunity is True
    assert clusters["Sparse"].cluster_opportunity is False


def test_max_visits_truncates_suggested_beat() -> None:
    cohort = [_cust(f"C{i}", "X", "DEALER", str(i * 100), None) for i in range(5)]
    plan = compute_beat_plan(cohort, _PARAMS, max_visits=3)
    assert len(plan.suggested_beat) == 3
    assert len(plan.all_customers) == 5
    # Suggested beat is the top-VPS slice (VPS descending).
    vps_values = [c.vps for c in plan.suggested_beat]
    assert vps_values == sorted(vps_values, reverse=True)


def test_priority_bands() -> None:
    assert _priority(80, _PARAMS) == "CRITICAL"
    assert _priority(60, _PARAMS) == "HIGH"
    assert _priority(40, _PARAMS) == "MEDIUM"
    assert _priority(39.99, _PARAMS) == "LOW"


def test_zero_revenue_everywhere_scores_zero() -> None:
    cohort = [_cust("A", "X", "RETAILER", "0", None), _cust("B", "X", "RETAILER", "0", None)]
    plan = compute_beat_plan(cohort, _PARAMS, max_visits=12)
    assert all(r.revenue_score == 0 for r in plan.all_customers)


# ===========================================================================
# Integration
# ===========================================================================


async def test_beat_plan_endpoint_includes_handled_customer(
    authenticated_client: AsyncClient,
) -> None:
    cust = (
        await authenticated_client.post(
            CUSTOMERS_URL,
            json={
                "company_name": "Beat Co",
                "contact_person": "P",
                "customer_type": "DEALER",
                "district": "Jajpur",
            },
        )
    ).json()
    user_id = cust["created_by_user_id"]
    customer_id = cust["id"]

    # Log a VISIT by this rep → the customer becomes "handled".
    visited_on = (date.today() - timedelta(days=10)).isoformat()
    activity = await authenticated_client.post(
        ACTIVITIES_URL,
        json={
            "type": "VISIT",
            "occurred_at": f"{visited_on}T10:00:00Z",
            "customer_id": customer_id,
        },
    )
    assert activity.status_code == 201

    resp = await authenticated_client.get(BEAT_URL, params={"rep_user_id": user_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["rep_user_id"] == user_id
    handled = next((c for c in body["all_customers"] if c["customer_id"] == customer_id), None)
    assert handled is not None
    assert handled["customer_type"] == "DEALER"
    assert handled["days_since_last_visit"] == 10
    assert handled["priority"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


async def test_beat_plan_unknown_rep_returns_404(authenticated_client: AsyncClient) -> None:
    resp = await authenticated_client.get(BEAT_URL, params={"rep_user_id": str(uuid.uuid4())})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "USER_NOT_FOUND"
