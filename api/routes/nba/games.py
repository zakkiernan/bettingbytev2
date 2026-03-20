from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas.game_context import GameContextResponse
from api.schemas.games import GameDetailResponse, GameResponse
from api.services import game_context_service, game_service
from database.db import get_db

router = APIRouter(prefix="/games", tags=["games"])


@router.get("/today", response_model=list[GameDetailResponse])
def get_games_today(db: Session = Depends(get_db)) -> list[GameDetailResponse]:
    return game_service.get_games_today(db)


@router.get("/{game_id}", response_model=GameDetailResponse)
def get_game_detail(game_id: str, db: Session = Depends(get_db)) -> GameDetailResponse:
    result = game_service.get_game_detail(db, game_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id!r} not found")
    return result


@router.get("/{game_id}/context", response_model=GameContextResponse)
def get_game_context(game_id: str, db: Session = Depends(get_db)) -> GameContextResponse:
    result = game_context_service.get_game_context(db, game_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id!r} not found")
    return result
