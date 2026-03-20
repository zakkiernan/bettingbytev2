from __future__ import annotations

# Re-export everything from submodules.
# Routes may import from `api.schemas` directly (flat) or from the specific
# submodule (preferred). Both styles work.

from api.schemas.absence_impact import AbsenceImpactEntry, AbsenceImpactResponse
from api.schemas.advanced_trends import AdvancedTrendPoint, AdvancedTrendsResponse
from api.schemas.audit import SignalAuditEntry
from api.schemas.auth import AuthResponse, UserResponse
from api.schemas.base import APIModel
from api.schemas.board import PropBoardMeta, PropBoardResponse, PropBoardRow
from api.schemas.detail import (
    FeatureSnapshot,
    GameLogEntry,
    InjuryEntry,
    OpportunityContext,
    PointsBreakdown,
    PropDetailResponse,
)
from api.schemas.edges import EdgeResponse
from api.schemas.game_context import (
    GameContextResponse,
    LineupEntry,
    TeamDefenseSnapshot,
    TeamGameContext,
)
from api.schemas.games import GameDetailResponse, GameResponse, TeamBrief
from api.schemas.health import (
    IngestionHealthResponse,
    InjuryReportsHealth,
    LinesHealth,
    PregameContextHealth,
    RotationsHealth,
    SignalRunHealth,
)
from api.schemas.line_movement import LineMovementPoint, LineMovementResponse
from api.schemas.live import (
    LiveAlert,
    LiveGameResponse,
    LiveGameSummary,
    LivePlayerRow,
    PaceSummary,
)
from api.schemas.narrative import (
    AbsenceStoryEntry,
    LineupContextNarrative,
    NarrativeContext,
)
from api.schemas.players import PlayerProfileResponse, SeasonAverages, TrendPoint
from api.schemas.rotation import RotationGameEntry, RotationProfile

__all__ = [
    # base
    "APIModel",
    # auth
    "AuthResponse",
    "UserResponse",
    # audit
    "SignalAuditEntry",
    # games
    "GameDetailResponse",
    "GameResponse",
    "TeamBrief",
    # board
    "PropBoardMeta",
    "PropBoardResponse",
    "PropBoardRow",
    # detail
    "FeatureSnapshot",
    "GameLogEntry",
    "InjuryEntry",
    "OpportunityContext",
    "PointsBreakdown",
    "PropDetailResponse",
    # edges
    "EdgeResponse",
    # players
    "PlayerProfileResponse",
    "SeasonAverages",
    "TrendPoint",
    # advanced trends
    "AdvancedTrendPoint",
    "AdvancedTrendsResponse",
    # rotation
    "RotationGameEntry",
    "RotationProfile",
    # absence impact
    "AbsenceImpactEntry",
    "AbsenceImpactResponse",
    # game context
    "GameContextResponse",
    "LineupEntry",
    "TeamDefenseSnapshot",
    "TeamGameContext",
    # line movement
    "LineMovementPoint",
    "LineMovementResponse",
    # narrative
    "AbsenceStoryEntry",
    "LineupContextNarrative",
    "NarrativeContext",
    # live
    "LiveAlert",
    "LiveGameResponse",
    "LiveGameSummary",
    "LivePlayerRow",
    "PaceSummary",
    # health
    "IngestionHealthResponse",
    "InjuryReportsHealth",
    "LinesHealth",
    "PregameContextHealth",
    "RotationsHealth",
    "SignalRunHealth",
]
