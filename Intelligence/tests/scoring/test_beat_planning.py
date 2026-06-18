"""Tests for beat planning (§7) — Intelligence service."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import CustomerType
from app.models.sales_activity import ActivityType
from app.models.user import User
from app.services.scoring.beat_planning import (
    BeatCustomerInput,
    _priority,
    _visit_gap_score,
    compute_beat_plan,
)
from app.services.scoring.default_configs import BEAT_PLANNING_V1
from tests.factories import make_activity, make_customer

_PARAMS = BEAT_PLANNING_V1
BEAT_URL = "/api/v1/intelligence/beat-plan"


def _cust(
    name: str, district: str | None, ctype: str, revenue: str, days: int | None
) -> BeatCustomerInput:
    return BeatCustomerInput(
        customer_id=uuid.uuid4(),
        company_name=name,
        district=district,
        customer_type=ctype,
        revenue_90d=Decimal(revenue),
        days_since_last_visit=days,
    )


# --- Unit ------------------------------------------------------------------


def test_bp1_canonical_vector() -> None:
    cohort: list[BeatCustomerInput] = [
        _cust(f"Jaj{i}", "Jajpur", "RETAILER", "0", None) for i in range(11)
    ]
    target = _cust("C", "Jajpur", "DEALER", "340000", 25)
    cohort.append(target)
    cohort.append(_cust("Max", "Cuttack", "RETAILER", "400000", None))
    cohort.extend(_cust(f"Other{i}", "Cuttack", "RETAILER", "0", None) for i in range(27))
    assert len(cohort) == 40

    plan = compute_beat_plan(cohort, _PARAMS, max_visits=12)
    c = next(r for r in plan.all_customers if r.customer_id == target.customer_id)
    assert (
        c.revenue_score,
        c.visit_gap_score,
        c.customer_type_score,
        c.location_density_score,
    ) == (
        85,
        50,
        100,
        30,
    )
    assert c.vps == 68.25
    assert c.priority == "HIGH"


def test_visit_gap_band_edges() -> None:
    for days, expected in [(14, 25), (15, 50), (29, 50), (30, 75), (44, 75), (45, 100)]:
        assert _visit_gap_score(days, _PARAMS) == expected
    assert _visit_gap_score(None, _PARAMS) == 100


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


def test_null_district_zero_density_and_cluster_threshold() -> None:
    cohort = [
        _cust("A", "Dense", "RETAILER", "0", None),
        _cust("B", "Dense", "RETAILER", "0", None),
        _cust("C", "Dense", "RETAILER", "0", None),
        _cust("D", None, "RETAILER", "0", None),
    ]
    plan = compute_beat_plan(cohort, _PARAMS, max_visits=12)
    assert next(r for r in plan.all_customers if r.company_name == "D").location_density_score == 0
    clusters = {c.district: c for c in plan.clusters}
    assert clusters["Dense"].lds == 0.75
    assert clusters["Dense"].cluster_opportunity is True


def test_max_visits_truncates_and_priority_bands() -> None:
    cohort = [_cust(f"C{i}", "X", "DEALER", str(i * 100), None) for i in range(5)]
    plan = compute_beat_plan(cohort, _PARAMS, max_visits=3)
    assert len(plan.suggested_beat) == 3 and len(plan.all_customers) == 5
    assert _priority(80, _PARAMS) == "CRITICAL"
    assert _priority(60, _PARAMS) == "HIGH"
    assert _priority(40, _PARAMS) == "MEDIUM"
    assert _priority(39.99, _PARAMS) == "LOW"


# --- Integration -----------------------------------------------------------


async def test_beat_plan_includes_handled_customer(
    authenticated_client: tuple[AsyncClient, User], db_session: AsyncSession
) -> None:
    client, user = authenticated_client
    customer = make_customer(
        user.id, company_name="Beat Co", customer_type=CustomerType.DEALER, district="Jajpur"
    )
    db_session.add(customer)
    await db_session.flush()
    db_session.add(
        make_activity(
            user.id,
            user.id,
            datetime.now() - timedelta(days=10),
            type_=ActivityType.VISIT,
            customer_id=customer.id,
        )
    )
    await db_session.commit()

    resp = await client.get(BEAT_URL, params={"rep_user_id": str(user.id)})
    assert resp.status_code == 200
    body = resp.json()
    handled = next((c for c in body["all_customers"] if c["customer_id"] == str(customer.id)), None)
    assert handled is not None
    assert handled["customer_type"] == "DEALER"
    assert handled["priority"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


async def test_beat_plan_unknown_rep_404(authenticated_client: tuple[AsyncClient, User]) -> None:
    client, _ = authenticated_client
    resp = await client.get(BEAT_URL, params={"rep_user_id": str(uuid.uuid4())})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "USER_NOT_FOUND"
