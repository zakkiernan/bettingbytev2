from __future__ import annotations

from datetime import datetime

from pydantic import Field

from api.schemas.base import APIModel


class LineMovementPoint(APIModel):
    captured_at: datetime
    line: float
    over_odds: int
    under_odds: int
    market_phase: str = "pregame"


class LineMovementResponse(APIModel):
    signal_id: int
    game_id: str
    player_id: str
    player_name: str
    stat_type: str
    current_line: float
    opening_line: float | None = None
    line_movement: float | None = None
    snapshots: list[LineMovementPoint] = Field(default_factory=list)
