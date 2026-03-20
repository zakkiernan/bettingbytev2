from __future__ import annotations

from datetime import datetime

from pydantic import Field

from api.schemas.base import APIModel


class RotationGameEntry(APIModel):
    game_id: str
    game_date: datetime | None = None
    opponent: str | None = None
    started: bool | None = None
    closed_game: bool | None = None
    stint_count: int | None = None
    total_shift_duration_real: float | None = None
    avg_shift_duration_real: float | None = None


class RotationProfile(APIModel):
    player_id: str
    player_name: str
    games_tracked: int = 0
    start_rate: float = 0.0
    close_rate: float = 0.0
    avg_stint_count: float = 0.0
    avg_minutes: float = 0.0
    recent_games: list[RotationGameEntry] = Field(default_factory=list)
