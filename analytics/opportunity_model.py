from __future__ import annotations

from dataclasses import asdict, dataclass

from analytics.features_opportunity import PregameOpportunityFeatures, _weighted_average


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


@dataclass(slots=True)
class _VacancyAdjustment:
    expected_minutes: float
    expected_usage_pct: float
    expected_est_usage_pct: float
    expected_touches: float
    expected_passes: float
    expected_start_rate: float
    vacated_minutes_bonus: float
    vacated_usage_bonus: float



def _value_or_zero(value: float | None) -> float:
    return float(value) if value is not None else 0.0



def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))



def _regress_to_target(value: float, *, target: float, factor: float, lower: float | None = None, upper: float | None = None) -> float:
    regressed = target + factor * (value - target)
    if lower is not None or upper is not None:
        regressed = _clamp(regressed, lower if lower is not None else regressed, upper if upper is not None else regressed)
    return regressed



def _estimate_baseline_role(
    features: PregameOpportunityFeatures,
    config: PregameOpportunityModelConfig,
) -> _BaselineRoleEstimate:
    box_expected_minutes = _weighted_average(
        [(weight, getattr(features, attr)) for weight, attr in config.expected_minutes_weights]
    )
    rotation_expected_minutes = _weighted_average(
        [(weight, getattr(features, attr)) for weight, attr in config.expected_rotation_minutes_weights]
    )
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
    expected_stint_count = _weighted_average(
        [(weight, getattr(features, attr)) for weight, attr in config.stint_count_weights]
    ) or 0.0
    expected_start_rate = _weighted_average(
        [(weight, getattr(features, attr)) for weight, attr in config.started_rate_weights]
    ) or 0.0
    expected_close_rate = _weighted_average(
        [(weight, getattr(features, attr)) for weight, attr in config.closed_rate_weights]
    ) or 0.0

    rotation_sample_confidence = _clamp(features.rotation_sample_size / config.rotation_sample_scale, 0.0, 1.0)
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

    return _BaselineRoleEstimate(
        expected_minutes=_regress_to_target(
            expected_minutes,
            target=config.minutes_regression_target,
            factor=config.minutes_regression_factor,
            lower=0.0,
            upper=48.0,
        ),
        rotation_expected_minutes=_value_or_zero(rotation_expected_minutes),
        expected_usage_pct=_regress_to_target(
            expected_usage_pct,
            target=config.usage_regression_target,
            factor=config.usage_regression_factor,
            lower=0.0,
            upper=0.5,
        ),
        expected_est_usage_pct=_regress_to_target(
            expected_est_usage_pct,
            target=config.est_usage_regression_target,
            factor=config.est_usage_regression_factor,
            lower=0.0,
            upper=0.5,
        ),
        expected_touches=max(0.0, expected_touches * config.touches_scale_factor),
        expected_passes=max(0.0, expected_passes * config.passes_scale_factor),
        expected_stint_count=expected_stint_count,
        expected_start_rate=_regress_to_target(
            expected_start_rate,
            target=config.rate_regression_target,
            factor=config.start_rate_regression_factor,
            lower=0.0,
            upper=1.0,
        ),
        expected_close_rate=_regress_to_target(
            expected_close_rate,
            target=config.rate_regression_target,
            factor=config.close_rate_regression_factor,
            lower=0.0,
            upper=1.0,
        ),
        rotation_sample_confidence=rotation_sample_confidence,
    )



def _apply_availability_gate(
    baseline: _BaselineRoleEstimate,
    features: PregameOpportunityFeatures,
    config: PregameOpportunityModelConfig,
    *,
    pregame_context_confidence: float,
) -> _AvailabilityAdjustedRole:
    expected_minutes = baseline.expected_minutes
    expected_usage_pct = baseline.expected_usage_pct
    expected_est_usage_pct = baseline.expected_est_usage_pct
    expected_touches = baseline.expected_touches
    expected_passes = baseline.expected_passes
    expected_start_rate = baseline.expected_start_rate
    expected_close_rate = baseline.expected_close_rate
    availability_modifier = 1.0

    if features.official_available is False:
        return _AvailabilityAdjustedRole(
            expected_minutes=min(expected_minutes, config.official_unavailable_minutes_cap),
            expected_usage_pct=expected_usage_pct * 0.35,
            expected_est_usage_pct=expected_est_usage_pct * 0.35,
            expected_touches=expected_touches * 0.25,
            expected_passes=expected_passes * 0.25,
            expected_start_rate=0.0,
            expected_close_rate=0.0,
            availability_modifier=0.1,
        )

    if features.projected_available is False:
        expected_minutes *= config.projected_unavailable_minutes_scale
        expected_usage_pct *= config.projected_unavailable_usage_scale
        expected_est_usage_pct *= config.projected_unavailable_usage_scale
        expected_touches *= config.projected_unavailable_touches_scale
        expected_passes *= config.projected_unavailable_touches_scale
        expected_start_rate *= 0.25
        expected_close_rate *= 0.25
        availability_modifier *= config.projected_unavailable_minutes_scale

    late_scratch_risk = _value_or_zero(features.late_scratch_risk)
    scratch_scale = 1.0 - (config.late_scratch_minutes_penalty * pregame_context_confidence * late_scratch_risk)
    expected_minutes *= _clamp(scratch_scale, 0.55, 1.0)
    availability_modifier *= _clamp(1.0 - 0.65 * late_scratch_risk * pregame_context_confidence, 0.2, 1.0)

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



def _apply_role_vacancy_adjustments(
    role: _AvailabilityAdjustedRole,
    baseline: _BaselineRoleEstimate,
    features: PregameOpportunityFeatures,
    config: PregameOpportunityModelConfig,
    *,
    pregame_context_confidence: float,
    starter_confidence: float,
) -> _VacancyAdjustment:
    expected_minutes = role.expected_minutes
    expected_usage_pct = role.expected_usage_pct
    expected_est_usage_pct = role.expected_est_usage_pct
    expected_touches = role.expected_touches
    expected_passes = role.expected_passes
    expected_start_rate = role.expected_start_rate

    if role.availability_modifier <= 0.15:
        return _VacancyAdjustment(
            expected_minutes=expected_minutes,
            expected_usage_pct=expected_usage_pct,
            expected_est_usage_pct=expected_est_usage_pct,
            expected_touches=expected_touches,
            expected_passes=expected_passes,
            expected_start_rate=expected_start_rate,
            vacated_minutes_bonus=0.0,
            vacated_usage_bonus=0.0,
        )

    if features.expected_start is not None:
        context_start_rate = 1.0 if features.expected_start else 0.0
        start_blend_weight = _clamp(
            config.context_start_rate_weight * pregame_context_confidence * max(starter_confidence, 0.35),
            0.0,
            0.85,
        )
        expected_start_rate = _weighted_average(
            [
                (1.0 - start_blend_weight, expected_start_rate),
                (start_blend_weight, context_start_rate),
            ]
        ) or expected_start_rate

    vacated_minutes_bonus = _clamp(
        _value_or_zero(features.vacated_minutes_proxy) * config.context_minutes_vacated_factor,
        0.0,
        config.context_minutes_vacated_cap,
    ) * pregame_context_confidence
    expected_minutes += vacated_minutes_bonus

    vacated_usage_bonus = _clamp(
        _value_or_zero(features.vacated_usage_proxy) * config.context_usage_vacated_factor
        + _value_or_zero(features.missing_high_usage_teammates) * config.context_usage_missing_teammate_bonus
        + (config.context_primary_ballhandler_usage_bonus if features.missing_primary_ballhandler else 0.0),
        0.0,
        config.context_usage_vacated_cap,
    ) * pregame_context_confidence
    expected_usage_pct = _clamp(expected_usage_pct + vacated_usage_bonus, 0.0, 0.5)
    expected_est_usage_pct = _clamp(expected_est_usage_pct + vacated_usage_bonus * 0.85, 0.0, 0.5)
    expected_touches += _clamp(
        _value_or_zero(features.vacated_minutes_proxy) * config.context_touch_vacated_factor,
        0.0,
        config.context_touch_vacated_cap,
    ) * pregame_context_confidence
    if features.missing_primary_ballhandler:
        expected_touches += config.context_primary_ballhandler_touches_bonus * pregame_context_confidence
        expected_passes += config.context_primary_ballhandler_passes_bonus * pregame_context_confidence

    return _VacancyAdjustment(
        expected_minutes=expected_minutes,
        expected_usage_pct=expected_usage_pct,
        expected_est_usage_pct=expected_est_usage_pct,
        expected_touches=expected_touches,
        expected_passes=expected_passes,
        expected_start_rate=expected_start_rate,
        vacated_minutes_bonus=vacated_minutes_bonus,
        vacated_usage_bonus=vacated_usage_bonus,
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
    vacancy = _apply_role_vacancy_adjustments(
        availability,
        baseline,
        features,
        config,
        pregame_context_confidence=pregame_context_confidence,
        starter_confidence=starter_confidence,
    )

    expected_minutes = vacancy.expected_minutes
    expected_usage_pct = vacancy.expected_usage_pct
    expected_est_usage_pct = vacancy.expected_est_usage_pct
    expected_touches = vacancy.expected_touches
    expected_passes = vacancy.expected_passes
    expected_start_rate = vacancy.expected_start_rate
    expected_close_rate = availability.expected_close_rate
    expected_stint_count = baseline.expected_stint_count

    minutes_stability = 1.0 - _clamp(_value_or_zero(features.last10_minutes_std) / 8.0, 0.0, 1.0)
    rotation_minutes_stability = 1.0 - _clamp(_value_or_zero(features.last10_rotation_minutes_std) / 8.0, 0.0, 1.0)
    usage_alignment = 1.0 - _clamp(
        abs(_value_or_zero(features.last5_usage_pct) - _value_or_zero(features.season_usage_pct)) / 0.12,
        0.0,
        1.0,
    )
    started_alignment = 1.0 - _clamp(
        abs(_value_or_zero(features.last5_started_rate) - _value_or_zero(features.season_started_rate)),
        0.0,
        1.0,
    )
    closed_alignment = 1.0 - _clamp(
        abs(_value_or_zero(features.last5_closed_rate) - _value_or_zero(features.season_closed_rate)),
        0.0,
        1.0,
    )
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

    minutes_score = _clamp(expected_minutes / config.expected_minutes_scale, 0.0, 1.2)
    usage_score = _clamp(((expected_usage_pct + expected_est_usage_pct) / 2.0) / 0.30, 0.0, 1.2)
    touches_score = _clamp(expected_touches / config.touches_scale, 0.0, 1.2)
    passes_score = _clamp(expected_passes / config.passes_scale, 0.0, 1.2)
    rotation_minutes_score = _clamp(baseline.rotation_expected_minutes / config.expected_minutes_scale, 0.0, 1.2)
    stint_pattern_score = 1.0 - _clamp(
        abs(expected_stint_count - config.typical_stint_count) / config.typical_stint_count,
        0.0,
        1.0,
    )
    rotation_role_score = _clamp(
        0.46 * rotation_minutes_score
        + 0.24 * expected_start_rate
        + 0.15 * expected_close_rate
        + 0.15 * stint_pattern_score,
        0.0,
        1.25,
    )
    offensive_role_score = _clamp(
        0.34 * minutes_score
        + 0.30 * usage_score
        + 0.14 * touches_score
        + 0.08 * passes_score
        + 0.14 * rotation_role_score,
        0.0,
        1.25,
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
            role_stability=round(role_stability, 4),
            rotation_role_score=round(rotation_role_score, 4),
            offensive_role_score=round(offensive_role_score, 4),
            matchup_environment_score=round(matchup_environment_score, 4),
            opportunity_score=round(opportunity_score, 4),
            confidence=round(confidence, 4),
        ),
    )
