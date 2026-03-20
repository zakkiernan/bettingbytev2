from __future__ import annotations

from pydantic import Field

from api.schemas.base import APIModel


class AbsenceImpactEntry(APIModel):
    source_player_id: str
    source_player_name: str
    beneficiary_player_id: str
    beneficiary_player_name: str
    team_abbreviation: str
    points_delta: float | None = None
    rebounds_delta: float | None = None
    assists_delta: float | None = None
    minutes_delta: float | None = None
    usage_delta: float | None = None
    touches_delta: float | None = None
    source_out_game_count: int = 0
    beneficiary_active_game_count: int = 0
    impact_score: float | None = None
    sample_confidence: float | None = None


class AbsenceImpactResponse(APIModel):
    player_id: str
    player_name: str
    when_player_sits: list[AbsenceImpactEntry] = Field(default_factory=list)
    when_others_sit: list[AbsenceImpactEntry] = Field(default_factory=list)
