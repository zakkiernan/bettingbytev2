from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from api.schemas.base import APIModel


class SignalReadiness(APIModel):
    is_ready: bool = True
    status: Literal["ready", "limited", "blocked"] = "ready"
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    line_age_minutes: int | None = None
    minutes_to_tip: int | None = None
    using_fallback: bool = False


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
    readiness: SignalReadiness = Field(default_factory=SignalReadiness)
    recent_values: list[float] | None = None
    opening_line: float | None = None


class PropBoardMeta(APIModel):
    total_count: int = 0
    game_count: int = 0
    updated_at: datetime | None = None
    stat_types_available: list[str] = Field(default_factory=lambda: ["points"])


class PropBoardResponse(APIModel):
    props: list[PropBoardRow] = Field(default_factory=list)
    meta: PropBoardMeta
