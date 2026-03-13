from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserResponse(APIModel):
    id: int
    email: str
    tier: Literal["FREE", "PREMIUM", "PRO"]
    is_active: bool
    created_at: datetime


class AuthResponse(APIModel):
    user: UserResponse
    token: str


class TeamBrief(APIModel):
    team_id: str
    abbreviation: str
    full_name: str
    city: str | None = None
    nickname: str | None = None


class GameResponse(APIModel):
    game_id: str
    season: str | None = None
    game_date: datetime | None = None
    game_time_utc: datetime | None = None
    home_team: TeamBrief
    away_team: TeamBrief
    game_status: int | None = None
    status_text: str | None = None


class GameDetailResponse(GameResponse):
    home_team_score: int | None = None
    away_team_score: int | None = None
    period: int | None = None
    game_clock: str | None = None
    prop_count: int = 0
    edge_count: int = 0


class PropBoardRow(APIModel):
    signal_id: int
    game_id: str
    game_time_utc: datetime | None = None
    home_team_abbreviation: str
    away_team_abbreviation: str
    player_id: str
    player_name: str
    team_abbreviation: str
    stat_type: str
    line: float
    over_odds: int
    under_odds: int
    projected_value: float
    edge_over: float
    edge_under: float
    over_probability: float
    under_probability: float
    confidence: float
    recommended_side: Literal["OVER", "UNDER"] | None = None
    recent_hit_rate: float | None = None
    recent_games_count: int | None = None
    key_factor: str | None = None


class PropBoardMeta(APIModel):
    total_count: int = 0
    game_count: int = 0
    updated_at: datetime | None = None
    stat_types_available: list[str] = Field(default_factory=lambda: ["points"])


class PropBoardResponse(APIModel):
    props: list[PropBoardRow] = Field(default_factory=list)
    meta: PropBoardMeta


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


class SeasonAverages(APIModel):
    games_played: int = 0
    ppg: float = 0.0
    rpg: float = 0.0
    apg: float = 0.0
    mpg: float = 0.0
    fg_pct: float = 0.0
    three_pct: float = 0.0
    ft_pct: float = 0.0
    usage_pct: float = 0.0
    ts_pct: float = 0.0


class TrendPoint(APIModel):
    game_date: datetime | None = None
    value: float
    line: float | None = None
    hit: bool | None = None


class PlayerProfileResponse(APIModel):
    player_id: str
    full_name: str
    first_name: str | None = None
    last_name: str | None = None
    team_abbreviation: str
    team_full_name: str
    season_averages: SeasonAverages
    active_props: list[PropBoardRow] = Field(default_factory=list)


class EdgeResponse(APIModel):
    signal_id: int
    game_id: str
    game_time_utc: datetime | None = None
    matchup: str
    player_id: str
    player_name: str
    team_abbreviation: str
    stat_type: str
    line: float
    projected_value: float
    edge: float
    confidence: float
    recommended_side: Literal["OVER", "UNDER"] | None = None
    key_factor: str | None = None


class LivePlayerRow(APIModel):
    player_id: str
    player_name: str
    team_abbreviation: str
    stat_type: str
    line: float
    current_stat: float
    live_projection: float
    pace_projection: float
    live_edge: float
    pregame_projection: float
    on_court: bool
    minutes_played: float
    fouls: float


class LiveAlert(APIModel):
    id: str
    type: Literal["edge_emerged", "cold_start", "hot_start", "pace_shift", "foul_trouble"]
    player_name: str
    message: str
    edge_value: float | None = None
    created_at: datetime


class PaceSummary(APIModel):
    current_pace: float = 0.0
    expected_pace: float = 0.0
    scoring_impact_pct: float = 0.0


class LiveGameSummary(APIModel):
    game_id: str
    home_team: TeamBrief
    away_team: TeamBrief
    home_score: int = 0
    away_score: int = 0
    period: int = 0
    game_clock: str = "Not Started"
    live_edge_count: int = 0
    updated_at: datetime | None = None


class LiveGameResponse(LiveGameSummary):
    players: list[LivePlayerRow] = Field(default_factory=list)
    alerts: list[LiveAlert] = Field(default_factory=list)
    pace: PaceSummary
