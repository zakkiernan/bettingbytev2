from __future__ import annotations

from sqlalchemy.orm import Session

from api.schemas.board import PropBoardResponse
from api.schemas.detail import PropDetailResponse
from api.services import stats_signal_service


def get_prop_board(
    db: Session,
    game_id: str | None = None,
    recommended_only: bool = False,
    min_confidence: float | None = None,
) -> PropBoardResponse:
    return stats_signal_service.get_prop_board_response(
        db,
        game_id=game_id,
        recommended_only=recommended_only,
        min_confidence=min_confidence,
    )


def get_prop_detail(db: Session, signal_id: int) -> PropDetailResponse | None:
    return stats_signal_service.get_prop_detail_response(db, signal_id)
