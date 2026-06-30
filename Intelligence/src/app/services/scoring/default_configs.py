"""Frozen v1 default parameters for the four scoring engines.

These are the canonical ``scoring_configs.params`` shapes from
``INTELLIGENCE_SPECIFICATION.md`` §17. They live here, in one place, so the
Alembic data-migration that seeds ``version 1 active`` and the config
validator (``config_service``) reference the *same* literals — no drift.

**Immutable.** A parameter change is a new config version (a new DB row),
never an edit to these dicts; the v1 migration imports them as a frozen
snapshot. Do not mutate at runtime.
"""

from __future__ import annotations

from typing import Any

from app.models.scoring_config import ScoringEngine

LEAD_SCORING_V1: dict[str, Any] = {
    "cohort_window_days": 90,
    "weights": {
        "urgency": 0.20,
        "location": 0.20,
        "contribution_margin": 0.20,
        "quantity": 0.20,
        "product_margin": 0.20,
    },
    "classification": {"hot_min": 80, "medium_min": 40},
    "urgency_bands": [
        {"max_days": 6, "score": 100},
        {"max_days": 30, "score": 70},
        {"max_days": 60, "score": 40},
        {"max_days": None, "score": 20},
    ],
    "urgency_default": 40,
    "location_scores": {"full": 100, "partial": 50, "state_only": 30, "none": 0},
    "budget_thresholds": {"high_min": 1000000, "medium_min": 250000},
    "contribution_matrix": {
        "HIGH": {"HIGH": 100, "MEDIUM": 70, "LOW": 40},
        "MEDIUM": {"HIGH": 70, "MEDIUM": 70, "LOW": 40},
        "LOW": {"HIGH": 40, "MEDIUM": 40, "LOW": 10},
    },
    "contribution_single_input": {"HIGH": 100, "MEDIUM": 70, "LOW": 40},
    "contribution_default": 40,
    "quantity_ratio_bands": [
        {"min_ratio": 0.75, "score": 100},
        {"min_ratio": 0.40, "score": 70},
        {"min_ratio": 0.15, "score": 40},
        {"min_ratio": 0.0, "score": 20},
    ],
    "quantity_default": 40,
    "product_margin_bands": [
        {"min_pct": 25, "score": 100},
        {"min_pct": 10, "score": 60},
        {"min_pct": 0, "score": 30},
    ],
    "product_margin_default": 60,
}

EFFORT_EFFICIENCY_V1: dict[str, Any] = {
    "period_days_default": 90,
    "activity_weights": {"VISIT": 3, "MEETING": 4, "FOLLOW_UP": 2, "CALL": 1},
    "time_points_per_hour": 1,
    "efficiency_weights": {
        "stage_change_rate": 0.20,
        "won_rate": 0.20,
        "revenue_efficiency": 0.20,
        "time_to_close": 0.20,
        "lead_score_utilization": 0.20,
    },
    "efficiency_bands": {
        "highly_efficient_min": 80,
        "efficient_min": 60,
        "needs_improvement_min": 40,
    },
    "quadrant_thresholds": {"effort": 60, "efficiency": 60},
}

# V2 — absolute-threshold mode (recommended for teams of ≤ 4 reps where
# cohort normalization is meaningless). Inherits all V1 keys and adds
# "scoring_mode" + "absolute_thresholds".
#
# Threshold guidance (all admin-tunable via a new config version):
#   effort_target          — raw effort points that count as "full effort".
#                            With weights VISIT=3/MEETING=4/FOLLOW_UP=2/CALL=1
#                            a rep doing ~2 visits + 1 meeting + 3 follow-ups +
#                            5 calls per week over 90 days ≈ 250 pts.
#   revenue_per_effort_target — revenue (₹) per effort point for full revenue
#                            efficiency. Tune to your average deal size.
#   close_target_days      — deals closed at this many days score 50%;
#                            faster → up to 100%, slower → down to 0% at
#                            2× this value.
EFFORT_EFFICIENCY_V2: dict[str, Any] = {
    **EFFORT_EFFICIENCY_V1,
    "scoring_mode": "absolute",
    "absolute_thresholds": {
        "effort_target": 250.0,
        "revenue_per_effort_target": 500.0,
        "close_target_days": 45.0,
    },
}

CUSTOMER_HEALTH_V1: dict[str, Any] = {
    "weight_profiles": {
        "standard": {"w_p": 0.60, "w_r": 0.40},
        "credit_stress": {"w_p": 0.55, "w_r": 0.45},
        "growth_expansion": {"w_p": 0.70, "w_r": 0.30},
    },
    "default_profile": "standard",
    "classification": {"healthy_min": 80, "stable_min": 60, "at_risk_min": 40},
    "cps_weights": {
        "volume_achievement": 0.30,
        "payment_discipline": 0.20,
        "engagement": 0.20,
        "growth_trend": 0.15,
        "margin_quality": 0.15,
    },
    "crs_weights": {
        "volume_decline": 0.30,
        "payment_risk": 0.25,
        "competitive_risk": 0.20,
        "engagement_gap": 0.15,
        "service_risk": 0.10,
    },
    "volume_achievement_default": 50,
    "dso_window_days": 180,
    "dso_bands": [
        {"max_days": 30, "score": 100},
        {"max_days": 45, "score": 75},
        {"max_days": 60, "score": 50},
        {"max_days": 90, "score": 25},
        {"max_days": None, "score": 0},
    ],
    "dso_default": 50,
    "engagement_window_days": 90,
    "engagement_bands": [
        {"min_visits": 6, "score": 100},
        {"min_visits": 4, "score": 75},
        {"min_visits": 2, "score": 50},
        {"min_visits": 1, "score": 25},
        {"min_visits": 0, "score": 0},
    ],
    "growth_bands": [
        {"min_pct": 20, "score": 100},
        {"min_pct": 5, "score": 75},
        {"min_pct": -5, "score": 50},
        {"min_pct": -20, "score": 25},
        {"min_pct": None, "score": 0},
    ],
    "growth_default": 50,
    "margin_bands": [
        {"min_pct": 25, "score": 100},
        {"min_pct": 10, "score": 60},
        {"min_pct": 0, "score": 30},
    ],
    "margin_default": 60,
    "decline_bands": [
        {"min_pct": 50, "score": 100},
        {"min_pct": 25, "score": 70},
        {"min_pct": 10, "score": 40},
        {"min_pct": 0, "score": 0},
    ],
    "payment_risk_bands": [
        {"min_pct": 75, "score": 100},
        {"min_pct": 50, "score": 75},
        {"min_pct": 25, "score": 50},
        {"min_pct": 1, "score": 25},
        {"min_pct": 0, "score": 0},
    ],
    "competitive_scores": {"NONE": 0, "LOW": 33, "MEDIUM": 66, "HIGH": 100},
    "engagement_gap_weights": {"communication": 0.40, "activity": 0.60},
    "comm_gap_bands": [
        {"max_days": 7, "score": 0},
        {"max_days": 15, "score": 20},
        {"max_days": 30, "score": 40},
        {"max_days": 60, "score": 70},
        {"max_days": None, "score": 100},
    ],
    "activity_gap_bands": [
        {"max_days": 15, "score": 0},
        {"max_days": 30, "score": 25},
        {"max_days": 60, "score": 50},
        {"max_days": 90, "score": 75},
        {"max_days": None, "score": 100},
    ],
    "service_risk_bands": [
        {"min_complaints": 3, "score": 100},
        {"min_complaints": 2, "score": 70},
        {"min_complaints": 1, "score": 40},
        {"min_complaints": 0, "score": 0},
    ],
}

BEAT_PLANNING_V1: dict[str, Any] = {
    "weights": {
        "revenue": 0.35,
        "visit_gap": 0.25,
        "customer_type": 0.20,
        "location_density": 0.20,
    },
    "visit_gap_bands": [
        {"max_days": 14, "score": 25},
        {"max_days": 29, "score": 50},
        {"max_days": 44, "score": 75},
        {"max_days": None, "score": 100},
    ],
    "customer_type_scores": {"DEALER": 100, "SUB_DEALER": 80, "RETAILER": 70},
    "priority_bands": {"critical_min": 80, "high_min": 60, "medium_min": 40},
    "revenue_window_days": 90,
    "handled_window_days": 180,
    "cluster_lds_threshold": 0.50,
    "default_max_visits": 12,
}

#: Frozen v1 parameters keyed by engine — consumed by the seed migration and
#: the config validator. Treat as read-only.
DEFAULT_PARAMS_V1: dict[ScoringEngine, dict[str, Any]] = {
    ScoringEngine.LEAD_SCORING: LEAD_SCORING_V1,
    ScoringEngine.EFFORT_EFFICIENCY: EFFORT_EFFICIENCY_V1,
    ScoringEngine.CUSTOMER_HEALTH: CUSTOMER_HEALTH_V1,
    ScoringEngine.BEAT_PLANNING: BEAT_PLANNING_V1,
}
