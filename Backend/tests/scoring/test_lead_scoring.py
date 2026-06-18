"""Tests for Phase 2B.1 — lead scoring (§4).

Two layers, per the pure-function rule (§16):

* **Unit** — :func:`compute_lead_score` against the canonical vector LS-1
  (§4.6), every band edge, and every documented default.
* **Integration** — the write-triggers (create / scoring-input PATCH /
  transition each snapshot), the read endpoints, and ``defaults_applied``.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.services.scoring.default_configs import LEAD_SCORING_V1
from app.services.scoring.lead_scoring import (
    LeadScoringInputs,
    compute_lead_score,
)

_PARAMS = LEAD_SCORING_V1
_TODAY = date(2026, 1, 1)

LEADS_URL = "/api/v1/leads"
CUSTOMERS_URL = "/api/v1/customers"
ITEMS_URL = "/api/v1/items"
SCORES_URL = "/api/v1/intelligence/lead-scores"


# ===========================================================================
# Unit — pure function
# ===========================================================================


def test_ls1_canonical_vector() -> None:
    """§4.6: required in 20d (70), state+district (50), budget 800k + HIGH
    (70), qty 50 / cohort 60 → 0.83 (100), margin 16% (60) ⇒ 70.00 MEDIUM."""
    inputs = LeadScoringInputs(
        today=_TODAY,
        required_by_date=_TODAY + timedelta(days=20),
        state="Odisha",
        district="Jajpur",
        estimated_budget=Decimal("800000"),
        dealer_potential="HIGH",
        quantity=Decimal("50"),
        cohort_max_quantity=Decimal("60"),
        unit_price=Decimal("100"),
        standard_cost=Decimal("84"),
    )
    result = compute_lead_score(inputs, _PARAMS)
    assert (
        result.urgency,
        result.location,
        result.contribution_margin,
        result.quantity,
        result.product_margin,
    ) == (70, 50, 70, 100, 60)
    assert result.total_score == 70.00
    assert result.classification == "MEDIUM"
    assert result.defaults_applied == []


@pytest.mark.parametrize(
    ("days", "expected"),
    [(0, 100), (6, 100), (7, 70), (30, 70), (31, 40), (60, 40), (61, 20), (-5, 100)],
)
def test_urgency_band_edges(days: int, expected: int) -> None:
    inputs = LeadScoringInputs(today=_TODAY, required_by_date=_TODAY + timedelta(days=days))
    assert compute_lead_score(inputs, _PARAMS).urgency == expected


def test_urgency_missing_uses_default() -> None:
    result = compute_lead_score(LeadScoringInputs(today=_TODAY), _PARAMS)
    assert result.urgency == 40
    assert "urgency" in result.defaults_applied


@pytest.mark.parametrize(
    ("state", "district", "city", "pincode", "expected"),
    [
        ("Odisha", "Jajpur", "Cuttack", None, 100),
        ("Odisha", "Jajpur", None, "755001", 100),
        ("Odisha", "Jajpur", None, None, 50),
        ("Odisha", None, None, None, 30),
        (None, None, None, None, 0),
    ],
)
def test_location_tiers(
    state: str | None, district: str | None, city: str | None, pincode: str | None, expected: int
) -> None:
    inputs = LeadScoringInputs(
        today=_TODAY, state=state, district=district, city=city, pincode=pincode
    )
    assert compute_lead_score(inputs, _PARAMS).location == expected


@pytest.mark.parametrize(
    ("budget", "potential", "expected"),
    [
        (Decimal("1000000"), "HIGH", 100),
        (Decimal("800000"), "HIGH", 70),  # MEDIUM budget x HIGH
        (Decimal("249999"), "LOW", 10),  # LOW x LOW
        (Decimal("250000"), "MEDIUM", 70),  # MEDIUM x MEDIUM
    ],
)
def test_contribution_matrix(budget: Decimal, potential: str, expected: int) -> None:
    inputs = LeadScoringInputs(today=_TODAY, estimated_budget=budget, dealer_potential=potential)
    assert compute_lead_score(inputs, _PARAMS).contribution_margin == expected


def test_contribution_single_input() -> None:
    only_potential = compute_lead_score(
        LeadScoringInputs(today=_TODAY, dealer_potential="MEDIUM"), _PARAMS
    )
    assert only_potential.contribution_margin == 70
    only_budget = compute_lead_score(
        LeadScoringInputs(today=_TODAY, estimated_budget=Decimal("2000000")), _PARAMS
    )
    assert only_budget.contribution_margin == 100  # HIGH budget band


def test_contribution_both_missing_uses_default() -> None:
    result = compute_lead_score(LeadScoringInputs(today=_TODAY), _PARAMS)
    assert result.contribution_margin == 40
    assert "contribution_margin" in result.defaults_applied


@pytest.mark.parametrize(
    ("ratio_num", "expected"),
    [(75, 100), (74, 70), (40, 70), (39, 40), (15, 40), (14, 20)],
)
def test_quantity_ratio_bands(ratio_num: int, expected: int) -> None:
    inputs = LeadScoringInputs(
        today=_TODAY,
        quantity=Decimal(ratio_num),
        cohort_max_quantity=Decimal("100"),
    )
    assert compute_lead_score(inputs, _PARAMS).quantity == expected


def test_quantity_missing_or_empty_cohort_uses_default() -> None:
    no_qty = compute_lead_score(LeadScoringInputs(today=_TODAY), _PARAMS)
    assert no_qty.quantity == 40 and "quantity" in no_qty.defaults_applied
    empty_cohort = compute_lead_score(
        LeadScoringInputs(today=_TODAY, quantity=Decimal("10"), cohort_max_quantity=None),
        _PARAMS,
    )
    assert empty_cohort.quantity == 40 and "quantity" in empty_cohort.defaults_applied


@pytest.mark.parametrize(
    ("unit_price", "standard_cost", "expected"),
    [
        (Decimal("100"), Decimal("75"), 100),  # 25%
        (Decimal("100"), Decimal("76"), 60),  # 24%
        (Decimal("100"), Decimal("90"), 60),  # 10%
        (Decimal("100"), Decimal("91"), 30),  # 9%
        (Decimal("100"), Decimal("110"), 30),  # negative margin
    ],
)
def test_product_margin_bands(unit_price: Decimal, standard_cost: Decimal, expected: int) -> None:
    inputs = LeadScoringInputs(today=_TODAY, unit_price=unit_price, standard_cost=standard_cost)
    assert compute_lead_score(inputs, _PARAMS).product_margin == expected


def test_product_margin_missing_uses_default() -> None:
    no_item = compute_lead_score(LeadScoringInputs(today=_TODAY), _PARAMS)
    assert no_item.product_margin == 60 and "product_margin" in no_item.defaults_applied
    no_cost = compute_lead_score(
        LeadScoringInputs(today=_TODAY, unit_price=Decimal("100"), standard_cost=None),
        _PARAMS,
    )
    assert no_cost.product_margin == 60 and "product_margin" in no_cost.defaults_applied


@pytest.mark.parametrize(
    ("components", "expected_total", "expected_class"),
    [
        ((100, 100, 100, 100, 100), 100.0, "HOT"),
        ((100, 100, 100, 70, 30), 80.0, "HOT"),  # exactly 80
        ((40, 50, 40, 40, 30), 40.0, "MEDIUM"),  # exactly 40
        ((40, 30, 40, 40, 30), 36.0, "COLD"),  # below 40
    ],
)
def test_classification_band_edges(
    components: tuple[int, int, int, int, int], expected_total: float, expected_class: str
) -> None:
    """Drive exact totals by choosing inputs that yield the target component
    scores, then assert the HOT/MEDIUM/COLD boundary (80 / 40)."""
    urgency, location, contribution, quantity, margin = components
    # Map target component scores back to inputs.
    urgency_days = {100: 3, 70: 20, 40: 45, 20: 90}[urgency]
    location_inputs = {
        100: ("S", "D", "C", None),
        50: ("S", "D", None, None),
        30: ("S", None, None, None),
        0: (None, None, None, None),
    }[location]
    contribution_inputs = {100: "HIGH", 70: "MEDIUM", 40: "LOW"}[contribution]
    quantity_ratio = {100: 80, 70: 50, 40: 20, 20: 10}[quantity]
    margin_cost = {100: Decimal("75"), 60: Decimal("85"), 30: Decimal("95")}[margin]
    s, d, c, p = location_inputs
    inputs = LeadScoringInputs(
        today=_TODAY,
        required_by_date=_TODAY + timedelta(days=urgency_days),
        state=s,
        district=d,
        city=c,
        pincode=p,
        dealer_potential=contribution_inputs,
        quantity=Decimal(quantity_ratio),
        cohort_max_quantity=Decimal("100"),
        unit_price=Decimal("100"),
        standard_cost=margin_cost,
    )
    result = compute_lead_score(inputs, _PARAMS)
    assert result.total_score == expected_total
    assert result.classification == expected_class


# ===========================================================================
# Integration — write-triggers + endpoints
# ===========================================================================


async def _seed_refs(client: AsyncClient) -> tuple[str, str, str]:
    cust = (
        await client.post(
            CUSTOMERS_URL, json={"company_name": "Ref Co", "contact_person": "Ref Person"}
        )
    ).json()
    item = (
        await client.post(
            ITEMS_URL,
            json={
                "sku": f"ITM-{uuid.uuid4().hex[:8]}",
                "name": "Ref Item",
                "type": "RAW",
                "category": "Polymer",
                "unit_of_measure": "kg",
                "unit_price": "100.00",
                "standard_cost": "75.00",  # 25% margin → product_margin 100
            },
        )
    ).json()
    return cust["created_by_user_id"], cust["id"], item["id"]


async def test_create_lead_writes_initial_score(authenticated_client: AsyncClient) -> None:
    user_id, _customer_id, item_id = await _seed_refs(authenticated_client)
    soon = (date.today() + timedelta(days=3)).isoformat()
    created = (
        await authenticated_client.post(
            LEADS_URL,
            json={
                "contact_name": "Hot Lead",
                "source": "FIELD_VISIT",
                "assigned_to_user_id": user_id,
                "item_id": item_id,
                "quantity": "50",
                "estimated_budget": "2000000",
                "dealer_potential": "HIGH",
                "required_by_date": soon,
                "state": "Odisha",
                "district": "Jajpur",
                "city": "Cuttack",
            },
        )
    ).json()
    assert created["latest_score"]["classification"] == "HOT"
    assert created["latest_score"]["total_score"] == 100.0

    detail = (await authenticated_client.get(f"{LEADS_URL}/{created['id']}")).json()
    assert detail["score"]["components"] == {
        "urgency": 100,
        "location": 100,
        "contribution_margin": 100,
        "quantity": 100,
        "product_margin": 100,
    }
    assert detail["score"]["defaults_applied"] == []


async def test_sparse_lead_scores_with_defaults(authenticated_client: AsyncClient) -> None:
    user_id, _, _ = await _seed_refs(authenticated_client)
    created = (
        await authenticated_client.post(
            LEADS_URL,
            json={"contact_name": "Sparse", "source": "OTHER", "assigned_to_user_id": user_id},
        )
    ).json()
    assert created["latest_score"]["classification"] == "COLD"

    score = (await authenticated_client.get(f"{SCORES_URL}/{created['id']}")).json()
    assert set(score["defaults_applied"]) == {
        "urgency",
        "contribution_margin",
        "quantity",
        "product_margin",
    }
    assert score["total_score"] == 36.0


async def test_patch_scoring_input_adds_snapshot(authenticated_client: AsyncClient) -> None:
    user_id, _, _ = await _seed_refs(authenticated_client)
    lead_id = (
        await authenticated_client.post(
            LEADS_URL,
            json={"contact_name": "Patch Me", "source": "OTHER", "assigned_to_user_id": user_id},
        )
    ).json()["id"]

    await authenticated_client.patch(
        f"{LEADS_URL}/{lead_id}", json={"required_by_date": (date.today()).isoformat()}
    )
    score = (await authenticated_client.get(f"{SCORES_URL}/{lead_id}")).json()
    assert len(score["history"]) == 2  # initial + recompute


async def test_patch_non_scoring_input_does_not_recompute(
    authenticated_client: AsyncClient,
) -> None:
    user_id, _, _ = await _seed_refs(authenticated_client)
    lead_id = (
        await authenticated_client.post(
            LEADS_URL,
            json={"contact_name": "Notes", "source": "OTHER", "assigned_to_user_id": user_id},
        )
    ).json()["id"]

    await authenticated_client.patch(f"{LEADS_URL}/{lead_id}", json={"notes": "just a note"})
    score = (await authenticated_client.get(f"{SCORES_URL}/{lead_id}")).json()
    assert len(score["history"]) == 1


async def test_transition_recomputes_score(authenticated_client: AsyncClient) -> None:
    user_id, _, _ = await _seed_refs(authenticated_client)
    lead_id = (
        await authenticated_client.post(
            LEADS_URL,
            json={"contact_name": "Move", "source": "OTHER", "assigned_to_user_id": user_id},
        )
    ).json()["id"]

    await authenticated_client.post(
        f"{LEADS_URL}/{lead_id}/transition", json={"to_stage": "QUALIFICATION"}
    )
    score = (await authenticated_client.get(f"{SCORES_URL}/{lead_id}")).json()
    assert len(score["history"]) == 2


async def test_list_lead_scores_filter_by_classification(
    authenticated_client: AsyncClient,
) -> None:
    user_id, _, _ = await _seed_refs(authenticated_client)
    # One sparse (COLD) lead.
    await authenticated_client.post(
        LEADS_URL,
        json={"contact_name": "Cold One", "source": "OTHER", "assigned_to_user_id": user_id},
    )
    resp = await authenticated_client.get(SCORES_URL, params={"classification": "COLD"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(item["classification"] == "COLD" for item in body["items"])


async def test_get_lead_score_unknown_returns_404(authenticated_client: AsyncClient) -> None:
    resp = await authenticated_client.get(f"{SCORES_URL}/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "LEAD_SCORE_NOT_FOUND"
