from __future__ import annotations

from datetime import datetime
from statistics import NormalDist
from typing import Any

from analytics.features_opportunity import PregameOpportunityFeatures
from database.models import Game, HistoricalGameLog

POINTS_STAT_TYPE = "points"
SUPPORTED_STAT_TYPES = ("points", "rebounds", "assists", "threes")
MAX_RECENT_LOGS = 10
MIN_RECENT_GAMES_FOR_RECOMMENDATION = 5
MAX_SIGNAL_CAPTURE_AGE_MINUTES = 90
INJURY_REPORT_REQUIRED_WINDOW_MINUTES = 240
LOW_CONTEXT_CONFIDENCE_THRESHOLD = 0.45
LOW_OPPORTUNITY_CONFIDENCE_THRESHOLD = 0.35
STALE_ODDS_ARCHIVE_WARNING_MINUTES = 120
MIN_NON_ZERO_STAT_GAMES = 5

_STAT_LOG_ATTRS = {
    "points": "points",
    "rebounds": "rebounds",
    "assists": "assists",
    "threes": "threes_made",
}

_STAT_REQUIRED_FEATURE_FIELDS: dict[str, tuple[tuple[str, str], ...]] = {
    "points": (
        ("season_points_avg", "season scoring average"),
        ("last10_points_avg", "last-10 scoring average"),
    ),
    "rebounds": (
        ("season_rebounds_avg", "season rebounds average"),
        ("season_reb_pct", "season rebound rate"),
    ),
    "assists": (
        ("season_assists_avg", "season assists average"),
        ("season_ast_pct", "season assist rate"),
    ),
    "threes": (
        ("season_threes_avg", "season threes average"),
        ("season_3pa_rate", "season three-point attempt rate"),
    ),
}


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def float_or_none(value: Any) -> float | None:
    return float(value) if value is not None else None


def value_or_zero(value: Any) -> float:
    return float(value) if value is not None else 0.0


def weighted_average(weighted_values: list[tuple[float, float | None]]) -> float:
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


def title_case_status(status: str | None) -> str | None:
    if not status:
        return None
    return status.replace("_", " ").strip().title()


def recent_hit_rate(
    recent_logs: list[HistoricalGameLog],
    line: float,
    *,
    stat_type: str,
) -> tuple[float | None, int]:
    stat_attr = _STAT_LOG_ATTRS.get(stat_type, "points")
    values = [float(getattr(row, stat_attr) or 0.0) for row in recent_logs[:MAX_RECENT_LOGS]]
    if not values:
        return None, 0
    return sum(1 for value in values if value > line) / len(values), len(values)


def line_probability(projected_value: float, line: float, distribution_std: float | None) -> tuple[float, float]:
    std = max(float(distribution_std or 0.0), 1.2)
    distribution = NormalDist(mu=projected_value, sigma=std)
    over_probability = 1.0 - distribution.cdf(line)
    over_probability = clamp(over_probability, 0.0, 1.0)
    return over_probability, 1.0 - over_probability


def age_minutes(later: datetime, earlier: datetime | None) -> int | None:
    if earlier is None:
        return None
    delta_seconds = (later - earlier).total_seconds()
    return max(int(delta_seconds // 60), 0)


def minutes_to_tip(game: Game | None, *, evaluation_time: datetime) -> int | None:
    if game is None or game.game_time_utc is None:
        return None
    return int((game.game_time_utc - evaluation_time).total_seconds() // 60)


def count_non_zero_recent_games(recent_logs: list[HistoricalGameLog], *, stat_type: str) -> int:
    stat_attr = _STAT_LOG_ATTRS.get(stat_type)
    if stat_attr is None:
        return 0
    return sum(
        1
        for row in recent_logs[:MAX_RECENT_LOGS]
        if value_or_zero(getattr(row, stat_attr, None)) > 0.0
    )


def missing_stat_feature_labels(
    feature: PregameOpportunityFeatures,
    *,
    stat_type: str,
) -> list[str]:
    missing_labels: list[str] = []
    for attr, label in _STAT_REQUIRED_FEATURE_FIELDS.get(stat_type, ()):
        if getattr(feature, attr, None) is None:
            missing_labels.append(label)
    return missing_labels


def infer_stat_type_from_feature(features: PregameOpportunityFeatures) -> str:
    if hasattr(features, "season_rebounds_avg"):
        return "rebounds"
    if hasattr(features, "season_assists_avg"):
        return "assists"
    if hasattr(features, "season_threes_avg"):
        return "threes"
    return POINTS_STAT_TYPE
