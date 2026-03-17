from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from api.schemas.base import APIModel
from api.schemas.board import PropBoardRow


class PointsBreakdown(APIModel):
    base_scoring: float = 0.0
    recent_form_adjustment: float = 0.0
    minutes_adjustment: float = 0.0
    usage_adjustment: float = 0.0
    efficiency_adjustment: float = 0.0
    opponent_adjustment: float = 0.0
    pace_adjustment: float = 0.0
    context_adjustment: float = 0.0
    expected_minutes: float = 0.0
    expected_usage_pct: float = 0.0
    points_per_minute: float = 0.0
    projected_points: float = 0.0


class InjuryEntry(APIModel):
    player_name: str
    team_abbreviation: str
    current_status: Literal["Out", "Doubtful", "Questionable", "Probable"]
    reason: str


class OpportunityContext(APIModel):
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
    injury_entries: list[InjuryEntry] = Field(default_factory=list)


class FeatureSnapshot(APIModel):
    team_abbreviation: str
    opponent_abbreviation: str
    is_home: bool
    days_rest: int | None = None
    back_to_back: bool = False
    sample_size: int = 0
    season_points_avg: float | None = None
    last10_points_avg: float | None = None
    last5_points_avg: float | None = None
    season_minutes_avg: float | None = None
    last10_minutes_avg: float | None = None
    last5_minutes_avg: float | None = None
    season_usage_pct: float | None = None
    opponent_def_rating: float | None = None
    opponent_pace: float | None = None
    team_pace: float | None = None
    context_source: str | None = None


class GameLogEntry(APIModel):
    game_id: str
    game_date: datetime | None = None
    opponent: str
    is_home: bool
    minutes: float = 0.0
    points: float = 0.0
    rebounds: float = 0.0
    assists: float = 0.0
    steals: float = 0.0
    blocks: float = 0.0
    turnovers: float = 0.0
    threes_made: float = 0.0
    field_goals_made: float = 0.0
    field_goals_attempted: float = 0.0
    free_throws_made: float = 0.0
    free_throws_attempted: float = 0.0
    plus_minus: float = 0.0


class PropDetailResponse(PropBoardRow):
    breakdown: PointsBreakdown
    opportunity: OpportunityContext
    features: FeatureSnapshot
    recent_game_log: list[GameLogEntry] = Field(default_factory=list)
