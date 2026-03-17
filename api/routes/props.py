from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.schemas.board import PropBoardResponse
from api.schemas.detail import PropDetailResponse
from api.services import signal_service
from database.db import get_db

router = APIRouter(prefix="/props", tags=["props"])


@router.get("/board", response_model=PropBoardResponse)
def get_prop_board(
    game_id: str | None = Query(default=None, description="Filter to a single game"),
    recommended_only: bool = Query(default=False, description="Only return signals with a recommendation"),
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    db: Session = Depends(get_db),
) -> PropBoardResponse:
    return signal_service.get_prop_board(
        db,
        game_id=game_id,
        recommended_only=recommended_only,
        min_confidence=min_confidence,
    )


@router.get("/{signal_id}", response_model=PropDetailResponse)
def get_prop_detail(signal_id: int, db: Session = Depends(get_db)) -> PropDetailResponse:
    result = signal_service.get_prop_detail(db, signal_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")
    return result
