from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.schemas.absence_impact import AbsenceImpactResponse
from api.schemas.advanced_trends import AdvancedTrendsResponse
from api.schemas.detail import GameLogEntry
from api.schemas.players import PlayerProfileResponse, SignalHistoryEntry, TrendPoint
from api.schemas.rotation import RotationProfile
from api.services import player_analytics_service, player_service
from database.db import get_db

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/{player_id}", response_model=PlayerProfileResponse)
def get_player_profile(player_id: str, db: Session = Depends(get_db)) -> PlayerProfileResponse:
    result = player_service.get_player_profile(db, player_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result


@router.get("/{player_id}/game-log", response_model=list[GameLogEntry])
def get_player_game_log(
    player_id: str,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[GameLogEntry]:
    return player_service.get_player_game_log(db, player_id, limit=limit)


@router.get("/{player_id}/trends", response_model=list[TrendPoint])
def get_player_trends(
    player_id: str,
    stat_type: str = Query(default="points", description="Stat type: points, rebounds, assists"),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[TrendPoint]:
    return player_service.get_player_trends(db, player_id, stat_type=stat_type, limit=limit)


@router.get("/{player_id}/signal-history", response_model=list[SignalHistoryEntry])
def get_player_signal_history(
    player_id: str,
    stat_type: str = Query(default="points", description="Stat type: points"),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[SignalHistoryEntry]:
    return player_service.get_player_signal_history(db, player_id, stat_type=stat_type, limit=limit)


@router.get("/{player_id}/advanced-trends", response_model=AdvancedTrendsResponse)
def get_player_advanced_trends(
    player_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> AdvancedTrendsResponse:
    result = player_analytics_service.get_advanced_trends(db, player_id, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result


@router.get("/{player_id}/rotation-profile", response_model=RotationProfile)
def get_player_rotation_profile(
    player_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> RotationProfile:
    result = player_analytics_service.get_rotation_profile(db, player_id, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result


@router.get("/{player_id}/absence-impact", response_model=AbsenceImpactResponse)
def get_player_absence_impact(
    player_id: str,
    db: Session = Depends(get_db),
) -> AbsenceImpactResponse:
    result = player_analytics_service.get_absence_impact(db, player_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result
