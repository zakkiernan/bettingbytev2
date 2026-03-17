from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from analytics.features_opportunity import PregameOpportunityFeatures, _weighted_average
from analytics.opportunity_math import clamp, value_or_zero


class ContextRoleState(Protocol):
    expected_minutes: float
    expected_usage_pct: float
    expected_est_usage_pct: float
    expected_touches: float
    expected_passes: float
    expected_start_rate: float
    availability_modifier: float


class ContextBaselineState(Protocol):
    rotation_expected_minutes: float


class ContextConfig(Protocol):
    context_start_rate_weight: float
    context_minutes_vacated_factor: float
    context_minutes_vacated_cap: float
    context_usage_vacated_factor: float
    context_usage_vacated_cap: float
    context_touch_vacated_factor: float
    context_touch_vacated_cap: float
    context_usage_missing_teammate_bonus: float
    context_primary_ballhandler_usage_bonus: float
    context_primary_ballhandler_touches_bonus: float
    context_primary_ballhandler_passes_bonus: float
    context_frontcourt_minutes_bonus: float
    role_replacement_minutes_factor: float
    role_replacement_minutes_cap: float
    role_replacement_usage_factor: float
    role_replacement_usage_cap: float
    role_replacement_touches_factor: float
    role_replacement_touches_cap: float
    role_replacement_passes_factor: float
    role_replacement_passes_cap: float
    absence_impact_minutes_factor: float
    absence_impact_minutes_cap: float
    absence_impact_usage_factor: float
    absence_impact_usage_cap: float
    absence_impact_touches_factor: float
    absence_impact_touches_cap: float
    absence_impact_passes_factor: float
    absence_impact_passes_cap: float
    absence_impact_confidence_floor: float
    official_team_injury_minutes_bonus_cap: float
    official_team_injury_start_rate_bonus_cap: float
    official_team_injury_touch_bonus_per_minute: float
    official_team_injury_pass_bonus_per_minute: float
    official_team_injury_out_threshold: float
    official_team_injury_out_scale: float
    official_team_injury_top9_scale: float
    official_team_injury_vacated_minutes_scale: float
    official_team_injury_high_usage_scale: float
    official_team_injury_headroom_target: float
    official_team_injury_headroom_scale: float
    official_team_injury_candidate_minutes_scale: float


@dataclass(slots=True)
class VacancyAdjustment:
    expected_minutes: float
    expected_usage_pct: float
    expected_est_usage_pct: float
    expected_touches: float
    expected_passes: float
    expected_start_rate: float
    vacated_minutes_bonus: float
    vacated_usage_bonus: float
    role_replacement_minutes_bonus: float
    role_replacement_usage_bonus: float
    absence_impact_minutes_bonus: float
    absence_impact_usage_bonus: float



def apply_role_vacancy_adjustments(
    role: ContextRoleState,
    baseline: ContextBaselineState,
    features: PregameOpportunityFeatures,
    config: ContextConfig,
    *,
    pregame_context_confidence: float,
    starter_confidence: float,
) -> VacancyAdjustment:
    expected_minutes = role.expected_minutes
    expected_usage_pct = role.expected_usage_pct
    expected_est_usage_pct = role.expected_est_usage_pct
    expected_touches = role.expected_touches
    expected_passes = role.expected_passes
    expected_start_rate = role.expected_start_rate

    if role.availability_modifier <= 0.15:
        return VacancyAdjustment(
            expected_minutes=expected_minutes,
            expected_usage_pct=expected_usage_pct,
            expected_est_usage_pct=expected_est_usage_pct,
            expected_touches=expected_touches,
            expected_passes=expected_passes,
            expected_start_rate=expected_start_rate,
            vacated_minutes_bonus=0.0,
            vacated_usage_bonus=0.0,
            role_replacement_minutes_bonus=0.0,
            role_replacement_usage_bonus=0.0,
            absence_impact_minutes_bonus=0.0,
            absence_impact_usage_bonus=0.0,
        )

    if features.expected_start is not None:
        context_start_rate = 1.0 if features.expected_start else 0.0
        start_blend_weight = clamp(
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

    vacated_minutes_bonus = clamp(
        value_or_zero(features.vacated_minutes_proxy) * config.context_minutes_vacated_factor,
        0.0,
        config.context_minutes_vacated_cap,
    ) * pregame_context_confidence

    role_replacement_minutes_bonus = clamp(
        value_or_zero(features.role_replacement_minutes_proxy) * config.role_replacement_minutes_factor,
        0.0,
        config.role_replacement_minutes_cap,
    ) * pregame_context_confidence
    if features.missing_frontcourt_rotation_piece:
        role_replacement_minutes_bonus += config.context_frontcourt_minutes_bonus * pregame_context_confidence
    expected_minutes += vacated_minutes_bonus + role_replacement_minutes_bonus

    vacated_usage_bonus = clamp(
        value_or_zero(features.vacated_usage_proxy) * config.context_usage_vacated_factor
        + value_or_zero(features.missing_high_usage_teammates) * config.context_usage_missing_teammate_bonus
        + (config.context_primary_ballhandler_usage_bonus if features.missing_primary_ballhandler else 0.0),
        0.0,
        config.context_usage_vacated_cap,
    ) * pregame_context_confidence
    role_replacement_usage_bonus = clamp(
        value_or_zero(features.role_replacement_usage_proxy) * config.role_replacement_usage_factor,
        0.0,
        config.role_replacement_usage_cap,
    ) * pregame_context_confidence
    expected_usage_pct = clamp(expected_usage_pct + vacated_usage_bonus + role_replacement_usage_bonus, 0.0, 0.5)
    expected_est_usage_pct = clamp(expected_est_usage_pct + (vacated_usage_bonus + role_replacement_usage_bonus) * 0.85, 0.0, 0.5)
    expected_touches += clamp(
        value_or_zero(features.vacated_minutes_proxy) * config.context_touch_vacated_factor,
        0.0,
        config.context_touch_vacated_cap,
    ) * pregame_context_confidence
    expected_touches += clamp(
        value_or_zero(features.role_replacement_touches_proxy) * config.role_replacement_touches_factor,
        0.0,
        config.role_replacement_touches_cap,
    ) * pregame_context_confidence
    expected_passes += clamp(
        value_or_zero(features.role_replacement_passes_proxy) * config.role_replacement_passes_factor,
        0.0,
        config.role_replacement_passes_cap,
    ) * pregame_context_confidence
    if features.missing_primary_ballhandler:
        expected_touches += config.context_primary_ballhandler_touches_bonus * pregame_context_confidence
        expected_passes += config.context_primary_ballhandler_passes_bonus * pregame_context_confidence

    absence_impact_confidence = clamp(value_or_zero(features.absence_impact_sample_confidence), 0.0, 1.0)
    absence_impact_weight = clamp(
        (absence_impact_confidence - config.absence_impact_confidence_floor) / max(1.0 - config.absence_impact_confidence_floor, 0.01),
        0.0,
        1.0,
    )
    absence_impact_weight *= absence_impact_weight
    absence_impact_minutes_bonus = clamp(
        value_or_zero(features.absence_impact_minutes_delta) * config.absence_impact_minutes_factor,
        0.0,
        config.absence_impact_minutes_cap,
    ) * absence_impact_weight
    absence_impact_usage_bonus = clamp(
        value_or_zero(features.absence_impact_usage_delta) * config.absence_impact_usage_factor,
        0.0,
        config.absence_impact_usage_cap,
    ) * absence_impact_weight
    expected_minutes += absence_impact_minutes_bonus
    expected_usage_pct = clamp(expected_usage_pct + absence_impact_usage_bonus, 0.0, 0.5)
    expected_est_usage_pct = clamp(expected_est_usage_pct + absence_impact_usage_bonus * 0.85, 0.0, 0.5)
    expected_touches += clamp(
        value_or_zero(features.absence_impact_touches_delta) * config.absence_impact_touches_factor,
        0.0,
        config.absence_impact_touches_cap,
    ) * absence_impact_weight
    expected_passes += clamp(
        value_or_zero(features.absence_impact_passes_delta) * config.absence_impact_passes_factor,
        0.0,
        config.absence_impact_passes_cap,
    ) * absence_impact_weight

    return VacancyAdjustment(
        expected_minutes=expected_minutes,
        expected_usage_pct=expected_usage_pct,
        expected_est_usage_pct=expected_est_usage_pct,
        expected_touches=expected_touches,
        expected_passes=expected_passes,
        expected_start_rate=expected_start_rate,
        vacated_minutes_bonus=vacated_minutes_bonus,
        vacated_usage_bonus=vacated_usage_bonus,
        role_replacement_minutes_bonus=role_replacement_minutes_bonus,
        role_replacement_usage_bonus=role_replacement_usage_bonus,
        absence_impact_minutes_bonus=absence_impact_minutes_bonus,
        absence_impact_usage_bonus=absence_impact_usage_bonus,
    )



def apply_official_team_fallback_adjustments(
    vacancy: VacancyAdjustment,
    role: ContextRoleState,
    baseline: ContextBaselineState,
    features: PregameOpportunityFeatures,
    config: ContextConfig,
) -> VacancyAdjustment:
    if features.context_source != "official_injury_team":
        return vacancy

    role_signal_present = any(
        value not in (None, 0, 0.0, False)
        for value in (
            features.teammate_out_count_top9,
            features.vacated_minutes_proxy,
            features.role_replacement_minutes_proxy,
            features.missing_high_usage_teammates,
            features.missing_primary_ballhandler,
            features.missing_frontcourt_rotation_piece,
        )
    )
    if not role_signal_present:
        return vacancy

    expected_minutes = vacancy.expected_minutes
    headroom = clamp(
        (config.official_team_injury_headroom_target - min(expected_minutes, config.official_team_injury_headroom_target))
        / config.official_team_injury_headroom_scale,
        0.0,
        1.0,
    )
    if headroom <= 0.0:
        return vacancy

    candidate_minutes = max(baseline.rotation_expected_minutes, role.expected_minutes)
    candidate_factor = clamp(candidate_minutes / config.official_team_injury_candidate_minutes_scale, 0.25, 1.0)
    out_pressure = clamp(
        (value_or_zero(features.official_teammate_out_count) - config.official_team_injury_out_threshold)
        / config.official_team_injury_out_scale,
        0.0,
        1.0,
    )
    top9_pressure = clamp(value_or_zero(features.teammate_out_count_top9) / config.official_team_injury_top9_scale, 0.0, 1.0)
    vacated_minutes_pressure = clamp(
        value_or_zero(features.vacated_minutes_proxy) / config.official_team_injury_vacated_minutes_scale,
        0.0,
        1.0,
    )
    high_usage_pressure = clamp(
        value_or_zero(features.missing_high_usage_teammates) / config.official_team_injury_high_usage_scale,
        0.0,
        1.0,
    )
    pressure = max(
        out_pressure,
        (out_pressure + top9_pressure + vacated_minutes_pressure + high_usage_pressure) / 4.0,
    )
    if pressure <= 0.0:
        return vacancy

    expansion_factor = pressure * headroom * candidate_factor
    if expansion_factor <= 0.0:
        return vacancy

    minutes_bonus = config.official_team_injury_minutes_bonus_cap * expansion_factor
    start_rate_bonus = config.official_team_injury_start_rate_bonus_cap * expansion_factor

    return VacancyAdjustment(
        expected_minutes=vacancy.expected_minutes + minutes_bonus,
        expected_usage_pct=vacancy.expected_usage_pct,
        expected_est_usage_pct=vacancy.expected_est_usage_pct,
        expected_touches=vacancy.expected_touches + minutes_bonus * config.official_team_injury_touch_bonus_per_minute,
        expected_passes=vacancy.expected_passes + minutes_bonus * config.official_team_injury_pass_bonus_per_minute,
        expected_start_rate=clamp(vacancy.expected_start_rate + start_rate_bonus, 0.0, 0.55),
        vacated_minutes_bonus=vacancy.vacated_minutes_bonus + minutes_bonus,
        vacated_usage_bonus=vacancy.vacated_usage_bonus,
        role_replacement_minutes_bonus=vacancy.role_replacement_minutes_bonus,
        role_replacement_usage_bonus=vacancy.role_replacement_usage_bonus,
        absence_impact_minutes_bonus=vacancy.absence_impact_minutes_bonus,
        absence_impact_usage_bonus=vacancy.absence_impact_usage_bonus,
    )
