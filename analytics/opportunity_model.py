from __future__ import annotations

from dataclasses import asdict, dataclass

from analytics.features_opportunity import PregameOpportunityFeatures, _weighted_average


@dataclass(frozen=True, slots=True)
class PregameOpportunityModelConfig:
    expected_minutes_weights: tuple[tuple[float, str], ...] = ((0.50, "season_minutes_avg"), (0.30, "last10_minutes_avg"), (0.20, "last5_minutes_avg"))
    expected_usage_weights: tuple[tuple[float, str], ...] = ((0.45, "season_usage_pct"), (0.35, "last10_usage_pct"), (0.20, "last5_usage_pct"))
    expected_est_usage_weights: tuple[tuple[float, str], ...] = ((0.45, "season_est_usage_pct"), (0.35, "last10_est_usage_pct"), (0.20, "last5_est_usage_pct"))
    touches_weights: tuple[tuple[float, str], ...] = ((0.45, "season_touches"), (0.35, "last10_touches"), (0.20, "last5_touches"))
    passes_weights: tuple[tuple[float, str], ...] = ((0.45, "season_passes"), (0.35, "last10_passes"), (0.20, "last5_passes"))
    expected_minutes_scale: float = 36.0
    touches_scale: float = 75.0
    passes_scale: float = 60.0


DEFAULT_OPPORTUNITY_CONFIG = PregameOpportunityModelConfig()


@dataclass(slots=True)
class PregameOpportunityBreakdown:
    expected_minutes: float
    expected_usage_pct: float
    expected_est_usage_pct: float
    expected_touches: float
    expected_passes: float
    role_stability: float
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


def _value_or_zero(value: float | None) -> float:
    return float(value) if value is not None else 0.0


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def project_pregame_opportunity(features: PregameOpportunityFeatures, config: PregameOpportunityModelConfig = DEFAULT_OPPORTUNITY_CONFIG) -> PregameOpportunityProjection:
    expected_minutes = _weighted_average([(weight, getattr(features, attr)) for weight, attr in config.expected_minutes_weights]) or 0.0
    expected_usage_pct = _weighted_average([(weight, getattr(features, attr)) for weight, attr in config.expected_usage_weights]) or 0.0
    expected_est_usage_pct = _weighted_average([(weight, getattr(features, attr)) for weight, attr in config.expected_est_usage_weights]) or 0.0
    expected_touches = _weighted_average([(weight, getattr(features, attr)) for weight, attr in config.touches_weights]) or 0.0
    expected_passes = _weighted_average([(weight, getattr(features, attr)) for weight, attr in config.passes_weights]) or 0.0

    minutes_stability = 1.0 - _clamp(_value_or_zero(features.last10_minutes_std) / 8.0, 0.0, 1.0)
    usage_alignment = 1.0 - _clamp(abs(_value_or_zero(features.last5_usage_pct) - _value_or_zero(features.season_usage_pct)) / 0.12, 0.0, 1.0)
    role_stability = _clamp(0.60 * minutes_stability + 0.40 * usage_alignment, 0.0, 1.0)

    minutes_score = _clamp(expected_minutes / config.expected_minutes_scale, 0.0, 1.2)
    usage_score = _clamp(((expected_usage_pct + expected_est_usage_pct) / 2.0) / 0.30, 0.0, 1.2)
    touches_score = _clamp(expected_touches / config.touches_scale, 0.0, 1.2)
    passes_score = _clamp(expected_passes / config.passes_scale, 0.0, 1.2)
    offensive_role_score = _clamp(0.40 * minutes_score + 0.30 * usage_score + 0.20 * touches_score + 0.10 * passes_score, 0.0, 1.25)

    matchup_environment_score = 0.5
    if features.team_pace is not None and features.opponent_pace is not None and features.league_avg_pace is not None:
        matchup_environment_score = _clamp((((features.team_pace + features.opponent_pace) / 2.0) - features.league_avg_pace) / 6.0 + 0.5, 0.0, 1.0)

    opportunity_score = _clamp(0.55 * offensive_role_score + 0.30 * role_stability + 0.15 * matchup_environment_score, 0.0, 1.25)
    confidence = _clamp(0.35 * role_stability + 0.30 * minutes_stability + 0.20 * _clamp(features.sample_size / 10.0, 0.0, 1.0) + 0.15 * matchup_environment_score, 0.0, 1.0)

    return PregameOpportunityProjection(
        features=features,
        breakdown=PregameOpportunityBreakdown(
            expected_minutes=round(expected_minutes, 3),
            expected_usage_pct=round(expected_usage_pct, 4),
            expected_est_usage_pct=round(expected_est_usage_pct, 4),
            expected_touches=round(expected_touches, 3),
            expected_passes=round(expected_passes, 3),
            role_stability=round(role_stability, 4),
            offensive_role_score=round(offensive_role_score, 4),
            matchup_environment_score=round(matchup_environment_score, 4),
            opportunity_score=round(opportunity_score, 4),
            confidence=round(confidence, 4),
        ),
    )
