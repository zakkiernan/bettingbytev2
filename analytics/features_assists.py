from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from analytics.features_opportunity import (
    PregameFeatureSeed,
    PregameOpportunityFeatures,
    _mean,
    _median,
    _std,
    _values,
    load_pregame_feature_seeds,
)
from database.models import HistoricalAdvancedLog, HistoricalGameLog


@dataclass(slots=True)
class PregameAssistsFeatures(PregameOpportunityFeatures):
    line: float = 0.0
    over_odds: int = 0
    under_odds: int = 0
    season_assists_avg: float | None = None
    last10_assists_avg: float | None = None
    last5_assists_avg: float | None = None
    last10_assists_median: float | None = None
    last10_assists_std: float | None = None
    season_ast_pct: float | None = None
    last10_ast_pct: float | None = None
    last5_ast_pct: float | None = None
    season_potential_assists: float | None = None
    last10_potential_assists: float | None = None
    last5_potential_assists: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _advanced_values(rows: list[HistoricalAdvancedLog], attr: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = getattr(row, attr, None)
        if value is not None:
            values.append(float(value))
    return values


def _build_assists_log_aggregates(logs: list[HistoricalGameLog]) -> dict[str, float | None]:
    last10 = logs[:10]
    last5 = logs[:5]
    return {
        "season_assists_avg": _mean(_values(logs, "assists")),
        "last10_assists_avg": _mean(_values(last10, "assists")),
        "last5_assists_avg": _mean(_values(last5, "assists")),
        "last10_assists_median": _median(_values(last10, "assists")),
        "last10_assists_std": _std(_values(last10, "assists")),
    }


def _build_assists_advanced_aggregates(rows: list[HistoricalAdvancedLog]) -> dict[str, float | None]:
    last10 = rows[:10]
    last5 = rows[:5]
    return {
        "season_ast_pct": _mean(_values(rows, "assist_percentage")),
        "last10_ast_pct": _mean(_values(last10, "assist_percentage")),
        "last5_ast_pct": _mean(_values(last5, "assist_percentage")),
        "season_potential_assists": _mean(_advanced_values(rows, "potential_assists")),
        "last10_potential_assists": _mean(_advanced_values(last10, "potential_assists")),
        "last5_potential_assists": _mean(_advanced_values(last5, "potential_assists")),
    }


def build_pregame_assists_features_from_seed(seed: PregameFeatureSeed) -> PregameAssistsFeatures:
    opportunity = seed.build_opportunity_features()
    return PregameAssistsFeatures(
        **opportunity.to_dict(),
        line=seed.line,
        over_odds=seed.over_odds,
        under_odds=seed.under_odds,
        **_build_assists_log_aggregates(seed.recent_logs),
        **_build_assists_advanced_aggregates(seed.advanced_rows),
    )


def build_pregame_assists_features_from_seeds(seeds: list[PregameFeatureSeed]) -> list[PregameAssistsFeatures]:
    return [build_pregame_assists_features_from_seed(seed) for seed in seeds]


def build_pregame_assists_features(captured_at: datetime | None = None, limit: int | None = None) -> list[PregameAssistsFeatures]:
    seeds = load_pregame_feature_seeds(captured_at=captured_at, stat_type="assists", limit=limit)
    return build_pregame_assists_features_from_seeds(seeds)
