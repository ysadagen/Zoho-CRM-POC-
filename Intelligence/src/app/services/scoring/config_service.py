"""Scoring-config service — load, validate, version, and activate configs.

The engines never read weights from code; they call :meth:`load_active_params`
to get the active config for their engine. Admins create new versions via
:meth:`create_and_activate`, which validates the incoming ``params`` against
the engine's shape (§17) before swapping the active flag — all in one
transaction.

Validation (per §17): every documented top-level key must be present and no
others (unknown keys → 422); weight dicts must sum to 1.0 ± 0.001; band lists
must be monotonic with a single open-ended catch-all last.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.scoring_config import ScoringConfig, ScoringEngine
from app.repositories.scoring_config_repo import ScoringConfigRepository
from app.services.scoring.default_configs import DEFAULT_PARAMS_V1, EFFORT_EFFICIENCY_V2

logger = logging.getLogger(__name__)

_WEIGHT_SUM_TOLERANCE = 0.001


@dataclass(frozen=True)
class _EngineParamSpec:
    """How to validate one engine's ``params`` blob."""

    #: every required top-level key (must be present)
    keys: frozenset[str]
    #: keys allowed but not required (present in newer config versions)
    optional_keys: frozenset[str] = field(default_factory=frozenset)
    #: top-level dicts whose numeric values must sum to 1.0
    weight_sum_keys: tuple[str, ...] = ()
    #: band-list keys (validated monotonic, single None catch-all last)
    band_keys: tuple[str, ...] = ()
    #: nested profile dict whose every profile's values must sum to 1.0
    profile_weights_key: str | None = field(default=None)


_SPECS: dict[ScoringEngine, _EngineParamSpec] = {
    ScoringEngine.LEAD_SCORING: _EngineParamSpec(
        keys=frozenset(DEFAULT_PARAMS_V1[ScoringEngine.LEAD_SCORING]),
        weight_sum_keys=("weights",),
        band_keys=("urgency_bands", "quantity_ratio_bands", "product_margin_bands"),
    ),
    ScoringEngine.EFFORT_EFFICIENCY: _EngineParamSpec(
        keys=frozenset(DEFAULT_PARAMS_V1[ScoringEngine.EFFORT_EFFICIENCY]),
        # scoring_mode and absolute_thresholds are v2-only; absent in v1 configs.
        optional_keys=frozenset(EFFORT_EFFICIENCY_V2) - frozenset(DEFAULT_PARAMS_V1[ScoringEngine.EFFORT_EFFICIENCY]),
        weight_sum_keys=("efficiency_weights",),
    ),
    ScoringEngine.CUSTOMER_HEALTH: _EngineParamSpec(
        keys=frozenset(DEFAULT_PARAMS_V1[ScoringEngine.CUSTOMER_HEALTH]),
        weight_sum_keys=("cps_weights", "crs_weights", "engagement_gap_weights"),
        band_keys=(
            "dso_bands",
            "engagement_bands",
            "growth_bands",
            "margin_bands",
            "decline_bands",
            "payment_risk_bands",
            "comm_gap_bands",
            "activity_gap_bands",
            "service_risk_bands",
        ),
        profile_weights_key="weight_profiles",
    ),
    ScoringEngine.BEAT_PLANNING: _EngineParamSpec(
        keys=frozenset(DEFAULT_PARAMS_V1[ScoringEngine.BEAT_PLANNING]),
        weight_sum_keys=("weights",),
        band_keys=("visit_gap_bands",),
    ),
}


def validate_params(engine: ScoringEngine, params: Any) -> None:
    """Validate ``params`` against ``engine``'s shape. Raise 422 on violation.

    Pure (no I/O) so it is unit-testable and reusable by the seed assertions.
    """
    spec = _SPECS[engine]
    if not isinstance(params, dict):
        raise ValidationError("params must be an object", code="INVALID_CONFIG_PARAMS")

    keys = set(params)
    allowed = spec.keys | spec.optional_keys
    unknown = keys - allowed
    if unknown:
        raise ValidationError(
            f"Unknown config keys for {engine.value}: {sorted(unknown)}",
            code="INVALID_CONFIG_PARAMS",
        )
    missing = spec.keys - keys
    if missing:
        raise ValidationError(
            f"Missing config keys for {engine.value}: {sorted(missing)}",
            code="INVALID_CONFIG_PARAMS",
        )

    for weight_key in spec.weight_sum_keys:
        _check_weight_sum(weight_key, params[weight_key])

    if spec.profile_weights_key is not None:
        profiles = params[spec.profile_weights_key]
        if not isinstance(profiles, dict) or not profiles:
            raise ValidationError(
                f"{spec.profile_weights_key} must be a non-empty object",
                code="INVALID_CONFIG_PARAMS",
            )
        for name, profile in profiles.items():
            _check_weight_sum(f"{spec.profile_weights_key}.{name}", profile)

    for band_key in spec.band_keys:
        _check_band_list(band_key, params[band_key])


def _check_weight_sum(name: str, weights: Any) -> None:
    if not isinstance(weights, dict) or not weights:
        raise ValidationError(f"{name} must be a non-empty object", code="INVALID_CONFIG_PARAMS")
    try:
        total = sum(float(v) for v in weights.values())
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"{name} weights must all be numbers", code="INVALID_CONFIG_PARAMS"
        ) from exc
    if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
        raise ValidationError(
            f"{name} weights must sum to 1.0 (got {total:.4f})",
            code="INVALID_CONFIG_PARAMS",
        )


def _check_band_list(name: str, bands: Any) -> None:
    """Bands must be monotonic on their threshold key, with at most one
    open-ended (``None``) catch-all as the final entry.

    Threshold keys prefixed ``max`` ascend (each band caps a ``≤`` range);
    keys prefixed ``min`` descend (each band floors a ``≥`` range).
    """
    if not isinstance(bands, list) or not bands:
        raise ValidationError(f"{name} must be a non-empty array", code="INVALID_CONFIG_PARAMS")

    prev: float | None = None
    last_index = len(bands) - 1
    for i, band in enumerate(bands):
        if not isinstance(band, dict) or "score" not in band:
            raise ValidationError(f"{name}[{i}] must have a score", code="INVALID_CONFIG_PARAMS")
        threshold_keys = [k for k in band if k != "score"]
        if len(threshold_keys) != 1:
            raise ValidationError(
                f"{name}[{i}] must have exactly one threshold key",
                code="INVALID_CONFIG_PARAMS",
            )
        key = threshold_keys[0]
        value = band[key]
        if value is None:
            if i != last_index:
                raise ValidationError(
                    f"{name}: open-ended band must be last", code="INVALID_CONFIG_PARAMS"
                )
            continue
        ascending = key.startswith("max")
        numeric = float(value)
        if prev is not None and (
            (ascending and numeric <= prev) or (not ascending and numeric >= prev)
        ):
            raise ValidationError(
                f"{name} thresholds must be strictly monotonic",
                code="INVALID_CONFIG_PARAMS",
            )
        prev = numeric


class ScoringConfigService:
    """Loads the active config, lists versions, and creates+activates new ones."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._configs = ScoringConfigRepository(session)

    async def load_active(self, engine: ScoringEngine) -> ScoringConfig:
        """Return the active config for ``engine`` or raise (server invariant).

        Migrations seed one active config per engine, so a missing one is a
        misconfiguration, not a client error.
        """
        config = await self._configs.get_active(engine)
        if config is None:
            raise NotFoundError(
                f"No active scoring config for {engine.value}",
                code="SCORING_CONFIG_NOT_FOUND",
            )
        return config

    async def load_active_params(self, engine: ScoringEngine) -> tuple[uuid.UUID, dict[str, Any]]:
        """Return ``(config_id, params)`` for the active config — the pair the
        engines need to compute and to stamp snapshots."""
        config = await self.load_active(engine)
        return config.id, config.params

    async def list_configs(self, *, engine: ScoringEngine | None = None) -> list[ScoringConfig]:
        return await self._configs.list_(engine=engine)

    async def create_and_activate(
        self,
        engine: ScoringEngine,
        params: dict[str, Any],
        *,
        description: str | None,
        actor_id: uuid.UUID,
    ) -> ScoringConfig:
        """Validate, version (max+1), deactivate the prior active, insert the
        new active config — atomically. 422 if ``params`` is invalid."""
        validate_params(engine, params)

        next_version = await self._configs.max_version(engine) + 1
        await self._configs.deactivate_active(engine)
        config = await self._configs.add(
            ScoringConfig(
                engine=engine,
                version=next_version,
                params=params,
                is_active=True,
                description=description,
                created_by_user_id=actor_id,
            )
        )
        await self._session.commit()
        await self._session.refresh(config)
        logger.info(
            "scoring_config_activated",
            extra={
                "engine": engine.value,
                "version": next_version,
                "config_id": str(config.id),
            },
        )
        return config
