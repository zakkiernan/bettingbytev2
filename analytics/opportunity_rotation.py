from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from analytics.features_opportunity import PregameOpportunityFeatures, _weighted_average
from analytics.opportunity_math import clamp, regress_to_target, value_or_zero


class RotationConfig(Protocol):
    started_rate_weights: tuple[tuple[float, str], ...]
    closed_rate_weights: tuple[tuple[float, str], ...]
    stint_count_weights: tuple[tuple[float, str], ...]
    rate_regression_target: float
    start_rate_regression_factor: float
    close_rate_regression_factor: float
    expected_minutes_scale: float
    typical_stint_count: float


@dataclass(slots=True)
class RotationBaselineEstimate:
    expected_stint_count: float
    expected_start_rate: float
    expected_close_rate: float



def estimate_rotation_baseline(
    features: PregameOpportunityFeatures,
    config: RotationConfig,
) -> RotationBaselineEstimate:
    expected_stint_count = _weighted_average(
        [(weight, getattr(features, attr)) for weight, attr in config.stint_count_weights]
    ) or 0.0
    expected_start_rate = _weighted_average(
        [(weight, getattr(features, attr)) for weight, attr in config.started_rate_weights]
    ) or 0.0
    expected_close_rate = _weighted_average(
        [(weight, getattr(features, attr)) for weight, attr in config.closed_rate_weights]
    ) or 0.0

    return RotationBaselineEstimate(
        expected_stint_count=expected_stint_count,
        expected_start_rate=regress_to_target(
            expected_start_rate,
            target=config.rate_regression_target,
            factor=config.start_rate_regression_factor,
            lower=0.0,
            upper=1.0,
        ),
        expected_close_rate=regress_to_target(
            expected_close_rate,
            target=config.rate_regression_target,
            factor=config.close_rate_regression_factor,
            lower=0.0,
            upper=1.0,
        ),
    )



def compute_rotation_role_score(
    *,
    expected_start_rate: float,
    expected_close_rate: float,
    expected_stint_count: float,
    rotation_expected_minutes: float,
    config: RotationConfig,
) -> float:
    rotation_minutes_score = clamp(rotation_expected_minutes / config.expected_minutes_scale, 0.0, 1.2)
    stint_pattern_score = 1.0 - clamp(
        abs(expected_stint_count - config.typical_stint_count) / config.typical_stint_count,
        0.0,
        1.0,
    )
    return clamp(
        0.46 * rotation_minutes_score
        + 0.24 * expected_start_rate
        + 0.15 * expected_close_rate
        + 0.15 * stint_pattern_score,
        0.0,
        1.25,
    )



def compute_started_alignment(features: PregameOpportunityFeatures) -> float:
    return 1.0 - clamp(
        abs(value_or_zero(features.last5_started_rate) - value_or_zero(features.season_started_rate)),
        0.0,
        1.0,
    )



def compute_closed_alignment(features: PregameOpportunityFeatures) -> float:
    return 1.0 - clamp(
        abs(value_or_zero(features.last5_closed_rate) - value_or_zero(features.season_closed_rate)),
        0.0,
        1.0,
    )
