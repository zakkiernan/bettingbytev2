from __future__ import annotations

from api.schemas.base import APIModel


class LineupEntry(APIModel):
    group_id: str
    group_name: str
    gp: int | None = None
    min: float | None = None
    off_rating: float | None = None
    def_rating: float | None = None
    net_rating: float | None = None
    pace: float | None = None
    ts_pct: float | None = None
    efg_pct: float | None = None
    plus_minus: float | None = None


class TeamLineupsResponse(APIModel):
    team_id: str
    team_abbreviation: str | None = None
    season: str
    lineups: list[LineupEntry]


class TeamDefenseProfile(APIModel):
    team_id: str
    team_name: str
    season: str
    defensive_rating: float | None = None
    pace: float | None = None
    opponent_points_per_game: float | None = None
    opponent_field_goal_percentage: float | None = None
    opponent_three_point_percentage: float | None = None


class TeamProfileResponse(APIModel):
    team_id: str
    team_abbreviation: str | None = None
    team_name: str
    lineups: TeamLineupsResponse
    defense: TeamDefenseProfile | None = None
