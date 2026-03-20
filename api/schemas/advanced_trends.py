from __future__ import annotations

from datetime import datetime

from pydantic import Field

from api.schemas.base import APIModel


class AdvancedTrendPoint(APIModel):
    game_id: str
    game_date: datetime | None = None
    opponent: str | None = None
    is_home: bool | None = None
    minutes: float | None = None
    usage_percentage: float | None = None
    true_shooting_percentage: float | None = None
    effective_field_goal_percentage: float | None = None
    pace: float | None = None
    offensive_rating: float | None = None
    defensive_rating: float | None = None
    net_rating: float | None = None
    touches: float | None = None
    passes: float | None = None
    pie: float | None = None


class AdvancedTrendsResponse(APIModel):
    player_id: str
    player_name: str
    game_count: int = 0
    points: list[AdvancedTrendPoint] = Field(default_factory=list)
