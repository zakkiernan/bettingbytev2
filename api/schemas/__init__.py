from __future__ import annotations

# Re-export everything from submodules.
# Routes may import from `api.schemas` directly (flat) or from the specific
# submodule (preferred). Both styles work.

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
from api.schemas.games import GameDetailResponse, GameResponse, TeamBrief
from api.schemas.health import (
    IngestionHealthResponse,
    InjuryReportsHealth,
    LinesHealth,
    PregameContextHealth,
    RotationsHealth,
    SignalRunHealth,
)
from api.schemas.live import (
    LiveAlert,
    LiveGameResponse,
    LiveGameSummary,
    LivePlayerRow,
    PaceSummary,
)
from api.schemas.players import PlayerProfileResponse, SeasonAverages, TrendPoint

__all__ = [
    # base
    "APIModel",
    # auth
    "AuthResponse",
    "UserResponse",
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
