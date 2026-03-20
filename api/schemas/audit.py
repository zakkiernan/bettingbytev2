from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from api.schemas.base import APIModel
from api.schemas.detail import PointsBreakdown


class SignalAuditEntry(APIModel):
    id: int
    game_id: str
    player_id: str
    stat_type: str
    snapshot_phase: str
    line: float
    projected_value: float
    edge: float
    confidence: float
    recommended_side: Literal["OVER", "UNDER"] | None = None
    readiness_status: Literal["ready", "limited", "blocked"]
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    breakdown: PointsBreakdown
    source_context_captured_at: datetime | None = None
    source_injury_report_at: datetime | None = None
    captured_at: datetime
