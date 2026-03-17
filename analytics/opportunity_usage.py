from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from analytics.features_opportunity import PregameOpportunityFeatures, _weighted_average
from analytics.opportunity_math import clamp, regress_to_target, value_or_zero


class UsageConfig(Protocol):
    expected_usage_weights: tuple[tuple[float, str], ...]
    expected_est_usage_weights: tuple[tuple[float, str], ...]
    touches_weights: tuple[tuple[float, str], ...]
    passes_weights: tuple[tuple[float, str], ...]
    usage_regression_target: float
    usage_regression_factor: float
    est_usage_regression_target: float
    est_usage_regression_factor: float
    touches_scale_factor: float
    passes_scale_factor: float
    expected_minutes_scale: float
    touches_scale: float
    passes_scale: float


@dataclass(slots=True)
class UsageBaselineEstimate:
    expected_usage_pct: float
    expected_est_usage_pct: float
    expected_touches: float
    expected_passes: float



def estimate_usage_baseline(
    features: PregameOpportunityFeatures,
    config: UsageConfig,
) -> UsageBaselineEstimate:
    expected_usage_pct = _weighted_average(
        [(weight, getattr(features, attr)) for weight, attr in config.expected_usage_weights]
    ) or 0.0
    expected_est_usage_pct = _weighted_average(
        [(weight, getattr(features, attr)) for weight, attr in config.expected_est_usage_weights]
    ) or 0.0
    expected_touches = _weighted_average(
        [(weight, getattr(features, attr)) for weight, attr in config.touches_weights]
    ) or 0.0
    expected_passes = _weighted_average(
        [(weight, getattr(features, attr)) for weight, attr in config.passes_weights]
    ) or 0.0

    return UsageBaselineEstimate(
        expected_usage_pct=regress_to_target(
            expected_usage_pct,
            target=config.usage_regression_target,
            factor=config.usage_regression_factor,
            lower=0.0,
            upper=0.5,
        ),
        expected_est_usage_pct=regress_to_target(
            expected_est_usage_pct,
            target=config.est_usage_regression_target,
            factor=config.est_usage_regression_factor,
            lower=0.0,
            upper=0.5,
        ),
        expected_touches=max(0.0, expected_touches * config.touches_scale_factor),
        expected_passes=max(0.0, expected_passes * config.passes_scale_factor),
    )



def compute_offensive_role_score(
    *,
    expected_minutes: float,
    expected_usage_pct: float,
    expected_est_usage_pct: float,
    expected_touches: float,
    expected_passes: float,
    rotation_role_score: float,
    config: UsageConfig,
) -> float:
    minutes_score = clamp(expected_minutes / config.expected_minutes_scale, 0.0, 1.2)
    usage_score = clamp(((expected_usage_pct + expected_est_usage_pct) / 2.0) / 0.30, 0.0, 1.2)
    touches_score = clamp(expected_touches / config.touches_scale, 0.0, 1.2)
    passes_score = clamp(expected_passes / config.passes_scale, 0.0, 1.2)
    return clamp(
        0.34 * minutes_score
        + 0.30 * usage_score
        + 0.14 * touches_score
        + 0.08 * passes_score
        + 0.14 * rotation_role_score,
        0.0,
        1.25,
    )



def compute_usage_alignment(features: PregameOpportunityFeatures) -> float:
    return 1.0 - clamp(
        abs(value_or_zero(features.last5_usage_pct) - value_or_zero(features.season_usage_pct)) / 0.12,
        0.0,
        1.0,
    )
