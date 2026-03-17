from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from api.schemas.base import APIModel
from api.schemas.board import PropBoardRow, SignalReadiness
from api.schemas.detail import FeatureSnapshot, OpportunityContext, PointsBreakdown


class SeasonAverages(APIModel):
    games_played: int = 0
    ppg: float = 0.0
    rpg: float = 0.0
    apg: float = 0.0
    mpg: float = 0.0
    fg_pct: float = 0.0
    three_pct: float = 0.0
    ft_pct: float = 0.0
    usage_pct: float = 0.0
    ts_pct: float = 0.0


class TrendPoint(APIModel):
    game_date: datetime | None = None
    value: float
    line: float | None = None
    hit: bool | None = None


class SignalHistoryEntry(APIModel):
    signal_snapshot_id: int
    game_id: str
    game_time_utc: datetime | None = None
    created_at: datetime
    snapshot_phase: str
    stat_type: str
    line: float
    projected_value: float
    confidence: float | None = None
    recommended_side: Literal["OVER", "UNDER"] | None = None
    key_factor: str | None = None
    readiness: SignalReadiness
    breakdown: PointsBreakdown
    opportunity: OpportunityContext
    features: FeatureSnapshot
    source_prop_captured_at: datetime | None = None
    source_context_captured_at: datetime | None = None
    source_injury_report_at: datetime | None = None


class PlayerProfileResponse(APIModel):
    player_id: str
    full_name: str
    first_name: str | None = None
    last_name: str | None = None
    team_abbreviation: str
    team_full_name: str
    season_averages: SeasonAverages
    active_props: list[PropBoardRow] = Field(default_factory=list)
