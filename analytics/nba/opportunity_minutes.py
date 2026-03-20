from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from analytics.features_opportunity import PregameOpportunityFeatures, _weighted_average
from analytics.opportunity_math import clamp, regress_to_target, value_or_zero


class MinutesConfig(Protocol):
    expected_minutes_weights: tuple[tuple[float, str], ...]
    expected_rotation_minutes_weights: tuple[tuple[float, str], ...]
    rotation_sample_scale: float
    rotation_minutes_blend_max_weight: float
    minutes_regression_target: float
    minutes_regression_factor: float
    official_unavailable_minutes_cap: float
    projected_unavailable_minutes_scale: float
    late_scratch_minutes_penalty: float


@dataclass(slots=True)
class MinutesBaselineEstimate:
    expected_minutes: float
    rotation_expected_minutes: float
    rotation_sample_confidence: float


@dataclass(slots=True)
class AvailabilityAdjustment:
    expected_minutes: float
    availability_modifier: float



def estimate_minutes_baseline(
    features: PregameOpportunityFeatures,
    config: MinutesConfig,
) -> MinutesBaselineEstimate:
    box_expected_minutes = _weighted_average(
        [(weight, getattr(features, attr)) for weight, attr in config.expected_minutes_weights]
    )
    rotation_expected_minutes = _weighted_average(
        [(weight, getattr(features, attr)) for weight, attr in config.expected_rotation_minutes_weights]
    )

    rotation_sample_confidence = clamp(features.rotation_sample_size / config.rotation_sample_scale, 0.0, 1.0)
    rotation_minutes_weight = (
        config.rotation_minutes_blend_max_weight * rotation_sample_confidence if rotation_expected_minutes is not None else 0.0
    )
    expected_minutes = _weighted_average(
        [
            (1.0 - rotation_minutes_weight, box_expected_minutes),
            (rotation_minutes_weight, rotation_expected_minutes),
        ]
    )
    if expected_minutes is None:
        expected_minutes = box_expected_minutes or rotation_expected_minutes or 0.0

    return MinutesBaselineEstimate(
        expected_minutes=regress_to_target(
            expected_minutes,
            target=config.minutes_regression_target,
            factor=config.minutes_regression_factor,
            lower=0.0,
            upper=48.0,
        ),
        rotation_expected_minutes=value_or_zero(rotation_expected_minutes),
        rotation_sample_confidence=rotation_sample_confidence,
    )



def apply_minutes_availability_gate(
    baseline: MinutesBaselineEstimate,
    features: PregameOpportunityFeatures,
    config: MinutesConfig,
    *,
    pregame_context_confidence: float,
) -> AvailabilityAdjustment:
    expected_minutes = baseline.expected_minutes
    availability_modifier = 1.0

    if features.official_available is False:
        return AvailabilityAdjustment(
            expected_minutes=min(expected_minutes, config.official_unavailable_minutes_cap),
            availability_modifier=0.1,
        )

    if features.projected_available is False:
        expected_minutes *= config.projected_unavailable_minutes_scale
        availability_modifier *= config.projected_unavailable_minutes_scale

    late_scratch_risk = value_or_zero(features.late_scratch_risk)
    scratch_scale = 1.0 - (config.late_scratch_minutes_penalty * pregame_context_confidence * late_scratch_risk)
    expected_minutes *= clamp(scratch_scale, 0.55, 1.0)
    availability_modifier *= clamp(1.0 - 0.65 * late_scratch_risk * pregame_context_confidence, 0.2, 1.0)

    return AvailabilityAdjustment(
        expected_minutes=expected_minutes,
        availability_modifier=availability_modifier,
    )



def compute_minutes_stability(features: PregameOpportunityFeatures) -> float:
    return 1.0 - clamp(value_or_zero(features.last10_minutes_std) / 8.0, 0.0, 1.0)



def compute_rotation_minutes_stability(features: PregameOpportunityFeatures) -> float:
    return 1.0 - clamp(value_or_zero(features.last10_rotation_minutes_std) / 8.0, 0.0, 1.0)
