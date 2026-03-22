from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from statistics import NormalDist
from typing import Any

from analytics.features_threes import PregameThreesFeatures, build_pregame_threes_features
from analytics.nba.model_signal_generation import generate_model_signals, persist_generated_model_signals
from analytics.opportunity_model import (
    PregameOpportunityModelConfig,
    PregameOpportunityProjection,
    project_pregame_opportunity,
)

MODEL_NAME = "pregame_threes_baseline"
MODEL_VERSION = "v1"
MIN_EDGE_TO_RECOMMEND = 0.6
MIN_PROBABILITY_TO_RECOMMEND = 0.54
MIN_CONFIDENCE_TO_RECOMMEND = 0.56


@dataclass(frozen=True, slots=True)
class PregameThreesModelConfig:
    threes_per_minute_weights: tuple[tuple[float, str, str], ...] = (
        (0.50, "season_threes_avg", "season_minutes_avg"),
        (0.30, "last10_threes_avg", "last10_minutes_avg"),
        (0.20, "last5_threes_avg", "last5_minutes_avg"),
    )
    tpm_regression_target: float = 0.085
    tpm_regression_factor: float = 0.90
    tpm_floor: float = 0.01
    tpm_ceiling: float = 0.30
    recent_form_last5_factor: float = 0.14
    recent_form_last10_factor: float = 0.07
    recent_form_clamp: float = 1.2
    three_point_rate_factor: float = 4.5
    volume_trend_factor: float = 0.18
    volume_clamp: float = 1.6
    opponent_3pt_defense_factor: float = 6.0
    pace_factor: float = 0.07
    opponent_clamp: float = 0.8
    pace_clamp: float = 0.8
    home_bonus: float = 0.10
    back_to_back_penalty: float = 0.25
    rest_bonus_per_day: float = 0.05
    rest_bonus_max_days: int = 2
    context_clamp: float = 0.7
    opportunity_confidence_weight: float = 0.28
    opportunity_score_weight: float = 0.22
    sample_strength_weight: float = 0.14
    stat_stability_weight: float = 0.12
    form_alignment_weight: float = 0.10
    role_stability_weight: float = 0.08
    minutes_trend_weight: float = 0.06


DEFAULT_CONFIG = PregameThreesModelConfig()


@dataclass(slots=True)
class PregameThreesBreakdown:
    base_shooting: float
    recent_form_adjustment: float
    minutes_adjustment: float
    volume_adjustment: float
    opponent_adjustment: float
    pace_adjustment: float
    context_adjustment: float
    expected_minutes: float
    expected_usage_pct: float
    threes_per_minute: float
    opportunity_score: float
    opportunity_confidence: float
    projected_threes: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(slots=True)
class PregameThreesProjection:
    features: PregameThreesFeatures
    breakdown: PregameThreesBreakdown
    projected_value: float
    distribution_std: float
    over_probability: float
    under_probability: float
    edge_over: float
    edge_under: float
    confidence: float
    recommended_side: str | None

    def to_signal(self) -> dict[str, Any]:
        return {
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "market_phase": "pregame",
            "sportsbook": "fanduel",
            "game_id": self.features.game_id,
            "player_id": self.features.player_id,
            "player_name": self.features.player_name,
            "stat_type": "threes",
            "line": self.features.line,
            "projected_value": self.projected_value,
            "over_probability": self.over_probability,
            "under_probability": self.under_probability,
            "edge_over": self.edge_over,
            "edge_under": self.edge_under,
            "confidence": self.confidence,
            "recommended_side": self.recommended_side,
            "metadata_json": json.dumps({"breakdown": self.breakdown.to_dict()}, sort_keys=True),
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
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _safe_rate(total: float | None, minutes: float | None) -> float | None:
    if total is None or minutes is None or minutes <= 0:
        return None
    return total / minutes


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def project_pregame_threes(
    features: PregameThreesFeatures,
    config: PregameThreesModelConfig = DEFAULT_CONFIG,
    *,
    opportunity_config: PregameOpportunityModelConfig | None = None,
    opportunity_projection: PregameOpportunityProjection | None = None,
) -> PregameThreesProjection:
    if opportunity_projection is None:
        opportunity_projection = project_pregame_opportunity(
            features,
            config=opportunity_config or PregameOpportunityModelConfig(),
        ) if opportunity_config is not None else project_pregame_opportunity(features)
    opportunity = opportunity_projection.breakdown

    threes_per_minute = _weighted_average(
        [
            (weight, _safe_rate(getattr(features, threes_attr), getattr(features, minutes_attr)))
            for weight, threes_attr, minutes_attr in config.threes_per_minute_weights
        ]
    )
    threes_per_minute = _clamp(
        config.tpm_regression_target + config.tpm_regression_factor * (threes_per_minute - config.tpm_regression_target),
        config.tpm_floor,
        config.tpm_ceiling,
    )

    expected_minutes = opportunity.expected_minutes
    expected_usage_pct = opportunity.expected_usage_pct
    base_shooting = max(0.0, expected_minutes * threes_per_minute)

    minutes_adjustment = 0.0
    if features.season_minutes_avg is not None:
        minutes_adjustment = (expected_minutes - features.season_minutes_avg) * threes_per_minute * 0.25

    recent_form_adjustment = 0.0
    if features.last5_threes_avg is not None and features.season_threes_avg is not None:
        recent_form_adjustment += (features.last5_threes_avg - features.season_threes_avg) * config.recent_form_last5_factor
    if features.last10_threes_avg is not None and features.season_threes_avg is not None:
        recent_form_adjustment += (features.last10_threes_avg - features.season_threes_avg) * config.recent_form_last10_factor
    recent_form_adjustment = _clamp(recent_form_adjustment, -config.recent_form_clamp, config.recent_form_clamp)

    volume_adjustment = 0.0
    if features.last10_3pa_avg is not None and features.season_3pa_avg is not None:
        volume_adjustment += (features.last10_3pa_avg - features.season_3pa_avg) * config.volume_trend_factor
    if features.last10_3pa_rate is not None and features.season_3pa_rate is not None:
        volume_adjustment += (features.last10_3pa_rate - features.season_3pa_rate) * config.three_point_rate_factor
    volume_adjustment = _clamp(volume_adjustment, -config.volume_clamp, config.volume_clamp)

    opponent_adjustment = 0.0
    if features.opponent_3pt_pct_allowed is not None:
        opponent_adjustment = (float(features.opponent_3pt_pct_allowed) - 0.35) * config.opponent_3pt_defense_factor
    opponent_adjustment = _clamp(opponent_adjustment, -config.opponent_clamp, config.opponent_clamp)

    expected_game_pace = _weighted_average([(0.50, features.team_pace), (0.50, features.opponent_pace)])
    pace_adjustment = 0.0
    if expected_game_pace and features.league_avg_pace is not None:
        pace_adjustment = (expected_game_pace - features.league_avg_pace) * config.pace_factor
    pace_adjustment = _clamp(pace_adjustment, -config.pace_clamp, config.pace_clamp)

    context_adjustment = 0.0
    if features.is_home:
        context_adjustment += config.home_bonus
    if features.back_to_back:
        context_adjustment -= config.back_to_back_penalty
    if features.days_rest is not None and features.days_rest >= 2:
        context_adjustment += min(features.days_rest - 1, config.rest_bonus_max_days) * config.rest_bonus_per_day
    context_adjustment = _clamp(context_adjustment, -config.context_clamp, config.context_clamp)

    projected_threes = max(
        0.0,
        base_shooting
        + recent_form_adjustment
        + minutes_adjustment
        + volume_adjustment
        + opponent_adjustment
        + pace_adjustment
        + context_adjustment,
    )

    distribution_std = max(1.2, _value_or_zero(features.last10_threes_std), projected_threes * 0.28)
    if features.line > 0:
        distribution = NormalDist(mu=projected_threes, sigma=distribution_std)
        over_probability = 1.0 - distribution.cdf(features.line)
        under_probability = 1.0 - over_probability
        edge_over = projected_threes - features.line
        edge_under = -edge_over
    else:
        over_probability = 0.5
        under_probability = 0.5
        edge_over = 0.0
        edge_under = 0.0

    sample_strength = _clamp(features.sample_size / 10.0, 0.0, 1.0)
    stat_stability = 1.0 - _clamp(_value_or_zero(features.last10_threes_std) / 3.0, 0.0, 1.0)
    form_alignment = 1.0 - _clamp(abs(_value_or_zero(features.last5_threes_avg) - _value_or_zero(features.season_threes_avg)) / 4.0, 0.0, 1.0)
    minutes_trend_stability = 1.0 - _clamp(abs(_value_or_zero(features.last5_minutes_avg) - _value_or_zero(features.last10_minutes_avg)) / 6.0, 0.0, 1.0)

    confidence = _clamp(
        config.opportunity_confidence_weight * opportunity.confidence
        + config.opportunity_score_weight * opportunity.opportunity_score
        + config.sample_strength_weight * sample_strength
        + config.stat_stability_weight * stat_stability
        + config.form_alignment_weight * form_alignment
        + config.role_stability_weight * opportunity.role_stability
        + config.minutes_trend_weight * minutes_trend_stability,
        0.0,
        1.0,
    )

    recommended_side = None
    if features.line > 0:
        if edge_over >= MIN_EDGE_TO_RECOMMEND and over_probability >= MIN_PROBABILITY_TO_RECOMMEND and confidence >= MIN_CONFIDENCE_TO_RECOMMEND:
            recommended_side = "OVER"
        elif edge_under >= MIN_EDGE_TO_RECOMMEND and under_probability >= MIN_PROBABILITY_TO_RECOMMEND and confidence >= MIN_CONFIDENCE_TO_RECOMMEND:
            recommended_side = "UNDER"

    breakdown = PregameThreesBreakdown(
        base_shooting=round(base_shooting, 3),
        recent_form_adjustment=round(recent_form_adjustment, 3),
        minutes_adjustment=round(minutes_adjustment, 3),
        volume_adjustment=round(volume_adjustment, 3),
        opponent_adjustment=round(opponent_adjustment, 3),
        pace_adjustment=round(pace_adjustment, 3),
        context_adjustment=round(context_adjustment, 3),
        expected_minutes=round(expected_minutes, 3),
        expected_usage_pct=round(expected_usage_pct, 4),
        threes_per_minute=round(threes_per_minute, 3),
        opportunity_score=round(opportunity.opportunity_score, 4),
        opportunity_confidence=round(opportunity.confidence, 4),
        projected_threes=round(projected_threes, 3),
    )
    return PregameThreesProjection(
        features=features,
        breakdown=breakdown,
        projected_value=round(projected_threes, 3),
        distribution_std=round(distribution_std, 3),
        over_probability=round(over_probability, 4),
        under_probability=round(under_probability, 4),
        edge_over=round(edge_over, 3),
        edge_under=round(edge_under, 3),
        confidence=round(confidence, 4),
        recommended_side=recommended_side,
    )


def generate_pregame_threes_signals(captured_at: datetime | None = None, limit: int | None = None, persist: bool = False) -> list[dict[str, Any]]:
    signals = generate_model_signals(
        build_features=build_pregame_threes_features,
        project=project_pregame_threes,
        captured_at=captured_at,
        limit=limit,
    )
    if persist:
        persist_generated_model_signals(signals)
    return signals
