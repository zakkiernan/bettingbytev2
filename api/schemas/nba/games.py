from __future__ import annotations

from datetime import datetime

from api.schemas.base import APIModel


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
