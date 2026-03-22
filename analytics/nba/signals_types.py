from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

from database.models import Game, HistoricalGameLog, PlayerPropSnapshot


class SignalModelMixin:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def model_dump(self, *, mode: str | None = None) -> dict[str, Any]:
        return self.to_dict()

    def model_dump_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, default=str)


@dataclass(slots=True)
class SignalReadinessResult(SignalModelMixin):
    is_ready: bool = True
    status: Literal["ready", "limited", "blocked"] = "ready"
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    line_age_minutes: int | None = None
    minutes_to_tip: int | None = None
    using_fallback: bool = False


@dataclass(slots=True)
class SignalInjuryEntry(SignalModelMixin):
    player_name: str
    team_abbreviation: str
    current_status: str
    reason: str


@dataclass(slots=True)
class SignalOpportunityContext(SignalModelMixin):
    expected_minutes: float = 0.0
    season_minutes_avg: float = 0.0
    expected_usage_pct: float = 0.0
    expected_start_rate: float = 0.0
    expected_close_rate: float = 0.0
    role_stability: float = 0.0
    opportunity_score: float = 0.0
    opportunity_confidence: float = 0.0
    availability_modifier: float = 0.0
    vacated_minutes_bonus: float = 0.0
    vacated_usage_bonus: float = 0.0
    injury_entries: list[SignalInjuryEntry] = field(default_factory=list)


@dataclass(slots=True)
class SignalFeatureSnapshot(SignalModelMixin):
    stat_type: str = "points"
    team_abbreviation: str = ""
    opponent_abbreviation: str = ""
    is_home: bool = False
    days_rest: int | None = None
    back_to_back: bool = False
    sample_size: int = 0
    season_points_avg: float | None = None
    last10_points_avg: float | None = None
    last5_points_avg: float | None = None
    season_rebounds_avg: float | None = None
    last10_rebounds_avg: float | None = None
    last5_rebounds_avg: float | None = None
    season_assists_avg: float | None = None
    last10_assists_avg: float | None = None
    last5_assists_avg: float | None = None
    season_threes_avg: float | None = None
    last10_threes_avg: float | None = None
    last5_threes_avg: float | None = None
    season_minutes_avg: float | None = None
    last10_minutes_avg: float | None = None
    last5_minutes_avg: float | None = None
    season_usage_pct: float | None = None
    season_reb_pct: float | None = None
    season_ast_pct: float | None = None
    season_3pa_rate: float | None = None
    opponent_def_rating: float | None = None
    opponent_pace: float | None = None
    team_pace: float | None = None
    context_source: str | None = None


@dataclass(slots=True)
class SignalBreakdown(SignalModelMixin):
    base_scoring: float = 0.0
    base_rebounding: float = 0.0
    base_playmaking: float = 0.0
    base_shooting: float = 0.0
    recent_form_adjustment: float = 0.0
    minutes_adjustment: float = 0.0
    usage_adjustment: float = 0.0
    rebound_rate_adjustment: float = 0.0
    playmaking_adjustment: float = 0.0
    volume_adjustment: float = 0.0
    efficiency_adjustment: float = 0.0
    opponent_adjustment: float = 0.0
    pace_adjustment: float = 0.0
    context_adjustment: float = 0.0
    expected_minutes: float = 0.0
    expected_usage_pct: float = 0.0
    points_per_minute: float = 0.0
    rebounds_per_minute: float = 0.0
    assists_per_minute: float = 0.0
    threes_per_minute: float = 0.0
    projected_points: float = 0.0
    projected_rebounds: float = 0.0
    projected_assists: float = 0.0
    projected_threes: float = 0.0


@dataclass(slots=True)
class StatsSignalProfile(SignalModelMixin):
    projected_value: float
    edge_over: float
    edge_under: float
    over_probability: float
    under_probability: float
    confidence: float
    recommended_side: Literal["OVER", "UNDER"] | None
    recent_hit_rate: float | None
    recent_games_count: int
    key_factor: str | None
    breakdown: SignalBreakdown
    opportunity: SignalOpportunityContext
    feature_snapshot: SignalFeatureSnapshot
    readiness: SignalReadinessResult = field(default_factory=SignalReadinessResult)
    source_context_captured_at: datetime | None = None
    source_injury_report_at: datetime | None = None


@dataclass(slots=True)
class StatsSignalCard:
    snapshot: PlayerPropSnapshot
    game: Game | None
    profile: StatsSignalProfile
    recent_logs: list[HistoricalGameLog]
