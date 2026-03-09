from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from analytics.features_opportunity import PregameOpportunityFeatures, _mean, _median, _safe_pct, _std, _values, load_pregame_feature_seeds
from database.models import HistoricalAdvancedLog, HistoricalGameLog


@dataclass(slots=True)
class PregamePointsFeatures(PregameOpportunityFeatures):
    line: float = 0.0
    over_odds: int = 0
    under_odds: int = 0
    season_points_avg: float | None = None
    last10_points_avg: float | None = None
    last5_points_avg: float | None = None
    last10_points_median: float | None = None
    last10_points_std: float | None = None
    season_fga_avg: float | None = None
    last10_fga_avg: float | None = None
    last5_fga_avg: float | None = None
    season_3pa_avg: float | None = None
    last10_3pa_avg: float | None = None
    last5_3pa_avg: float | None = None
    season_fta_avg: float | None = None
    last10_fta_avg: float | None = None
    last5_fta_avg: float | None = None
    season_fg_pct: float | None = None
    last10_fg_pct: float | None = None
    last5_fg_pct: float | None = None
    season_3pt_pct: float | None = None
    last10_3pt_pct: float | None = None
    last5_3pt_pct: float | None = None
    season_ft_pct: float | None = None
    last10_ft_pct: float | None = None
    last5_ft_pct: float | None = None
    season_ts_pct: float | None = None
    last10_ts_pct: float | None = None
    last5_ts_pct: float | None = None
    season_efg_pct: float | None = None
    last10_efg_pct: float | None = None
    last5_efg_pct: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _build_points_log_aggregates(logs: list[HistoricalGameLog]) -> dict[str, float | None]:
    last10 = logs[:10]
    last5 = logs[:5]
    return {
        "season_points_avg": _mean(_values(logs, "points")),
        "last10_points_avg": _mean(_values(last10, "points")),
        "last5_points_avg": _mean(_values(last5, "points")),
        "last10_points_median": _median(_values(last10, "points")),
        "last10_points_std": _std(_values(last10, "points")),
        "season_fga_avg": _mean(_values(logs, "field_goals_attempted")),
        "last10_fga_avg": _mean(_values(last10, "field_goals_attempted")),
        "last5_fga_avg": _mean(_values(last5, "field_goals_attempted")),
        "season_3pa_avg": _mean(_values(logs, "threes_attempted")),
        "last10_3pa_avg": _mean(_values(last10, "threes_attempted")),
        "last5_3pa_avg": _mean(_values(last5, "threes_attempted")),
        "season_fta_avg": _mean(_values(logs, "free_throws_attempted")),
        "last10_fta_avg": _mean(_values(last10, "free_throws_attempted")),
        "last5_fta_avg": _mean(_values(last5, "free_throws_attempted")),
        "season_fg_pct": _safe_pct(_values(logs, "field_goals_made"), _values(logs, "field_goals_attempted")),
        "last10_fg_pct": _safe_pct(_values(last10, "field_goals_made"), _values(last10, "field_goals_attempted")),
        "last5_fg_pct": _safe_pct(_values(last5, "field_goals_made"), _values(last5, "field_goals_attempted")),
        "season_3pt_pct": _safe_pct(_values(logs, "threes_made"), _values(logs, "threes_attempted")),
        "last10_3pt_pct": _safe_pct(_values(last10, "threes_made"), _values(last10, "threes_attempted")),
        "last5_3pt_pct": _safe_pct(_values(last5, "threes_made"), _values(last5, "threes_attempted")),
        "season_ft_pct": _safe_pct(_values(logs, "free_throws_made"), _values(logs, "free_throws_attempted")),
        "last10_ft_pct": _safe_pct(_values(last10, "free_throws_made"), _values(last10, "free_throws_attempted")),
        "last5_ft_pct": _safe_pct(_values(last5, "free_throws_made"), _values(last5, "free_throws_attempted")),
    }


def _build_points_advanced_aggregates(rows: list[HistoricalAdvancedLog]) -> dict[str, float | None]:
    last10 = rows[:10]
    last5 = rows[:5]
    return {
        "season_ts_pct": _mean(_values(rows, "true_shooting_percentage")),
        "last10_ts_pct": _mean(_values(last10, "true_shooting_percentage")),
        "last5_ts_pct": _mean(_values(last5, "true_shooting_percentage")),
        "season_efg_pct": _mean(_values(rows, "effective_field_goal_percentage")),
        "last10_efg_pct": _mean(_values(last10, "effective_field_goal_percentage")),
        "last5_efg_pct": _mean(_values(last5, "effective_field_goal_percentage")),
    }


def build_pregame_points_features(captured_at: datetime | None = None, limit: int | None = None) -> list[PregamePointsFeatures]:
    seeds = load_pregame_feature_seeds(captured_at=captured_at, stat_type="points", limit=limit)
    feature_rows: list[PregamePointsFeatures] = []
    for seed in seeds:
        opportunity = seed.build_opportunity_features()
        feature_rows.append(
            PregamePointsFeatures(
                **opportunity.to_dict(),
                line=seed.line,
                over_odds=seed.over_odds,
                under_odds=seed.under_odds,
                **_build_points_log_aggregates(seed.recent_logs),
                **_build_points_advanced_aggregates(seed.advanced_rows),
            )
        )
    return feature_rows
