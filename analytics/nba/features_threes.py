from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from analytics.features_opportunity import (
    PregameFeatureSeed,
    PregameOpportunityFeatures,
    _mean,
    _median,
    _safe_pct,
    _std,
    _values,
    load_pregame_feature_seeds,
)
from database.models import HistoricalGameLog


@dataclass(slots=True)
class PregameThreesFeatures(PregameOpportunityFeatures):
    line: float = 0.0
    over_odds: int = 0
    under_odds: int = 0
    season_threes_avg: float | None = None
    last10_threes_avg: float | None = None
    last5_threes_avg: float | None = None
    last10_threes_median: float | None = None
    last10_threes_std: float | None = None
    season_3pa_avg: float | None = None
    last10_3pa_avg: float | None = None
    last5_3pa_avg: float | None = None
    season_3pt_pct: float | None = None
    last10_3pt_pct: float | None = None
    last5_3pt_pct: float | None = None
    season_3pa_rate: float | None = None
    last10_3pa_rate: float | None = None
    last5_3pa_rate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _build_threes_log_aggregates(logs: list[HistoricalGameLog]) -> dict[str, float | None]:
    last10 = logs[:10]
    last5 = logs[:5]
    return {
        "season_threes_avg": _mean(_values(logs, "threes_made")),
        "last10_threes_avg": _mean(_values(last10, "threes_made")),
        "last5_threes_avg": _mean(_values(last5, "threes_made")),
        "last10_threes_median": _median(_values(last10, "threes_made")),
        "last10_threes_std": _std(_values(last10, "threes_made")),
        "season_3pa_avg": _mean(_values(logs, "threes_attempted")),
        "last10_3pa_avg": _mean(_values(last10, "threes_attempted")),
        "last5_3pa_avg": _mean(_values(last5, "threes_attempted")),
        "season_3pt_pct": _safe_pct(_values(logs, "threes_made"), _values(logs, "threes_attempted")),
        "last10_3pt_pct": _safe_pct(_values(last10, "threes_made"), _values(last10, "threes_attempted")),
        "last5_3pt_pct": _safe_pct(_values(last5, "threes_made"), _values(last5, "threes_attempted")),
        "season_3pa_rate": _safe_pct(_values(logs, "threes_attempted"), _values(logs, "field_goals_attempted")),
        "last10_3pa_rate": _safe_pct(_values(last10, "threes_attempted"), _values(last10, "field_goals_attempted")),
        "last5_3pa_rate": _safe_pct(_values(last5, "threes_attempted"), _values(last5, "field_goals_attempted")),
    }


def build_pregame_threes_features_from_seed(seed: PregameFeatureSeed) -> PregameThreesFeatures:
    opportunity = seed.build_opportunity_features()
    return PregameThreesFeatures(
        **opportunity.to_dict(),
        line=seed.line,
        over_odds=seed.over_odds,
        under_odds=seed.under_odds,
        **_build_threes_log_aggregates(seed.recent_logs),
    )


def build_pregame_threes_features_from_seeds(seeds: list[PregameFeatureSeed]) -> list[PregameThreesFeatures]:
    return [build_pregame_threes_features_from_seed(seed) for seed in seeds]


def build_pregame_threes_features(captured_at: datetime | None = None, limit: int | None = None) -> list[PregameThreesFeatures]:
    seeds = load_pregame_feature_seeds(captured_at=captured_at, stat_type="threes", limit=limit)
    return build_pregame_threes_features_from_seeds(seeds)
