from __future__ import annotations

from datetime import datetime

from pydantic import Field

from api.schemas.base import APIModel
from api.schemas.detail import InjuryEntry


class LineupEntry(APIModel):
    player_id: str | None = None
    player_name: str | None = None
    expected_start: bool | None = None
    starter_confidence: float | None = None
    late_scratch_risk: float | None = None
    official_available: bool | None = None
    projected_available: bool | None = None


class TeamDefenseSnapshot(APIModel):
    defensive_rating: float | None = None
    pace: float | None = None
    opponent_points_per_game: float | None = None
    opponent_field_goal_percentage: float | None = None
    opponent_three_point_percentage: float | None = None


class TeamGameContext(APIModel):
    team_abbreviation: str
    team_name: str | None = None
    expected_lineup: list[LineupEntry] = Field(default_factory=list)
    injury_entries: list[InjuryEntry] = Field(default_factory=list)
    defense: TeamDefenseSnapshot | None = None
    teammate_out_count_top7: float | None = None
    teammate_out_count_top9: float | None = None


class GameContextResponse(APIModel):
    game_id: str
    game_date: datetime | None = None
    game_time_utc: datetime | None = None
    home_team: TeamGameContext
    away_team: TeamGameContext
    pace_matchup: float | None = None
