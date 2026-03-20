from __future__ import annotations

from pydantic import Field

from api.schemas.base import APIModel


class LineupContextNarrative(APIModel):
    expected_start: bool | None = None
    starter_confidence: float | None = None
    late_scratch_risk: float | None = None
    missing_teammates_top7: int | None = None
    missing_high_usage_teammates: int | None = None
    missing_primary_ballhandler: bool | None = None
    missing_frontcourt_rotation_piece: bool | None = None
    vacated_minutes_proxy: float | None = None
    vacated_usage_proxy: float | None = None
    pregame_context_confidence: float | None = None
    projected_lineup_confirmed: bool | None = None
    rotation_depletion: str | None = None


class AbsenceStoryEntry(APIModel):
    absent_player_name: str
    absent_player_id: str | None = None
    current_status: str | None = None
    points_delta: float | None = None
    minutes_delta: float | None = None
    usage_delta: float | None = None
    rebounds_delta: float | None = None
    assists_delta: float | None = None
    games_count: int = 0
    sample_confidence: float | None = None


class NarrativeContext(APIModel):
    lineup_context: LineupContextNarrative | None = None
    absence_stories: list[AbsenceStoryEntry] = Field(default_factory=list)
    matchup_note: str | None = None
