from __future__ import annotations

from sqlalchemy.orm import Session

from api.schemas.board import PropBoardResponse
from api.schemas.detail import PropDetailResponse
from api.schemas.line_movement import LineMovementResponse
from api.services import stats_signal_service


def get_prop_board(
    db: Session,
    game_id: str | None = None,
    stat_type: str | None = None,
    recommended_only: bool = False,
    min_confidence: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PropBoardResponse:
    return stats_signal_service.get_prop_board_response(
        db,
        game_id=game_id,
        stat_type=stat_type,
        recommended_only=recommended_only,
        min_confidence=min_confidence,
        limit=limit,
        offset=offset,
    )


def get_prop_detail(db: Session, signal_id: int) -> PropDetailResponse | None:
    return stats_signal_service.get_prop_detail_response(db, signal_id)


def get_line_movement(db: Session, signal_id: int) -> LineMovementResponse | None:
    return stats_signal_service.get_line_movement(db, signal_id)
