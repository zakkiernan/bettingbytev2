from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from api.schemas.base import APIModel
from api.schemas.games import TeamBrief


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
