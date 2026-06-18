"""Engine 1 — Lead scoring (§4).

Two layers:

* :func:`compute_lead_score` — a **pure function** over a plain
  :class:`LeadScoringInputs` dataclass and the engine ``params`` dict. No
  session, no I/O — this is what the canonical vector LS-1 and every band-edge
  / default test exercises to the decimal.
* :class:`LeadScoringService` — the thin orchestrator: it loads the active
  config, gathers inputs via repositories (cohort max quantity, the linked
  item's price/cost), calls the pure function, and inserts an append-only
  snapshot.

Five parameters, equally weighted (configurable). Missing data never blocks
scoring: each parameter has a documented default, and the parameters that fell
back are recorded in ``defaults_applied``.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.lead import Lead
from app.models.score_snapshot import LeadClassification, LeadScore
from app.models.scoring_config import ScoringEngine
from app.repositories.item_repo import ItemRepository
from app.repositories.lead_repo import LeadRepository
from app.repositories.score_snapshot_repo import ScoreSnapshotRepository
from app.services.scoring.config_service import ScoringConfigService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LeadScoringInputs:
    """Everything the pure scorer needs — no DB handles, all resolved."""

    today: date
    required_by_date: date | None = None
    state: str | None = None
    district: str | None = None
    city: str | None = None
    pincode: str | None = None
    estimated_budget: Decimal | None = None
    dealer_potential: str | None = None
    quantity: Decimal | None = None
    #: max quantity over cohort leads (same item type, non-null) — or None
    cohort_max_quantity: Decimal | None = None
    #: linked item's selling price; None when no item is linked
    unit_price: Decimal | None = None
    #: linked item's cost basis; None when no item or cost not set
    standard_cost: Decimal | None = None


@dataclass(frozen=True)
class LeadScoreResult:
    """Pure-function output — component scores, total, band, applied defaults."""

    urgency: int
    location: int
    contribution_margin: int
    quantity: int
    product_margin: int
    total_score: float
    classification: str
    defaults_applied: list[str] = field(default_factory=list)


def _band_score(value: float, bands: list[dict[str, Any]], threshold_key: str) -> int:
    """Walk a band list and return the score for ``value``.

    ``max_*`` keys ascend (first band whose threshold ``>=`` value, ``None`` =
    open); ``min_*`` keys descend (first band whose threshold ``<=`` value,
    ``None`` = open). Falls through to the last band when nothing matched.
    """
    ascending = threshold_key.startswith("max")
    for band in bands:
        threshold = band[threshold_key]
        if threshold is None:
            return int(band["score"])
        if ascending and value <= threshold:
            return int(band["score"])
        if not ascending and value >= threshold:
            return int(band["score"])
    return int(bands[-1]["score"])


def _score_urgency(inp: LeadScoringInputs, params: dict[str, Any]) -> tuple[int, bool]:
    if inp.required_by_date is None:
        return int(params["urgency_default"]), True
    days = (inp.required_by_date - inp.today).days
    return _band_score(float(days), params["urgency_bands"], "max_days"), False


def _score_location(inp: LeadScoringInputs, params: dict[str, Any]) -> int:
    scores = params["location_scores"]
    has_state = bool(inp.state)
    has_district = bool(inp.district)
    has_city_or_pincode = bool(inp.city or inp.pincode)
    if has_state and has_district and has_city_or_pincode:
        return int(scores["full"])
    if has_state and has_district:
        return int(scores["partial"])
    if has_state:
        return int(scores["state_only"])
    return int(scores["none"])


def _budget_band(budget: Decimal, params: dict[str, Any]) -> str:
    thresholds = params["budget_thresholds"]
    if budget >= thresholds["high_min"]:
        return "HIGH"
    if budget >= thresholds["medium_min"]:
        return "MEDIUM"
    return "LOW"


def _score_contribution_margin(inp: LeadScoringInputs, params: dict[str, Any]) -> tuple[int, bool]:
    potential = inp.dealer_potential
    budget_band = (
        _budget_band(inp.estimated_budget, params) if inp.estimated_budget is not None else None
    )

    if potential is not None and budget_band is not None:
        return int(params["contribution_matrix"][potential][budget_band]), False
    if potential is not None:
        return int(params["contribution_single_input"][potential]), False
    if budget_band is not None:
        return int(params["contribution_single_input"][budget_band]), False
    return int(params["contribution_default"]), True


def _score_quantity(inp: LeadScoringInputs, params: dict[str, Any]) -> tuple[int, bool]:
    if inp.quantity is None or not inp.cohort_max_quantity:
        return int(params["quantity_default"]), True
    ratio = float(inp.quantity) / float(inp.cohort_max_quantity)
    return _band_score(ratio, params["quantity_ratio_bands"], "min_ratio"), False


def _score_product_margin(inp: LeadScoringInputs, params: dict[str, Any]) -> tuple[int, bool]:
    if inp.unit_price is None or inp.standard_cost is None or inp.unit_price <= 0:
        return int(params["product_margin_default"]), True
    margin_pct = float(inp.unit_price - inp.standard_cost) / float(inp.unit_price) * 100
    return _band_score(margin_pct, params["product_margin_bands"], "min_pct"), False


def _classify(total: float, params: dict[str, Any]) -> str:
    bands = params["classification"]
    if total >= bands["hot_min"]:
        return LeadClassification.HOT.value
    if total >= bands["medium_min"]:
        return LeadClassification.MEDIUM.value
    return LeadClassification.COLD.value


def compute_lead_score(inputs: LeadScoringInputs, params: dict[str, Any]) -> LeadScoreResult:
    """Pure 0-100 lead score from inputs + config params (§4)."""
    defaults: list[str] = []

    urgency, urgency_default = _score_urgency(inputs, params)
    if urgency_default:
        defaults.append("urgency")
    location = _score_location(inputs, params)
    contribution, contribution_default = _score_contribution_margin(inputs, params)
    if contribution_default:
        defaults.append("contribution_margin")
    quantity, quantity_default = _score_quantity(inputs, params)
    if quantity_default:
        defaults.append("quantity")
    product_margin, product_margin_default = _score_product_margin(inputs, params)
    if product_margin_default:
        defaults.append("product_margin")

    weights = params["weights"]
    total = (
        weights["urgency"] * urgency
        + weights["location"] * location
        + weights["contribution_margin"] * contribution
        + weights["quantity"] * quantity
        + weights["product_margin"] * product_margin
    )
    total = round(total, 2)

    return LeadScoreResult(
        urgency=urgency,
        location=location,
        contribution_margin=contribution,
        quantity=quantity,
        product_margin=product_margin,
        total_score=total,
        classification=_classify(total, params),
        defaults_applied=defaults,
    )


class LeadScoringService:
    """Orchestrates input-gathering, scoring, and snapshot persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._configs = ScoringConfigService(session)
        self._snapshots = ScoreSnapshotRepository(session)
        self._leads = LeadRepository(session)
        self._items = ItemRepository(session)

    @staticmethod
    def _to_snapshot(
        lead_id: uuid.UUID, config_id: uuid.UUID, result: LeadScoreResult
    ) -> LeadScore:
        return LeadScore(
            lead_id=lead_id,
            config_id=config_id,
            urgency_score=result.urgency,
            location_score=result.location,
            contribution_margin_score=result.contribution_margin,
            quantity_score=result.quantity,
            product_margin_score=result.product_margin,
            total_score=Decimal(str(result.total_score)),
            classification=LeadClassification(result.classification),
            defaults_applied=result.defaults_applied,
        )

    async def list_live(
        self,
        *,
        limit: int,
        offset: int,
        classification: LeadClassification | None = None,
        assigned_to_user_id: uuid.UUID | None = None,
        today: date | None = None,
    ) -> tuple[list[tuple[Lead, LeadScoreResult]], int, int]:
        """Live-score every active lead, filter, and page (§9.4).

        Returns ``(page_rows, total_after_filter, config_version)`` — highest
        score first. Lead scores are computed on read (the cohort quantity
        ratio depends on the whole active set), not persisted on write.
        """
        as_of = today or date.today()
        config = await self._configs.load_active(ScoringEngine.LEAD_SCORING)
        params = config.params
        rows: list[tuple[Lead, LeadScoreResult]] = []
        for lead in await self._leads.list_all_active():
            if assigned_to_user_id is not None and lead.assigned_to_user_id != assigned_to_user_id:
                continue
            result = compute_lead_score(await self._gather_inputs(lead, params, as_of), params)
            if classification is not None and result.classification != classification.value:
                continue
            rows.append((lead, result))
        rows.sort(key=lambda lr: lr[1].total_score, reverse=True)
        return rows[offset : offset + limit], len(rows), config.version

    async def get_live(
        self, lead_id: uuid.UUID, *, today: date | None = None
    ) -> tuple[Lead, LeadScoreResult, int, list[LeadScore]]:
        """Live score + snapshot history for one lead. 404 if the lead is
        unknown/inactive."""
        as_of = today or date.today()
        lead = await self._leads.get_by_id(lead_id)
        if lead is None:
            raise NotFoundError("Lead not found", code="LEAD_NOT_FOUND")
        config = await self._configs.load_active(ScoringEngine.LEAD_SCORING)
        result = compute_lead_score(
            await self._gather_inputs(lead, config.params, as_of), config.params
        )
        history = await self._snapshots.lead_score_history(lead_id)
        return lead, result, config.version, history

    async def recompute_all(self, *, today: date | None = None) -> int:
        """Re-score every active lead in one transaction (recompute sweep).

        Reconciles cohort drift — a new larger lead changes everyone's quantity
        ratio (§4.7) — by snapshotting all leads against the active config.
        """
        as_of = today or date.today()
        config_id, params = await self._configs.load_active_params(ScoringEngine.LEAD_SCORING)
        leads = await self._leads.list_all_active()
        for lead in leads:
            inputs = await self._gather_inputs(lead, params, as_of)
            result = compute_lead_score(inputs, params)
            self._session.add(self._to_snapshot(lead.id, config_id, result))
        await self._session.commit()
        logger.info("lead_scores_recomputed", extra={"count": len(leads)})
        return len(leads)

    async def _gather_inputs(
        self, lead: Lead, params: dict[str, Any], today: date
    ) -> LeadScoringInputs:
        unit_price: Decimal | None = None
        standard_cost: Decimal | None = None
        item_type = None
        if lead.item_id is not None:
            item = await self._items.get_by_id(lead.item_id)
            if item is not None:
                unit_price = item.unit_price
                standard_cost = item.standard_cost
                item_type = item.type

        cohort_max: Decimal | None = None
        if lead.quantity is not None:
            window_start = today - timedelta(days=int(params["cohort_window_days"]))
            cohort_max = await self._leads.cohort_max_quantity(
                created_since=window_start, item_type=item_type
            )

        return LeadScoringInputs(
            today=today,
            required_by_date=lead.required_by_date,
            state=lead.state,
            district=lead.district,
            city=lead.city,
            pincode=lead.pincode,
            estimated_budget=lead.estimated_budget,
            dealer_potential=lead.dealer_potential.value if lead.dealer_potential else None,
            quantity=lead.quantity,
            cohort_max_quantity=cohort_max,
            unit_price=unit_price,
            standard_cost=standard_cost,
        )
