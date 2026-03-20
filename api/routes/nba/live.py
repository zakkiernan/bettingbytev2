from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas import LiveGameResponse, LiveGameSummary
from api.services import live_service
from database.db import get_db

router = APIRouter(prefix="/live", tags=["live"])


@router.get("/active", response_model=list[LiveGameSummary])
def get_active_live_games(db: Session = Depends(get_db)) -> list[LiveGameSummary]:
    return live_service.get_active_live_games(db)


@router.get("/{game_id}", response_model=LiveGameResponse)
def get_live_game(game_id: str, db: Session = Depends(get_db)) -> LiveGameResponse:
    result = live_service.get_live_game(db, game_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Live game {game_id!r} not found")
    return result
