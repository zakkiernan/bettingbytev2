from __future__ import annotations

from dataclasses import fields
from statistics import NormalDist
from typing import Any, Literal

from analytics.assists_model import project_pregame_assists
from analytics.features_assists import PregameAssistsFeatures, build_pregame_assists_features
from analytics.features_opportunity import PregameOpportunityFeatures
from analytics.features_pregame import PregamePointsFeatures, build_pregame_points_features
from analytics.features_rebounds import PregameReboundsFeatures, build_pregame_rebounds_features
from analytics.features_threes import PregameThreesFeatures, build_pregame_threes_features
from analytics.opportunity_model import project_pregame_opportunity
from analytics.pregame_model import project_pregame_points
from analytics.rebounds_model import project_pregame_rebounds
from analytics.threes_model import project_pregame_threes
from analytics.nba.signals_types import (
    SignalBreakdown,
    SignalFeatureSnapshot,
    SignalInjuryEntry,
    SignalOpportunityContext,
    StatsSignalProfile,
)
from database.models import HistoricalGameLog, PlayerPropSnapshot

POINTS_STAT_TYPE = "points"
SUPPORTED_STAT_TYPES = ("points", "rebounds", "assists", "threes")
MAX_RECENT_LOGS = 10

_MINUTES_WEIGHTS: tuple[tuple[float, str], ...] = (
    (0.50, "season_minutes_avg"),
    (0.30, "last10_minutes_avg"),
    (0.20, "last5_minutes_avg"),
)
_ROTATION_MINUTES_WEIGHTS: tuple[tuple[float, str], ...] = (
    (0.40, "season_rotation_minutes_avg"),
    (0.35, "last10_rotation_minutes_avg"),
    (0.25, "last5_rotation_minutes_avg"),
)
_USAGE_WEIGHTS: tuple[tuple[float, str], ...] = (
    (0.45, "season_usage_pct"),
    (0.35, "last10_usage_pct"),
    (0.20, "last5_usage_pct"),
)
_TOUCHES_WEIGHTS: tuple[tuple[float, str], ...] = (
    (0.45, "season_touches"),
    (0.35, "last10_touches"),
    (0.20, "last5_touches"),
)
_START_RATE_WEIGHTS: tuple[tuple[float, str], ...] = (
    (0.35, "season_started_rate"),
    (0.35, "last10_started_rate"),
    (0.30, "last5_started_rate"),
)
_CLOSE_RATE_WEIGHTS: tuple[tuple[float, str], ...] = (
    (0.35, "season_closed_rate"),
    (0.35, "last10_closed_rate"),
    (0.30, "last5_closed_rate"),
)
_INJURY_STATUS_LABELS = {
    "OUT": "Out",
    "DOUBTFUL": "Doubtful",
    "QUESTIONABLE": "Questionable",
    "PROBABLE": "Probable",
}
_STAT_LOG_ATTRS = {
    "points": "points",
    "rebounds": "rebounds",
    "assists": "assists",
    "threes": "threes_made",
}
_STAT_PROJECTORS = {
    "points": project_pregame_points,
    "rebounds": project_pregame_rebounds,
    "assists": project_pregame_assists,
    "threes": project_pregame_threes,
}
STAT_FEATURE_BUILDERS = {
    "points": build_pregame_points_features,
    "rebounds": build_pregame_rebounds_features,
    "assists": build_pregame_assists_features,
    "threes": build_pregame_threes_features,
}


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _float_or_none(value: float | int | None) -> float | None:
    return float(value) if value is not None else None


def _value_or_zero(value: float | int | None) -> float:
    return float(value) if value is not None else 0.0


def _weighted_average(weighted_values: list[tuple[float, float | None]]) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for weight, value in weighted_values:
        if value is None:
            continue
        numerator += weight * float(value)
        denominator += weight
    if denominator <= 0:
        return None
    return numerator / denominator


def _ppm(features: PregamePointsFeatures) -> float:
    weighted_values: list[tuple[float, float | None]] = []
    for weight, points_attr, minutes_attr in (
        (0.50, "season_points_avg", "season_minutes_avg"),
        (0.30, "last10_points_avg", "last10_minutes_avg"),
        (0.20, "last5_points_avg", "last5_minutes_avg"),
    ):
        points = _float_or_none(getattr(features, points_attr))
        minutes = _float_or_none(getattr(features, minutes_attr))
        if points is None or minutes is None or minutes <= 0:
            continue
        weighted_values.append((weight, points / minutes))

    ppm = _weighted_average(weighted_values)
    if ppm is None or ppm <= 0:
        return 0.65
    return _clamp(ppm, 0.35, 1.15)


def _title_case_status(status: str | None) -> str | None:
    if status is None:
        return None
    return _INJURY_STATUS_LABELS.get(str(status).upper())


def _recent_hit_rate(recent_logs: list[HistoricalGameLog], line: float, *, stat_type: str) -> tuple[float | None, int]:
    stat_attr = _STAT_LOG_ATTRS.get(stat_type, "points")
    results = [float(getattr(row, stat_attr) or 0.0) > line for row in recent_logs[:MAX_RECENT_LOGS]]
    if not results:
        return None, 0
    return sum(1 for hit in results if hit) / len(results), len(results)


def _line_probability(projected_value: float, line: float, last10_points_std: float | None) -> tuple[float, float]:
    distribution_std = max(4.0, _value_or_zero(last10_points_std), projected_value * 0.18)
    distribution = NormalDist(mu=projected_value, sigma=distribution_std)
    over_probability = 1.0 - distribution.cdf(line)
    over_probability = _clamp(over_probability, 0.0, 1.0)
    return over_probability, 1.0 - over_probability


def _availability_modifier(features: PregamePointsFeatures, *, context_confidence: float) -> float:
    if features.official_available is False:
        return 0.12
    modifier = 1.0
    if features.projected_available is False:
        modifier *= 0.40
    if features.late_scratch_risk is not None:
        modifier *= _clamp(1.0 - (float(features.late_scratch_risk) * context_confidence * 0.30), 0.35, 1.0)
    return modifier


def _build_opportunity_snapshot(features: PregamePointsFeatures) -> tuple[SignalOpportunityContext, dict[str, float]]:
    context_confidence = _value_or_zero(features.pregame_context_confidence)

    minutes_base = _weighted_average(
        [(weight, _float_or_none(getattr(features, attr))) for weight, attr in _MINUTES_WEIGHTS]
    ) or 0.0
    rotation_minutes = _weighted_average(
        [(weight, _float_or_none(getattr(features, attr))) for weight, attr in _ROTATION_MINUTES_WEIGHTS]
    )
    rotation_weight = 0.30 * _clamp(features.rotation_sample_size / 8.0, 0.0, 1.0) if rotation_minutes is not None else 0.0
    expected_minutes = _weighted_average(
        [
            (1.0 - rotation_weight, minutes_base),
            (rotation_weight, rotation_minutes),
        ]
    ) or minutes_base

    availability_modifier = _availability_modifier(features, context_confidence=context_confidence)

    vacated_minutes_bonus = _clamp(
        _value_or_zero(features.vacated_minutes_proxy) * 0.05,
        0.0,
        2.5,
    ) * context_confidence
    vacated_usage_bonus = _clamp(
        _value_or_zero(features.vacated_usage_proxy) * 0.22
        + _value_or_zero(features.missing_high_usage_teammates) * 0.006
        + (0.010 if features.missing_primary_ballhandler else 0.0),
        0.0,
        0.045,
    ) * context_confidence
    role_replacement_minutes_bonus = _clamp(
        _value_or_zero(features.role_replacement_minutes_proxy) * 0.035,
        0.0,
        2.5,
    ) * context_confidence
    if features.missing_frontcourt_rotation_piece:
        role_replacement_minutes_bonus += 0.9 * context_confidence

    role_replacement_usage_bonus = _clamp(
        _value_or_zero(features.role_replacement_usage_proxy) * 0.14,
        0.0,
        0.025,
    ) * context_confidence

    absence_confidence = _clamp(_value_or_zero(features.absence_impact_sample_confidence), 0.0, 1.0)
    absence_minutes_bonus = _clamp(
        _value_or_zero(features.absence_impact_minutes_delta) * 0.10,
        0.0,
        1.5,
    ) * absence_confidence
    absence_usage_bonus = _clamp(
        _value_or_zero(features.absence_impact_usage_delta) * 0.16,
        0.0,
        0.020,
    ) * absence_confidence

    expected_minutes = max(
        0.0,
        expected_minutes * availability_modifier + vacated_minutes_bonus + role_replacement_minutes_bonus + absence_minutes_bonus,
    )

    expected_usage_pct = _weighted_average(
        [(weight, _float_or_none(getattr(features, attr))) for weight, attr in _USAGE_WEIGHTS]
    ) or 0.0
    expected_usage_pct = _clamp(
        expected_usage_pct + vacated_usage_bonus + role_replacement_usage_bonus + absence_usage_bonus,
        0.0,
        0.45,
    )

    expected_touches = _weighted_average(
        [(weight, _float_or_none(getattr(features, attr))) for weight, attr in _TOUCHES_WEIGHTS]
    ) or 0.0
    expected_touches += _clamp(_value_or_zero(features.role_replacement_touches_proxy) * 0.08, 0.0, 4.0) * context_confidence
    expected_touches += _clamp(_value_or_zero(features.absence_impact_touches_delta) * 0.08, 0.0, 3.0) * absence_confidence
    if features.missing_primary_ballhandler:
        expected_touches += 2.5 * context_confidence

    expected_start_rate = _weighted_average(
        [(weight, _float_or_none(getattr(features, attr))) for weight, attr in _START_RATE_WEIGHTS]
    ) or 0.0
    if features.expected_start is not None:
        start_signal = 1.0 if features.expected_start else 0.0
        expected_start_rate = _weighted_average(
            [
                (1.0 - (0.45 * context_confidence), expected_start_rate),
                (0.45 * context_confidence, start_signal),
            ]
        ) or expected_start_rate

    expected_close_rate = _weighted_average(
        [(weight, _float_or_none(getattr(features, attr))) for weight, attr in _CLOSE_RATE_WEIGHTS]
    ) or 0.0

    minutes_stability = 1.0 - _clamp(_value_or_zero(features.last10_minutes_std) / 8.0, 0.0, 1.0)
    rotation_stability = 1.0 - _clamp(_value_or_zero(features.last10_rotation_minutes_std) / 8.0, 0.0, 1.0)
    usage_alignment = 1.0 - _clamp(
        abs(_value_or_zero(features.last5_usage_pct) - _value_or_zero(features.season_usage_pct)) / 0.12,
        0.0,
        1.0,
    )
    role_stability = _clamp(
        0.30 * minutes_stability
        + 0.20 * rotation_stability
        + 0.22 * usage_alignment
        + 0.16 * _clamp(features.sample_size / 12.0, 0.0, 1.0)
        + 0.12 * (1.0 - _clamp(_value_or_zero(features.late_scratch_risk), 0.0, 1.0)),
        0.0,
        1.0,
    )
    opportunity_score = _clamp(
        0.42 * _clamp(expected_minutes / 36.0, 0.0, 1.2)
        + 0.22 * _clamp(expected_usage_pct / 0.30, 0.0, 1.2)
        + 0.10 * _clamp(expected_touches / 70.0, 0.0, 1.2)
        + 0.14 * role_stability
        + 0.12 * context_confidence,
        0.0,
        1.25,
    )
    opportunity_confidence = _clamp(
        0.30 * role_stability
        + 0.22 * _clamp(features.sample_size / 12.0, 0.0, 1.0)
        + 0.16 * minutes_stability
        + 0.12 * rotation_stability
        + 0.10 * context_confidence
        + 0.10 * availability_modifier,
        0.0,
        1.0,
    )

    opportunity = SignalOpportunityContext(
        expected_minutes=round(expected_minutes, 3),
        season_minutes_avg=round(_value_or_zero(features.season_minutes_avg), 3),
        expected_usage_pct=round(expected_usage_pct, 4),
        expected_start_rate=round(expected_start_rate, 4),
        expected_close_rate=round(expected_close_rate, 4),
        role_stability=round(role_stability, 4),
        opportunity_score=round(opportunity_score, 4),
        opportunity_confidence=round(opportunity_confidence, 4),
        availability_modifier=round(availability_modifier, 4),
        vacated_minutes_bonus=round(vacated_minutes_bonus + role_replacement_minutes_bonus + absence_minutes_bonus, 3),
        vacated_usage_bonus=round(vacated_usage_bonus + role_replacement_usage_bonus + absence_usage_bonus, 4),
        injury_entries=[],
    )
    return opportunity, {
        "expected_minutes": expected_minutes,
        "expected_usage_pct": expected_usage_pct,
        "expected_touches": expected_touches,
        "context_confidence": context_confidence,
        "vacated_minutes_bonus": vacated_minutes_bonus + role_replacement_minutes_bonus + absence_minutes_bonus,
        "vacated_usage_bonus": vacated_usage_bonus + role_replacement_usage_bonus + absence_usage_bonus,
    }


def _derive_key_factor(
    features: PregamePointsFeatures,
    *,
    opportunity_score: float,
    recent_hit_rate: float | None,
    edge_over: float,
) -> str | None:
    if features.official_injury_status:
        label = _title_case_status(features.official_injury_status)
        return f"Player listed as {label} on official injury report" if label else None
    if features.context_source == "pregame_context":
        return "Pregame context is driving tonight's signal"
    if features.context_source == "official_injury_player":
        return "Official injury report adds direct availability context"
    if features.context_source == "official_injury_team":
        return "Teammate absences are creating role pressure"
    if recent_hit_rate is not None and recent_hit_rate >= 0.70:
        return "Recent results have been clearing this line consistently"
    if recent_hit_rate is not None and recent_hit_rate <= 0.30:
        return "Recent results have been staying under this line"
    if features.last5_points_avg is not None and features.season_points_avg is not None:
        delta = float(features.last5_points_avg) - float(features.season_points_avg)
        if abs(delta) >= 3.0:
            direction = "above" if delta > 0 else "below"
            return f"Recent form is {abs(delta):.1f} points {direction} season average"
    if features.back_to_back:
        return "Back-to-back spot adds downside fatigue risk"
    if opportunity_score >= 0.78:
        return "Minutes and usage context are both supportive"
    if edge_over <= -2.0:
        return "Recent production and matchup context lean under"
    return None


def _infer_stat_type_from_feature(features: PregameOpportunityFeatures) -> str:
    if hasattr(features, "season_rebounds_avg"):
        return "rebounds"
    if hasattr(features, "season_assists_avg"):
        return "assists"
    if hasattr(features, "season_threes_avg"):
        return "threes"
    return "points"


def _coerce_injury_entries(injury_entries: list[Any]) -> list[SignalInjuryEntry]:
    normalized: list[SignalInjuryEntry] = []
    for entry in injury_entries:
        if isinstance(entry, SignalInjuryEntry):
            normalized.append(entry)
            continue
        normalized.append(
            SignalInjuryEntry(
                player_name=str(getattr(entry, "player_name", "") or ""),
                team_abbreviation=str(getattr(entry, "team_abbreviation", "") or ""),
                current_status=str(getattr(entry, "current_status", "") or ""),
                reason=str(getattr(entry, "reason", "") or ""),
            )
        )
    return normalized


def _build_opportunity_context(
    features: PregameOpportunityFeatures,
    *,
    injury_entries: list[Any],
    opportunity_projection: object,
) -> SignalOpportunityContext:
    breakdown = opportunity_projection.breakdown
    return SignalOpportunityContext(
        expected_minutes=round(float(breakdown.expected_minutes), 3),
        season_minutes_avg=round(_value_or_zero(features.season_minutes_avg), 3),
        expected_usage_pct=round(float(breakdown.expected_usage_pct), 4),
        expected_start_rate=round(float(breakdown.expected_start_rate), 4),
        expected_close_rate=round(float(breakdown.expected_close_rate), 4),
        role_stability=round(float(breakdown.role_stability), 4),
        opportunity_score=round(float(breakdown.opportunity_score), 4),
        opportunity_confidence=round(float(breakdown.confidence), 4),
        availability_modifier=round(float(breakdown.availability_modifier), 4),
        vacated_minutes_bonus=round(float(breakdown.vacated_minutes_bonus), 3),
        vacated_usage_bonus=round(float(breakdown.vacated_usage_bonus), 4),
        injury_entries=_coerce_injury_entries(injury_entries),
    )


def _build_feature_snapshot(features: PregameOpportunityFeatures, *, stat_type: str) -> SignalFeatureSnapshot:
    return SignalFeatureSnapshot(
        stat_type=stat_type,
        team_abbreviation=features.team_abbreviation or "",
        opponent_abbreviation=features.opponent_abbreviation or "",
        is_home=bool(features.is_home),
        days_rest=features.days_rest,
        back_to_back=bool(features.back_to_back),
        sample_size=int(features.sample_size or 0),
        season_points_avg=_float_or_none(getattr(features, "season_points_avg", None)),
        last10_points_avg=_float_or_none(getattr(features, "last10_points_avg", None)),
        last5_points_avg=_float_or_none(getattr(features, "last5_points_avg", None)),
        season_rebounds_avg=_float_or_none(getattr(features, "season_rebounds_avg", None)),
        last10_rebounds_avg=_float_or_none(getattr(features, "last10_rebounds_avg", None)),
        last5_rebounds_avg=_float_or_none(getattr(features, "last5_rebounds_avg", None)),
        season_assists_avg=_float_or_none(getattr(features, "season_assists_avg", None)),
        last10_assists_avg=_float_or_none(getattr(features, "last10_assists_avg", None)),
        last5_assists_avg=_float_or_none(getattr(features, "last5_assists_avg", None)),
        season_threes_avg=_float_or_none(getattr(features, "season_threes_avg", None)),
        last10_threes_avg=_float_or_none(getattr(features, "last10_threes_avg", None)),
        last5_threes_avg=_float_or_none(getattr(features, "last5_threes_avg", None)),
        season_minutes_avg=_float_or_none(features.season_minutes_avg),
        last10_minutes_avg=_float_or_none(features.last10_minutes_avg),
        last5_minutes_avg=_float_or_none(features.last5_minutes_avg),
        season_usage_pct=_float_or_none(features.season_usage_pct),
        season_reb_pct=_float_or_none(getattr(features, "season_reb_pct", None)),
        season_ast_pct=_float_or_none(getattr(features, "season_ast_pct", None)),
        season_3pa_rate=_float_or_none(getattr(features, "season_3pa_rate", None)),
        opponent_def_rating=_float_or_none(features.opponent_def_rating),
        opponent_pace=_float_or_none(features.opponent_pace),
        team_pace=_float_or_none(features.team_pace),
        context_source=features.context_source,
    )


def _build_breakdown_schema(stat_type: str, breakdown_dict: dict[str, float]) -> SignalBreakdown:
    payload = {
        field.name: float(breakdown_dict.get(field.name, 0.0) or 0.0)
        for field in fields(SignalBreakdown)
    }
    if stat_type == "points":
        payload["projected_points"] = float(
            breakdown_dict.get("projected_points", breakdown_dict.get("projected_value", payload["projected_points"])) or 0.0
        )
    elif stat_type == "rebounds":
        payload["projected_rebounds"] = float(
            breakdown_dict.get("projected_rebounds", breakdown_dict.get("projected_value", payload["projected_rebounds"])) or 0.0
        )
    elif stat_type == "assists":
        payload["projected_assists"] = float(
            breakdown_dict.get("projected_assists", breakdown_dict.get("projected_value", payload["projected_assists"])) or 0.0
        )
    elif stat_type == "threes":
        payload["projected_threes"] = float(
            breakdown_dict.get("projected_threes", breakdown_dict.get("projected_value", payload["projected_threes"])) or 0.0
        )
    return SignalBreakdown(**payload)


def _generic_key_factor(stat_type: str, breakdown_dict: dict[str, float]) -> str | None:
    label_map = {
        "recent_form_adjustment": "Recent form is supportive",
        "minutes_adjustment": "Projected minutes are driving the edge",
        "usage_adjustment": "Usage context is driving the edge",
        "rebound_rate_adjustment": "Rebounding rate trend is driving the edge",
        "playmaking_adjustment": "Playmaking role is driving the edge",
        "volume_adjustment": "Three-point volume trend is driving the edge",
        "opponent_adjustment": "Matchup context is driving the edge",
        "pace_adjustment": "Pace environment is driving the edge",
        "context_adjustment": "Teammate absences are creating role pressure",
    }
    candidate = None
    candidate_value = 0.0
    for key, label in label_map.items():
        value = abs(float(breakdown_dict.get(key, 0.0) or 0.0))
        if value > candidate_value:
            candidate = label
            candidate_value = value
    if candidate_value < 0.15 and stat_type != "points":
        return "Shared opportunity context is doing most of the work"
    return candidate


def build_stats_signal_profile(
    features: PregameOpportunityFeatures,
    *,
    recent_logs: list[HistoricalGameLog],
    injury_entries: list[Any],
    stat_type: str | None = None,
) -> StatsSignalProfile:
    resolved_stat_type = stat_type or _infer_stat_type_from_feature(features)
    opportunity_projection = project_pregame_opportunity(features)
    projection = _STAT_PROJECTORS[resolved_stat_type](features, opportunity_projection=opportunity_projection)
    breakdown_dict = projection.breakdown.to_dict()

    recent_hit_rate, recent_games_count = _recent_hit_rate(recent_logs, float(features.line), stat_type=resolved_stat_type)
    opportunity = _build_opportunity_context(features, injury_entries=injury_entries, opportunity_projection=opportunity_projection)
    feature_snapshot = _build_feature_snapshot(features, stat_type=resolved_stat_type)

    recommended_side = projection.recommended_side
    if features.official_available is False or _value_or_zero(features.late_scratch_risk) >= 0.75:
        recommended_side = None

    if resolved_stat_type == "points" and isinstance(features, PregamePointsFeatures):
        key_factor = _derive_key_factor(
            features,
            opportunity_score=opportunity.opportunity_score,
            recent_hit_rate=recent_hit_rate,
            edge_over=projection.edge_over,
        )
    else:
        key_factor = _generic_key_factor(resolved_stat_type, breakdown_dict)

    return StatsSignalProfile(
        projected_value=round(float(projection.projected_value), 3),
        edge_over=round(float(projection.edge_over), 3),
        edge_under=round(float(projection.edge_under), 3),
        over_probability=round(float(projection.over_probability), 4),
        under_probability=round(float(projection.under_probability), 4),
        confidence=round(float(projection.confidence), 4),
        recommended_side=recommended_side,
        recent_hit_rate=round(recent_hit_rate, 4) if recent_hit_rate is not None else None,
        recent_games_count=recent_games_count,
        key_factor=key_factor,
        breakdown=_build_breakdown_schema(resolved_stat_type, breakdown_dict),
        opportunity=opportunity,
        feature_snapshot=feature_snapshot,
        source_context_captured_at=features.captured_at if features.pregame_context_attached else None,
        source_injury_report_at=features.official_report_datetime_utc,
    )


def _build_fallback_profile(
    snapshot: PlayerPropSnapshot,
    game: Any,
    *,
    recent_logs: list[HistoricalGameLog],
    injury_entries: list[Any],
) -> StatsSignalProfile:
    stat_type = snapshot.stat_type if snapshot.stat_type in SUPPORTED_STAT_TYPES else POINTS_STAT_TYPE
    stat_attr = _STAT_LOG_ATTRS.get(stat_type, "points")
    recent_values = [float(getattr(row, stat_attr) or 0.0) for row in recent_logs[:MAX_RECENT_LOGS]]
    recent_minutes = [float(row.minutes or 0.0) for row in recent_logs[:MAX_RECENT_LOGS] if row.minutes is not None]
    projected_value = sum(recent_values) / len(recent_values) if recent_values else float(snapshot.line)
    recent_hit_rate, recent_games_count = _recent_hit_rate(recent_logs, float(snapshot.line), stat_type=stat_type)
    over_probability, under_probability = _line_probability(projected_value, float(snapshot.line), None)
    edge_over = projected_value - float(snapshot.line)
    sample_strength = _clamp(recent_games_count / 10.0, 0.0, 1.0)
    confidence = _clamp(0.20 + 0.35 * sample_strength + 0.20 * _clamp(abs(edge_over) / 4.0, 0.0, 1.0), 0.0, 0.72)
    recommended_side: Literal["OVER", "UNDER"] | None = None
    if edge_over >= 2.0 and confidence >= 0.55:
        recommended_side = "OVER"
    elif edge_over <= -2.0 and confidence >= 0.55:
        recommended_side = "UNDER"

    average_minutes = round(sum(recent_minutes) / len(recent_minutes), 3) if recent_minutes else 0.0
    opportunity = SignalOpportunityContext(
        expected_minutes=average_minutes,
        season_minutes_avg=average_minutes,
        expected_usage_pct=0.0,
        expected_start_rate=0.0,
        expected_close_rate=0.0,
        role_stability=round(sample_strength, 4),
        opportunity_score=round(sample_strength, 4),
        opportunity_confidence=round(confidence, 4),
        availability_modifier=1.0,
        vacated_minutes_bonus=0.0,
        vacated_usage_bonus=0.0,
        injury_entries=_coerce_injury_entries(injury_entries),
    )
    feature_snapshot = SignalFeatureSnapshot(
        stat_type=stat_type,
        team_abbreviation=snapshot.team or "",
        opponent_abbreviation=snapshot.opponent or "",
        is_home=bool(game and getattr(game, "home_team_abbreviation", None) == snapshot.team),
        days_rest=None,
        back_to_back=False,
        sample_size=recent_games_count,
        season_points_avg=round(projected_value, 3) if stat_type == "points" else None,
        last10_points_avg=round(projected_value, 3) if stat_type == "points" else None,
        last5_points_avg=round(projected_value, 3) if stat_type == "points" else None,
        season_rebounds_avg=round(projected_value, 3) if stat_type == "rebounds" else None,
        last10_rebounds_avg=round(projected_value, 3) if stat_type == "rebounds" else None,
        last5_rebounds_avg=round(projected_value, 3) if stat_type == "rebounds" else None,
        season_assists_avg=round(projected_value, 3) if stat_type == "assists" else None,
        last10_assists_avg=round(projected_value, 3) if stat_type == "assists" else None,
        last5_assists_avg=round(projected_value, 3) if stat_type == "assists" else None,
        season_threes_avg=round(projected_value, 3) if stat_type == "threes" else None,
        last10_threes_avg=round(projected_value, 3) if stat_type == "threes" else None,
        last5_threes_avg=round(projected_value, 3) if stat_type == "threes" else None,
        season_minutes_avg=average_minutes or None,
        last10_minutes_avg=average_minutes or None,
        last5_minutes_avg=average_minutes or None,
        season_usage_pct=None,
        opponent_def_rating=None,
        opponent_pace=None,
        team_pace=None,
        context_source="none",
    )
    breakdown_payload: dict[str, float] = {
        "recent_form_adjustment": 0.0,
        "minutes_adjustment": 0.0,
        "usage_adjustment": 0.0,
        "rebound_rate_adjustment": 0.0,
        "playmaking_adjustment": 0.0,
        "volume_adjustment": 0.0,
        "efficiency_adjustment": 0.0,
        "opponent_adjustment": 0.0,
        "pace_adjustment": 0.0,
        "context_adjustment": 0.0,
        "expected_minutes": opportunity.expected_minutes,
        "expected_usage_pct": 0.0,
    }
    rate_value = round(projected_value / average_minutes, 3) if average_minutes > 0 else 0.0
    if stat_type == "points":
        breakdown_payload.update(base_scoring=round(projected_value, 3), points_per_minute=rate_value, projected_points=round(projected_value, 3))
    elif stat_type == "rebounds":
        breakdown_payload.update(base_rebounding=round(projected_value, 3), rebounds_per_minute=rate_value, projected_rebounds=round(projected_value, 3))
    elif stat_type == "assists":
        breakdown_payload.update(base_playmaking=round(projected_value, 3), assists_per_minute=rate_value, projected_assists=round(projected_value, 3))
    else:
        breakdown_payload.update(base_shooting=round(projected_value, 3), threes_per_minute=rate_value, projected_threes=round(projected_value, 3))
    breakdown = SignalBreakdown(**breakdown_payload)
    return StatsSignalProfile(
        projected_value=round(projected_value, 3),
        edge_over=round(edge_over, 3),
        edge_under=round(-edge_over, 3),
        over_probability=round(over_probability, 4),
        under_probability=round(under_probability, 4),
        confidence=round(confidence, 4),
        recommended_side=recommended_side,
        recent_hit_rate=round(recent_hit_rate, 4) if recent_hit_rate is not None else None,
        recent_games_count=recent_games_count,
        key_factor="Limited historical sample; leaning on recent production" if recent_games_count else "Historical sample is limited",
        breakdown=breakdown,
        opportunity=opportunity,
        feature_snapshot=feature_snapshot,
        source_context_captured_at=None,
        source_injury_report_at=None,
    )


def build_fallback_signal_profile(
    snapshot: PlayerPropSnapshot,
    game: Any,
    *,
    recent_logs: list[HistoricalGameLog],
    injury_entries: list[Any],
) -> StatsSignalProfile:
    return _build_fallback_profile(
        snapshot,
        game,
        recent_logs=recent_logs,
        injury_entries=injury_entries,
    )
