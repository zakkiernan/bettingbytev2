from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.request_params import GameIdPath
from api.schemas.game_context import GameContextResponse
from api.schemas.games import GameDetailResponse, GameResponse
from api.schemas.nba.game_stats import (
    GameHustleResponse,
    GameMatchupsResponse,
    GameShotChartResponse,
    WinProbResponse,
)
from api.services import game_context_service, game_service, game_stats_service
from database.db import get_db

router = APIRouter(prefix="/games", tags=["games"])


@router.get("/today", response_model=list[GameDetailResponse])
def get_games_today(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[GameDetailResponse]:
    return game_service.get_games_today(db, limit=limit, offset=offset)


@router.get("/{game_id}", response_model=GameDetailResponse)
def get_game_detail(game_id: GameIdPath, db: Session = Depends(get_db)) -> GameDetailResponse:
    result = game_service.get_game_detail(db, game_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id!r} not found")
    return result


@router.get("/{game_id}/context", response_model=GameContextResponse)
def get_game_context(game_id: GameIdPath, db: Session = Depends(get_db)) -> GameContextResponse:
    result = game_context_service.get_game_context(db, game_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id!r} not found")
    return result


@router.get("/{game_id}/matchups", response_model=GameMatchupsResponse)
def get_game_matchups(game_id: GameIdPath, db: Session = Depends(get_db)) -> GameMatchupsResponse:
    result = game_stats_service.get_game_matchups(db, game_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id!r} not found")
    return result


@router.get("/{game_id}/win-probability", response_model=WinProbResponse)
def get_game_win_probability(game_id: GameIdPath, db: Session = Depends(get_db)) -> WinProbResponse:
    result = game_stats_service.get_game_win_probability(db, game_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id!r} not found")
    return result


@router.get("/{game_id}/hustle", response_model=GameHustleResponse)
def get_game_hustle(game_id: GameIdPath, db: Session = Depends(get_db)) -> GameHustleResponse:
    result = game_stats_service.get_game_hustle(db, game_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id!r} not found")
    return result


@router.get("/{game_id}/shot-chart", response_model=GameShotChartResponse)
def get_game_shot_chart(game_id: GameIdPath, db: Session = Depends(get_db)) -> GameShotChartResponse:
    result = game_stats_service.get_game_shot_chart(db, game_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id!r} not found")
    return result
