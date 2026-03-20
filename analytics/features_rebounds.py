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
class PregameReboundsFeatures(PregameOpportunityFeatures):
    line: float = 0.0
    over_odds: int = 0
    under_odds: int = 0
    season_rebounds_avg: float | None = None
    last10_rebounds_avg: float | None = None
    last5_rebounds_avg: float | None = None
    last10_rebounds_median: float | None = None
    last10_rebounds_std: float | None = None
    season_oreb_avg: float | None = None
    last10_oreb_avg: float | None = None
    last5_oreb_avg: float | None = None
    season_dreb_avg: float | None = None
    last10_dreb_avg: float | None = None
    last5_dreb_avg: float | None = None
    season_reb_pct: float | None = None
    last10_reb_pct: float | None = None
    last5_reb_pct: float | None = None
    season_oreb_pct: float | None = None
    last10_oreb_pct: float | None = None
    last5_oreb_pct: float | None = None
    season_dreb_pct: float | None = None
    last10_dreb_pct: float | None = None
    last5_dreb_pct: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _combined_rebound_pct(row: HistoricalAdvancedLog) -> float | None:
    offensive = getattr(row, "offensive_rebound_percentage", None)
    defensive = getattr(row, "defensive_rebound_percentage", None)
    if offensive is None and defensive is None:
        return None
    return float(offensive or 0.0) + float(defensive or 0.0)


def _reb_pct_values(rows: list[HistoricalAdvancedLog]) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = _combined_rebound_pct(row)
        if value is not None:
            values.append(value)
    return values


def _build_rebounds_log_aggregates(logs: list[HistoricalGameLog]) -> dict[str, float | None]:
    last10 = logs[:10]
    last5 = logs[:5]
    return {
        "season_rebounds_avg": _mean(_values(logs, "rebounds")),
        "last10_rebounds_avg": _mean(_values(last10, "rebounds")),
        "last5_rebounds_avg": _mean(_values(last5, "rebounds")),
        "last10_rebounds_median": _median(_values(last10, "rebounds")),
        "last10_rebounds_std": _std(_values(last10, "rebounds")),
        "season_oreb_avg": _mean(_values(logs, "offensive_rebounds")),
        "last10_oreb_avg": _mean(_values(last10, "offensive_rebounds")),
        "last5_oreb_avg": _mean(_values(last5, "offensive_rebounds")),
        "season_dreb_avg": _mean(_values(logs, "defensive_rebounds")),
        "last10_dreb_avg": _mean(_values(last10, "defensive_rebounds")),
        "last5_dreb_avg": _mean(_values(last5, "defensive_rebounds")),
    }


def _build_rebounds_advanced_aggregates(rows: list[HistoricalAdvancedLog]) -> dict[str, float | None]:
    last10 = rows[:10]
    last5 = rows[:5]
    return {
        "season_reb_pct": _mean(_reb_pct_values(rows)),
        "last10_reb_pct": _mean(_reb_pct_values(last10)),
        "last5_reb_pct": _mean(_reb_pct_values(last5)),
        "season_oreb_pct": _mean(_values(rows, "offensive_rebound_percentage")),
        "last10_oreb_pct": _mean(_values(last10, "offensive_rebound_percentage")),
        "last5_oreb_pct": _mean(_values(last5, "offensive_rebound_percentage")),
        "season_dreb_pct": _mean(_values(rows, "defensive_rebound_percentage")),
        "last10_dreb_pct": _mean(_values(last10, "defensive_rebound_percentage")),
        "last5_dreb_pct": _mean(_values(last5, "defensive_rebound_percentage")),
    }


def build_pregame_rebounds_features_from_seed(seed: PregameFeatureSeed) -> PregameReboundsFeatures:
    opportunity = seed.build_opportunity_features()
    return PregameReboundsFeatures(
        **opportunity.to_dict(),
        line=seed.line,
        over_odds=seed.over_odds,
        under_odds=seed.under_odds,
        **_build_rebounds_log_aggregates(seed.recent_logs),
        **_build_rebounds_advanced_aggregates(seed.advanced_rows),
    )


def build_pregame_rebounds_features_from_seeds(seeds: list[PregameFeatureSeed]) -> list[PregameReboundsFeatures]:
    return [build_pregame_rebounds_features_from_seed(seed) for seed in seeds]


def build_pregame_rebounds_features(captured_at: datetime | None = None, limit: int | None = None) -> list[PregameReboundsFeatures]:
    seeds = load_pregame_feature_seeds(captured_at=captured_at, stat_type="rebounds", limit=limit)
    return build_pregame_rebounds_features_from_seeds(seeds)
