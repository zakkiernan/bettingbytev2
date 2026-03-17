from __future__ import annotations

from datetime import datetime
from typing import Literal

from api.schemas.base import APIModel


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
