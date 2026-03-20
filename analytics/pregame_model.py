from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from statistics import NormalDist
from typing import Any

from analytics.features_pregame import PregamePointsFeatures, build_pregame_points_features
from analytics.opportunity_model import (
    PregameOpportunityModelConfig,
    PregameOpportunityProjection,
    project_pregame_opportunity,
)
from ingestion.writer import write_model_signals

MODEL_NAME = "pregame_points_baseline"
MODEL_VERSION = "v3"
MIN_EDGE_TO_RECOMMEND = 1.5
MIN_PROBABILITY_TO_RECOMMEND = 0.54
MIN_CONFIDENCE_TO_RECOMMEND = 0.65


@dataclass(frozen=True, slots=True)
class PregamePointsModelConfig:
    points_per_minute_weights: tuple[tuple[float, str, str], ...] = (
        (0.50, "season_points_avg", "season_minutes_avg"),
        (0.30, "last10_points_avg", "last10_minutes_avg"),
        (0.20, "last5_points_avg", "last5_minutes_avg"),
    )
    ppm_regression_target: float = 0.42
    ppm_regression_factor: float = 0.80
    ppm_floor: float = 0.35
    ppm_ceiling: float = 1.15
    recent_form_last5_factor: float = 0.18
    recent_form_last10_factor: float = 0.08
    recent_form_clamp: float = 2.5
    usage_delta_factor: float = 8.5
    estimated_usage_delta_factor: float = 5.5
    fga_delta_factor: float = 0.20
    fta_delta_factor: float = 0.16
    touches_delta_factor: float = 0.010
    usage_clamp: float = 2.4
    ts_delta_factor: float = 6.0
    fg_delta_factor: float = 2.4
    efficiency_clamp: float = 1.6
    opponent_def_rating_factor: float = 0.18
    opponent_clamp: float = 1.1
    pace_factor: float = 0.16
    pace_clamp: float = 1.6
    home_bonus: float = 0.0
    back_to_back_penalty: float = 0.65
    rest_bonus_per_day: float = 0.12
    rest_bonus_max_days: int = 2
    context_clamp: float = 1.2
    opportunity_confidence_weight: float = 0.26
    opportunity_score_weight: float = 0.26
    sample_strength_weight: float = 0.12
    points_stability_weight: float = 0.12
    form_alignment_weight: float = 0.08
    role_stability_weight: float = 0.10
    minutes_trend_weight: float = 0.06


DEFAULT_CONFIG = PregamePointsModelConfig()


@dataclass(slots=True)
class PregamePointsBreakdown:
    base_scoring: float
    recent_form_adjustment: float
    minutes_adjustment: float
    usage_adjustment: float
    efficiency_adjustment: float
    opponent_adjustment: float
    pace_adjustment: float
    context_adjustment: float
    expected_minutes: float
    expected_usage_pct: float
    expected_est_usage_pct: float
    expected_touches: float
    points_per_minute: float
    opportunity_score: float
    opportunity_confidence: float
    role_stability: float
    projected_points: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(slots=True)
class PregamePointsProjection:
    features: PregamePointsFeatures
    breakdown: PregamePointsBreakdown
    projected_value: float
    distribution_std: float
    over_probability: float
    under_probability: float
    edge_over: float
    edge_under: float
    confidence: float
    recommended_side: str | None

    def to_signal(self) -> dict[str, Any]:
        metadata = {
            "breakdown": self.breakdown.to_dict(),
            "features": {
                "team_abbreviation": self.features.team_abbreviation,
                "opponent_abbreviation": self.features.opponent_abbreviation,
                "is_home": self.features.is_home,
                "days_rest": self.features.days_rest,
                "sample_size": self.features.sample_size,
                "last5_count": self.features.last5_count,
                "last10_count": self.features.last10_count,
                "season_points_avg": self.features.season_points_avg,
                "last10_points_avg": self.features.last10_points_avg,
                "last5_points_avg": self.features.last5_points_avg,
                "season_minutes_avg": self.features.season_minutes_avg,
                "last10_minutes_avg": self.features.last10_minutes_avg,
                "last5_minutes_avg": self.features.last5_minutes_avg,
                "season_usage_pct": self.features.season_usage_pct,
                "last10_usage_pct": self.features.last10_usage_pct,
                "opponent_def_rating": self.features.opponent_def_rating,
                "opponent_pace": self.features.opponent_pace,
                "team_pace": self.features.team_pace,
                "pregame_context_attached": self.features.pregame_context_attached,
                "official_injury_attached": self.features.official_injury_attached,
                "context_source": self.features.context_source,
                "pregame_context_confidence": self.features.pregame_context_confidence,
                "official_injury_status": self.features.official_injury_status,
            },
        }
        return {
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "market_phase": "pregame",
            "sportsbook": "fanduel",
            "game_id": self.features.game_id,
            "player_id": self.features.player_id,
            "player_name": self.features.player_name,
            "stat_type": "points",
            "line": self.features.line,
            "projected_value": self.projected_value,
            "over_probability": self.over_probability,
            "under_probability": self.under_probability,
            "edge_over": self.edge_over,
            "edge_under": self.edge_under,
            "confidence": self.confidence,
            "recommended_side": self.recommended_side,
            "metadata_json": json.dumps(metadata, sort_keys=True),
            "created_at": datetime.utcnow(),
        }



def _value_or_zero(value: float | None) -> float:
    return float(value) if value is not None else 0.0



def _weighted_average(weighted_values: list[tuple[float, float | None]]) -> float:
    numerator = 0.0
    denominator = 0.0
    for weight, value in weighted_values:
        if value is None:
            continue
        numerator += weight * float(value)
        denominator += weight
    if denominator == 0:
        return 0.0
    return numerator / denominator



def _safe_points_per_minute(points: float | None, minutes: float | None) -> float | None:
    if points is None or minutes is None or minutes <= 0:
        return None
    return points / minutes



def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))



def project_pregame_points(
    features: PregamePointsFeatures,
    config: PregamePointsModelConfig = DEFAULT_CONFIG,
    *,
    opportunity_config: PregameOpportunityModelConfig | None = None,
    opportunity_projection: PregameOpportunityProjection | None = None,
) -> PregamePointsProjection:
    if opportunity_projection is None:
        opportunity_projection = project_pregame_opportunity(
            features,
            config=opportunity_config or PregameOpportunityModelConfig(),
        ) if opportunity_config is not None else project_pregame_opportunity(features)
    opportunity = opportunity_projection.breakdown

    expected_minutes = opportunity.expected_minutes
    expected_usage_pct = opportunity.expected_usage_pct
    expected_est_usage_pct = opportunity.expected_est_usage_pct
    expected_touches = opportunity.expected_touches

    points_per_minute = _weighted_average(
        [
            (weight, _safe_points_per_minute(getattr(features, points_attr), getattr(features, minutes_attr)))
            for weight, points_attr, minutes_attr in config.points_per_minute_weights
        ]
    )
    if points_per_minute <= 0:
        season_points = features.season_points_avg if features.season_points_avg is not None else features.last10_points_avg
        points_per_minute = _safe_points_per_minute(season_points, features.season_minutes_avg or features.last10_minutes_avg) or 0.0
    points_per_minute = _clamp(
        config.ppm_regression_target + config.ppm_regression_factor * (points_per_minute - config.ppm_regression_target),
        config.ppm_floor,
        config.ppm_ceiling,
    )

    base_scoring = max(0.0, expected_minutes * points_per_minute)
    minutes_adjustment = 0.0
    if features.season_minutes_avg is not None:
        minutes_adjustment = (expected_minutes - features.season_minutes_avg) * points_per_minute * 0.25

    recent_form_adjustment = 0.0
    if features.last5_points_avg is not None and features.season_points_avg is not None:
        recent_form_adjustment += (features.last5_points_avg - features.season_points_avg) * config.recent_form_last5_factor
    if features.last10_points_avg is not None and features.season_points_avg is not None:
        recent_form_adjustment += (features.last10_points_avg - features.season_points_avg) * config.recent_form_last10_factor
    recent_form_adjustment = _clamp(recent_form_adjustment, -config.recent_form_clamp, config.recent_form_clamp)

    usage_adjustment = 0.0
    if features.season_usage_pct is not None:
        usage_adjustment += (expected_usage_pct - features.season_usage_pct) * config.usage_delta_factor
    if features.season_est_usage_pct is not None:
        usage_adjustment += (expected_est_usage_pct - features.season_est_usage_pct) * config.estimated_usage_delta_factor
    if features.last10_fga_avg is not None and features.season_fga_avg is not None:
        usage_adjustment += (features.last10_fga_avg - features.season_fga_avg) * config.fga_delta_factor
    if features.last10_fta_avg is not None and features.season_fta_avg is not None:
        usage_adjustment += (features.last10_fta_avg - features.season_fta_avg) * config.fta_delta_factor
    if features.season_touches is not None:
        usage_adjustment += (expected_touches - features.season_touches) * config.touches_delta_factor
    usage_adjustment = _clamp(usage_adjustment, -config.usage_clamp, config.usage_clamp)

    efficiency_adjustment = 0.0
    if features.last10_ts_pct is not None and features.season_ts_pct is not None:
        efficiency_adjustment += (features.last10_ts_pct - features.season_ts_pct) * config.ts_delta_factor
    if features.last10_fg_pct is not None and features.season_fg_pct is not None:
        efficiency_adjustment += (features.last10_fg_pct - features.season_fg_pct) * config.fg_delta_factor
    efficiency_adjustment = _clamp(efficiency_adjustment, -config.efficiency_clamp, config.efficiency_clamp)

    opponent_adjustment = 0.0
    if features.opponent_def_rating is not None and features.league_avg_def_rating is not None:
        opponent_adjustment += (features.league_avg_def_rating - features.opponent_def_rating) * config.opponent_def_rating_factor
    opponent_adjustment = _clamp(opponent_adjustment, -config.opponent_clamp, config.opponent_clamp)

    expected_game_pace = _weighted_average([
        (0.50, features.team_pace),
        (0.50, features.opponent_pace),
    ])
    pace_adjustment = 0.0
    if expected_game_pace and features.league_avg_pace is not None:
        pace_adjustment = (expected_game_pace - features.league_avg_pace) * config.pace_factor
    pace_adjustment = _clamp(pace_adjustment, -config.pace_clamp, config.pace_clamp)

    context_adjustment = 0.0
    if features.is_home is True:
        context_adjustment += config.home_bonus
    if features.back_to_back:
        context_adjustment -= config.back_to_back_penalty
    if features.days_rest is not None and features.days_rest >= 2:
        context_adjustment += min(features.days_rest - 1, config.rest_bonus_max_days) * config.rest_bonus_per_day
    context_adjustment = _clamp(context_adjustment, -config.context_clamp, config.context_clamp)

    projected_points = max(
        0.0,
        base_scoring
        + minutes_adjustment
        + recent_form_adjustment
        + usage_adjustment
        + efficiency_adjustment
        + opponent_adjustment
        + pace_adjustment
        + context_adjustment,
    )

    distribution_std = max(
        4.0,
        _value_or_zero(features.last10_points_std),
        projected_points * 0.18,
    )

    if features.line > 0:
        distribution = NormalDist(mu=projected_points, sigma=distribution_std)
        over_probability = 1.0 - distribution.cdf(features.line)
        under_probability = 1.0 - over_probability
        edge_over = projected_points - features.line
        edge_under = -edge_over
    else:
        over_probability = 0.5
        under_probability = 0.5
        edge_over = 0.0
        edge_under = 0.0

    sample_strength = _clamp(features.sample_size / 10.0, 0.0, 1.0)
    points_stability = 1.0 - _clamp(_value_or_zero(features.last10_points_std) / 12.0, 0.0, 1.0)
    recent_reference = features.last5_points_avg if features.last5_points_avg is not None else projected_points
    season_reference = features.season_points_avg if features.season_points_avg is not None else projected_points
    denominator = max(abs(season_reference), 8.0)
    form_alignment = 1.0 - _clamp(abs(recent_reference - season_reference) / denominator, 0.0, 1.0)
    minutes_trend_volatility = 1.0 - _clamp(abs(_value_or_zero(features.last5_minutes_avg) - _value_or_zero(features.last10_minutes_avg)) / 6.0, 0.0, 1.0)

    confidence = _clamp(
        config.opportunity_confidence_weight * opportunity.confidence
        + config.opportunity_score_weight * opportunity.opportunity_score
        + config.sample_strength_weight * sample_strength
        + config.points_stability_weight * points_stability
        + config.form_alignment_weight * form_alignment
        + config.role_stability_weight * opportunity.role_stability
        + config.minutes_trend_weight * minutes_trend_volatility,
        0.0,
        1.0,
    )

    recommended_side = None
    if features.line > 0:
        if edge_over >= MIN_EDGE_TO_RECOMMEND and over_probability >= MIN_PROBABILITY_TO_RECOMMEND and confidence >= MIN_CONFIDENCE_TO_RECOMMEND:
            recommended_side = "OVER"
        elif edge_under >= MIN_EDGE_TO_RECOMMEND and under_probability >= MIN_PROBABILITY_TO_RECOMMEND and confidence >= MIN_CONFIDENCE_TO_RECOMMEND:
            recommended_side = "UNDER"

    breakdown = PregamePointsBreakdown(
        base_scoring=round(base_scoring, 3),
        recent_form_adjustment=round(recent_form_adjustment, 3),
        minutes_adjustment=round(minutes_adjustment, 3),
        usage_adjustment=round(usage_adjustment, 3),
        efficiency_adjustment=round(efficiency_adjustment, 3),
        opponent_adjustment=round(opponent_adjustment, 3),
        pace_adjustment=round(pace_adjustment, 3),
        context_adjustment=round(context_adjustment, 3),
        expected_minutes=round(expected_minutes, 3),
        expected_usage_pct=round(expected_usage_pct, 4),
        expected_est_usage_pct=round(expected_est_usage_pct, 4),
        expected_touches=round(expected_touches, 3),
        points_per_minute=round(points_per_minute, 3),
        opportunity_score=round(opportunity.opportunity_score, 4),
        opportunity_confidence=round(opportunity.confidence, 4),
        role_stability=round(opportunity.role_stability, 4),
        projected_points=round(projected_points, 3),
    )

    return PregamePointsProjection(
        features=features,
        breakdown=breakdown,
        projected_value=round(projected_points, 3),
        distribution_std=round(distribution_std, 3),
        over_probability=round(over_probability, 4),
        under_probability=round(under_probability, 4),
        edge_over=round(edge_over, 3),
        edge_under=round(edge_under, 3),
        confidence=round(confidence, 4),
        recommended_side=recommended_side,
    )



def generate_pregame_points_signals(
    captured_at: datetime | None = None,
    limit: int | None = None,
    persist: bool = False,
) -> list[dict[str, Any]]:
    features = build_pregame_points_features(captured_at=captured_at, limit=limit)
    projections = [project_pregame_points(feature) for feature in features]
    signals = [projection.to_signal() for projection in projections]
    if persist and signals:
        write_model_signals(signals)
    return signals
