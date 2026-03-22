from __future__ import annotations

from api.schemas.base import APIModel
from api.schemas.nba.player_stats import ShotChartShot


# ---------------------------------------------------------------------------
# Matchups
# ---------------------------------------------------------------------------

class GameMatchup(APIModel):
    offense_player_id: str
    offense_player_name: str
    defense_player_id: str
    defense_player_name: str
    matchup_minutes: float
    partial_possessions: float | None = None
    player_points: float | None = None
    switches_on: float | None = None
    matchup_field_goals_made: float | None = None
    matchup_field_goals_attempted: float | None = None
    matchup_field_goal_percentage: float | None = None
    matchup_assists: float | None = None
    matchup_turnovers: float | None = None


class GameMatchupsResponse(APIModel):
    game_id: str
    matchups: list[GameMatchup]


# ---------------------------------------------------------------------------
# Win Probability
# ---------------------------------------------------------------------------

class WinProbPoint(APIModel):
    event_num: int
    home_pct: float
    visitor_pct: float
    home_pts: int
    visitor_pts: int
    period: int
    seconds_remaining: float
    description: str | None = None


class WinProbResponse(APIModel):
    game_id: str
    points: list[WinProbPoint]


# ---------------------------------------------------------------------------
# Game Hustle
# ---------------------------------------------------------------------------

class GameHustleRow(APIModel):
    player_id: str
    player_name: str
    team_id: str
    minutes: float | None = None
    contested_shots: float | None = None
    contested_shots_2pt: float | None = None
    contested_shots_3pt: float | None = None
    deflections: float | None = None
    charges_drawn: float | None = None
    screen_assists: float | None = None
    loose_balls_recovered: float | None = None
    box_outs: float | None = None


class GameHustleResponse(APIModel):
    game_id: str
    players: list[GameHustleRow]


# ---------------------------------------------------------------------------
# Game Shot Chart
# ---------------------------------------------------------------------------

class GameShotChartResponse(APIModel):
    game_id: str
    total_shots: int
    shots: list[ShotChartShot]
