from __future__ import annotations

from dataclasses import asdict, dataclass

from analytics.features_opportunity import PregameOpportunityFeatures
from analytics.opportunity_context import (
    VacancyAdjustment as _VacancyAdjustment,
    apply_official_team_fallback_adjustments,
    apply_role_vacancy_adjustments,
)
from analytics.opportunity_math import clamp as _clamp
from analytics.opportunity_math import value_or_zero as _value_or_zero
from analytics.opportunity_minutes import (
    MinutesBaselineEstimate as _MinutesBaselineEstimate,
    apply_minutes_availability_gate,
    compute_minutes_stability,
    compute_rotation_minutes_stability,
    estimate_minutes_baseline,
)
from analytics.opportunity_rotation import (
    compute_closed_alignment,
    compute_rotation_role_score,
    compute_started_alignment,
    estimate_rotation_baseline,
)
from analytics.opportunity_usage import compute_offensive_role_score, compute_usage_alignment, estimate_usage_baseline


@dataclass(frozen=True, slots=True)
class PregameOpportunityModelConfig:
    expected_minutes_weights: tuple[tuple[float, str], ...] = (
        (0.50, "season_minutes_avg"),
        (0.30, "last10_minutes_avg"),
        (0.20, "last5_minutes_avg"),
    )
    expected_rotation_minutes_weights: tuple[tuple[float, str], ...] = (
        (0.40, "season_rotation_minutes_avg"),
        (0.35, "last10_rotation_minutes_avg"),
        (0.25, "last5_rotation_minutes_avg"),
    )
    expected_usage_weights: tuple[tuple[float, str], ...] = (
        (0.45, "season_usage_pct"),
        (0.35, "last10_usage_pct"),
        (0.20, "last5_usage_pct"),
    )
    expected_est_usage_weights: tuple[tuple[float, str], ...] = (
        (0.45, "season_est_usage_pct"),
        (0.35, "last10_est_usage_pct"),
        (0.20, "last5_est_usage_pct"),
    )
    touches_weights: tuple[tuple[float, str], ...] = (
        (0.45, "season_touches"),
        (0.35, "last10_touches"),
        (0.20, "last5_touches"),
    )
    passes_weights: tuple[tuple[float, str], ...] = (
        (0.45, "season_passes"),
        (0.35, "last10_passes"),
        (0.20, "last5_passes"),
    )
    started_rate_weights: tuple[tuple[float, str], ...] = (
        (0.35, "season_started_rate"),
        (0.35, "last10_started_rate"),
        (0.30, "last5_started_rate"),
    )
    closed_rate_weights: tuple[tuple[float, str], ...] = (
        (0.35, "season_closed_rate"),
        (0.35, "last10_closed_rate"),
        (0.30, "last5_closed_rate"),
    )
    stint_count_weights: tuple[tuple[float, str], ...] = (
        (0.40, "season_stint_count_avg"),
        (0.35, "last10_stint_count_avg"),
        (0.25, "last5_stint_count_avg"),
    )
    expected_minutes_scale: float = 36.0
    touches_scale: float = 75.0
    passes_scale: float = 60.0
    rotation_sample_scale: float = 8.0
    rotation_minutes_blend_max_weight: float = 0.45
    typical_stint_count: float = 3.0
    minutes_regression_target: float = 31.5
    minutes_regression_factor: float = 0.98
    rate_regression_target: float = 0.5
    start_rate_regression_factor: float = 0.95
    close_rate_regression_factor: float = 0.50
    usage_regression_target: float = 0.18
    usage_regression_factor: float = 0.90
    est_usage_regression_target: float = 0.18
    est_usage_regression_factor: float = 0.90
    touches_scale_factor: float = 0.99
    passes_scale_factor: float = 0.98
    context_start_rate_weight: float = 0.45
    context_minutes_vacated_factor: float = 0.08
    context_minutes_vacated_cap: float = 4.0
    context_usage_vacated_factor: float = 0.30
    context_usage_vacated_cap: float = 0.05
    context_touch_vacated_factor: float = 0.12
    context_touch_vacated_cap: float = 8.0
    context_usage_missing_teammate_bonus: float = 0.01
    context_primary_ballhandler_usage_bonus: float = 0.012
    context_primary_ballhandler_touches_bonus: float = 4.0
    context_primary_ballhandler_passes_bonus: float = 4.0
    context_frontcourt_minutes_bonus: float = 1.4
    role_replacement_minutes_factor: float = 0.11
    role_replacement_minutes_cap: float = 5.5
    role_replacement_usage_factor: float = 0.18
    role_replacement_usage_cap: float = 0.04
    role_replacement_touches_factor: float = 0.08
    role_replacement_touches_cap: float = 7.0
    role_replacement_passes_factor: float = 0.08
    role_replacement_passes_cap: float = 6.0
    absence_impact_minutes_factor: float = 0.0
    absence_impact_minutes_cap: float = 0.0
    absence_impact_usage_factor: float = 0.22
    absence_impact_usage_cap: float = 0.015
    absence_impact_touches_factor: float = 0.08
    absence_impact_touches_cap: float = 3.5
    absence_impact_passes_factor: float = 0.08
    absence_impact_passes_cap: float = 2.5
    absence_impact_confidence_floor: float = 0.35
    official_team_injury_minutes_bonus_cap: float = 8.0
    official_team_injury_start_rate_bonus_cap: float = 0.18
    official_team_injury_touch_bonus_per_minute: float = 1.2
    official_team_injury_pass_bonus_per_minute: float = 0.8
    official_team_injury_out_threshold: float = 2.0
    official_team_injury_out_scale: float = 5.0
    official_team_injury_top9_scale: float = 4.0
    official_team_injury_vacated_minutes_scale: float = 72.0
    official_team_injury_high_usage_scale: float = 2.0
    official_team_injury_headroom_target: float = 24.0
    official_team_injury_headroom_scale: float = 16.0
    official_team_injury_candidate_minutes_scale: float = 18.0
    projected_unavailable_minutes_scale: float = 0.35
    projected_unavailable_usage_scale: float = 0.70
    projected_unavailable_touches_scale: float = 0.50
    official_unavailable_minutes_cap: float = 2.0
    late_scratch_minutes_penalty: float = 0.18


DEFAULT_OPPORTUNITY_CONFIG = PregameOpportunityModelConfig()


@dataclass(slots=True)
class PregameOpportunityBreakdown:
    expected_minutes: float
    expected_rotation_minutes: float
    expected_usage_pct: float
    expected_est_usage_pct: float
    expected_touches: float
    expected_passes: float
    expected_stint_count: float
    expected_start_rate: float
    expected_close_rate: float
    availability_modifier: float
    vacated_minutes_bonus: float
    vacated_usage_bonus: float
    role_replacement_minutes_bonus: float
    role_replacement_usage_bonus: float
    absence_impact_minutes_bonus: float
    absence_impact_usage_bonus: float
    role_stability: float
    rotation_role_score: float
    offensive_role_score: float
    matchup_environment_score: float
    opportunity_score: float
    confidence: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(slots=True)
class PregameOpportunityProjection:
    features: PregameOpportunityFeatures
    breakdown: PregameOpportunityBreakdown


@dataclass(slots=True)
class _BaselineRoleEstimate:
    expected_minutes: float
    rotation_expected_minutes: float
    expected_usage_pct: float
    expected_est_usage_pct: float
    expected_touches: float
    expected_passes: float
    expected_stint_count: float
    expected_start_rate: float
    expected_close_rate: float
    rotation_sample_confidence: float


@dataclass(slots=True)
class _AvailabilityAdjustedRole:
    expected_minutes: float
    expected_usage_pct: float
    expected_est_usage_pct: float
    expected_touches: float
    expected_passes: float
    expected_start_rate: float
    expected_close_rate: float
    availability_modifier: float



def _estimate_baseline_role(
    features: PregameOpportunityFeatures,
    config: PregameOpportunityModelConfig,
) -> _BaselineRoleEstimate:
    minutes_baseline = estimate_minutes_baseline(features, config)
    rotation_baseline = estimate_rotation_baseline(features, config)
    usage_baseline = estimate_usage_baseline(features, config)

    return _BaselineRoleEstimate(
        expected_minutes=minutes_baseline.expected_minutes,
        rotation_expected_minutes=minutes_baseline.rotation_expected_minutes,
        expected_usage_pct=usage_baseline.expected_usage_pct,
        expected_est_usage_pct=usage_baseline.expected_est_usage_pct,
        expected_touches=usage_baseline.expected_touches,
        expected_passes=usage_baseline.expected_passes,
        expected_stint_count=rotation_baseline.expected_stint_count,
        expected_start_rate=rotation_baseline.expected_start_rate,
        expected_close_rate=rotation_baseline.expected_close_rate,
        rotation_sample_confidence=minutes_baseline.rotation_sample_confidence,
    )



def _apply_availability_gate(
    baseline: _BaselineRoleEstimate,
    features: PregameOpportunityFeatures,
    config: PregameOpportunityModelConfig,
    *,
    pregame_context_confidence: float,
) -> _AvailabilityAdjustedRole:
    expected_usage_pct = baseline.expected_usage_pct
    expected_est_usage_pct = baseline.expected_est_usage_pct
    expected_touches = baseline.expected_touches
    expected_passes = baseline.expected_passes
    expected_start_rate = baseline.expected_start_rate
    expected_close_rate = baseline.expected_close_rate

    minutes_adjustment = apply_minutes_availability_gate(
        _MinutesBaselineEstimate(
            expected_minutes=baseline.expected_minutes,
            rotation_expected_minutes=baseline.rotation_expected_minutes,
            rotation_sample_confidence=baseline.rotation_sample_confidence,
        ),
        features,
        config,
        pregame_context_confidence=pregame_context_confidence,
    )
    expected_minutes = minutes_adjustment.expected_minutes
    availability_modifier = minutes_adjustment.availability_modifier

    if features.official_available is False:
        return _AvailabilityAdjustedRole(
            expected_minutes=expected_minutes,
            expected_usage_pct=expected_usage_pct * 0.35,
            expected_est_usage_pct=expected_est_usage_pct * 0.35,
            expected_touches=expected_touches * 0.25,
            expected_passes=expected_passes * 0.25,
            expected_start_rate=0.0,
            expected_close_rate=0.0,
            availability_modifier=availability_modifier,
        )

    if features.projected_available is False:
        expected_usage_pct *= config.projected_unavailable_usage_scale
        expected_est_usage_pct *= config.projected_unavailable_usage_scale
        expected_touches *= config.projected_unavailable_touches_scale
        expected_passes *= config.projected_unavailable_touches_scale
        expected_start_rate *= 0.25
        expected_close_rate *= 0.25

    return _AvailabilityAdjustedRole(
        expected_minutes=expected_minutes,
        expected_usage_pct=expected_usage_pct,
        expected_est_usage_pct=expected_est_usage_pct,
        expected_touches=expected_touches,
        expected_passes=expected_passes,
        expected_start_rate=expected_start_rate,
        expected_close_rate=expected_close_rate,
        availability_modifier=availability_modifier,
    )


def project_pregame_opportunity(
    features: PregameOpportunityFeatures,
    config: PregameOpportunityModelConfig = DEFAULT_OPPORTUNITY_CONFIG,
) -> PregameOpportunityProjection:
    baseline = _estimate_baseline_role(features, config)
    pregame_context_confidence = _value_or_zero(features.pregame_context_confidence)
    starter_confidence = _value_or_zero(features.starter_confidence)
    availability = _apply_availability_gate(
        baseline,
        features,
        config,
        pregame_context_confidence=pregame_context_confidence,
    )
    vacancy = apply_role_vacancy_adjustments(
        availability,
        baseline,
        features,
        config,
        pregame_context_confidence=pregame_context_confidence,
        starter_confidence=starter_confidence,
    )
    vacancy = apply_official_team_fallback_adjustments(
        vacancy,
        availability,
        baseline,
        features,
        config,
    )

    expected_minutes = vacancy.expected_minutes
    expected_usage_pct = vacancy.expected_usage_pct
    expected_est_usage_pct = vacancy.expected_est_usage_pct
    expected_touches = vacancy.expected_touches
    expected_passes = vacancy.expected_passes
    expected_start_rate = vacancy.expected_start_rate
    expected_close_rate = availability.expected_close_rate
    expected_stint_count = baseline.expected_stint_count

    minutes_stability = compute_minutes_stability(features)
    rotation_minutes_stability = compute_rotation_minutes_stability(features)
    usage_alignment = compute_usage_alignment(features)
    started_alignment = compute_started_alignment(features)
    closed_alignment = compute_closed_alignment(features)
    context_alignment = 0.5
    if features.projected_available is not None or features.official_available is not None:
        projected = features.projected_available
        official = features.official_available
        if projected is not None and official is not None:
            context_alignment = 1.0 if projected == official else 0.35
        elif features.projected_lineup_confirmed:
            context_alignment = 0.85
        else:
            context_alignment = 0.65

    role_stability = _clamp(
        0.24 * minutes_stability
        + 0.18 * usage_alignment
        + 0.18 * rotation_minutes_stability
        + 0.10 * started_alignment
        + 0.08 * closed_alignment
        + 0.08 * baseline.rotation_sample_confidence
        + 0.08 * pregame_context_confidence
        + 0.06 * context_alignment
        + 0.04 * (1.0 - _value_or_zero(features.late_scratch_risk)),
        0.0,
        1.0,
    )

    rotation_role_score = compute_rotation_role_score(
        expected_start_rate=expected_start_rate,
        expected_close_rate=expected_close_rate,
        expected_stint_count=expected_stint_count,
        rotation_expected_minutes=baseline.rotation_expected_minutes,
        config=config,
    )
    offensive_role_score = compute_offensive_role_score(
        expected_minutes=expected_minutes,
        expected_usage_pct=expected_usage_pct,
        expected_est_usage_pct=expected_est_usage_pct,
        expected_touches=expected_touches,
        expected_passes=expected_passes,
        rotation_role_score=rotation_role_score,
        config=config,
    )

    matchup_environment_score = 0.5
    if features.team_pace is not None and features.opponent_pace is not None and features.league_avg_pace is not None:
        matchup_environment_score = _clamp(
            (((features.team_pace + features.opponent_pace) / 2.0) - features.league_avg_pace) / 6.0 + 0.5,
            0.0,
            1.0,
        )

    opportunity_score = _clamp(
        0.48 * offensive_role_score
        + 0.24 * role_stability
        + 0.14 * matchup_environment_score
        + 0.10 * rotation_role_score
        + 0.04 * pregame_context_confidence,
        0.0,
        1.25,
    ) * availability.availability_modifier
    confidence = _clamp(
        0.24 * role_stability
        + 0.20 * minutes_stability
        + 0.12 * rotation_minutes_stability
        + 0.12 * baseline.rotation_sample_confidence
        + 0.10 * _clamp(features.sample_size / 10.0, 0.0, 1.0)
        + 0.10 * matchup_environment_score
        + 0.07 * pregame_context_confidence
        + 0.05 * context_alignment,
        0.0,
        1.0,
    ) * _clamp(max(availability.availability_modifier, 0.25), 0.25, 1.0)

    return PregameOpportunityProjection(
        features=features,
        breakdown=PregameOpportunityBreakdown(
            expected_minutes=round(expected_minutes, 3),
            expected_rotation_minutes=round(baseline.rotation_expected_minutes, 3),
            expected_usage_pct=round(expected_usage_pct, 4),
            expected_est_usage_pct=round(expected_est_usage_pct, 4),
            expected_touches=round(expected_touches, 3),
            expected_passes=round(expected_passes, 3),
            expected_stint_count=round(expected_stint_count, 3),
            expected_start_rate=round(expected_start_rate, 4),
            expected_close_rate=round(expected_close_rate, 4),
            availability_modifier=round(availability.availability_modifier, 4),
            vacated_minutes_bonus=round(vacancy.vacated_minutes_bonus, 3),
            vacated_usage_bonus=round(vacancy.vacated_usage_bonus, 4),
            role_replacement_minutes_bonus=round(vacancy.role_replacement_minutes_bonus, 3),
            role_replacement_usage_bonus=round(vacancy.role_replacement_usage_bonus, 4),
            absence_impact_minutes_bonus=round(vacancy.absence_impact_minutes_bonus, 3),
            absence_impact_usage_bonus=round(vacancy.absence_impact_usage_bonus, 4),
            role_stability=round(role_stability, 4),
            rotation_role_score=round(rotation_role_score, 4),
            offensive_role_score=round(offensive_role_score, 4),
            matchup_environment_score=round(matchup_environment_score, 4),
            opportunity_score=round(opportunity_score, 4),
            confidence=round(confidence, 4),
        ),
    )
