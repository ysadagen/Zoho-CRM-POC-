"""Tests for lead scoring (§4) — Intelligence service.

* **Unit** — :func:`compute_lead_score` against canonical vector LS-1 (§4.6),
  every band edge, and every documented default.
* **Integration** — the live read endpoints (compute-on-read), backed by CRM
  rows inserted directly (this service has no CRM write endpoints).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.scoring.default_configs import LEAD_SCORING_V1
from app.services.scoring.lead_scoring import LeadScoringInputs, compute_lead_score
from tests.factories import make_lead

_PARAMS = LEAD_SCORING_V1
_TODAY = date(2026, 1, 1)

LEAD_SCORES_URL = "/api/v1/intelligence/lead-scores"


# ===========================================================================
# Unit — pure function
# ===========================================================================


def test_ls1_canonical_vector() -> None:
    """§4.6: 70.00 → MEDIUM from (70, 50, 70, 100, 60)."""
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
        (Decimal("800000"), "HIGH", 70),
        (Decimal("249999"), "LOW", 10),
        (Decimal("250000"), "MEDIUM", 70),
    ],
)
def test_contribution_matrix(budget: Decimal, potential: str, expected: int) -> None:
    inputs = LeadScoringInputs(today=_TODAY, estimated_budget=budget, dealer_potential=potential)
    assert compute_lead_score(inputs, _PARAMS).contribution_margin == expected


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
        today=_TODAY, quantity=Decimal(ratio_num), cohort_max_quantity=Decimal("100")
    )
    assert compute_lead_score(inputs, _PARAMS).quantity == expected


def test_quantity_missing_or_empty_cohort_uses_default() -> None:
    no_qty = compute_lead_score(LeadScoringInputs(today=_TODAY), _PARAMS)
    assert no_qty.quantity == 40 and "quantity" in no_qty.defaults_applied
    empty = compute_lead_score(
        LeadScoringInputs(today=_TODAY, quantity=Decimal("10"), cohort_max_quantity=None), _PARAMS
    )
    assert empty.quantity == 40 and "quantity" in empty.defaults_applied


@pytest.mark.parametrize(
    ("unit_price", "standard_cost", "expected"),
    [
        (Decimal("100"), Decimal("75"), 100),
        (Decimal("100"), Decimal("76"), 60),
        (Decimal("100"), Decimal("90"), 60),
        (Decimal("100"), Decimal("91"), 30),
        (Decimal("100"), Decimal("110"), 30),
    ],
)
def test_product_margin_bands(unit_price: Decimal, standard_cost: Decimal, expected: int) -> None:
    inputs = LeadScoringInputs(today=_TODAY, unit_price=unit_price, standard_cost=standard_cost)
    assert compute_lead_score(inputs, _PARAMS).product_margin == expected


def test_product_margin_missing_uses_default() -> None:
    result = compute_lead_score(LeadScoringInputs(today=_TODAY), _PARAMS)
    assert result.product_margin == 60
    assert "product_margin" in result.defaults_applied


# ===========================================================================
# Integration — live endpoints
# ===========================================================================


async def test_list_lead_scores_requires_auth(client_with_db: AsyncClient) -> None:
    resp = await client_with_db.get(LEAD_SCORES_URL)
    assert resp.status_code == 401


async def test_sparse_lead_scored_live_with_defaults(
    authenticated_client: tuple[AsyncClient, User], db_session: AsyncSession
) -> None:
    client, user = authenticated_client
    lead = make_lead(user.id, user.id)
    db_session.add(lead)
    await db_session.commit()

    detail = await client.get(f"{LEAD_SCORES_URL}/{lead.id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["classification"] == "COLD"
    assert body["total_score"] == 36.0
    assert set(body["defaults_applied"]) == {
        "urgency",
        "contribution_margin",
        "quantity",
        "product_margin",
    }
    assert body["history"] == []  # nothing persisted until recompute


async def test_list_lead_scores_filters_classification(
    authenticated_client: tuple[AsyncClient, User], db_session: AsyncSession
) -> None:
    client, user = authenticated_client
    db_session.add(make_lead(user.id, user.id, contact_name="Cold Lead"))
    await db_session.commit()

    resp = await client.get(LEAD_SCORES_URL, params={"classification": "COLD"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(item["classification"] == "COLD" for item in body["items"])


async def test_get_lead_score_unknown_returns_404(
    authenticated_client: tuple[AsyncClient, User],
) -> None:
    client, _ = authenticated_client
    resp = await client.get(f"{LEAD_SCORES_URL}/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "LEAD_NOT_FOUND"
