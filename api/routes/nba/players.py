from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.request_params import (
    PlayerIdPath,
    ShotChartGameIdQuery,
    SignalHistoryStatTypeQuery,
    TrendStatTypeQuery,
)
from api.schemas.absence_impact import AbsenceImpactResponse
from api.schemas.advanced_trends import AdvancedTrendsResponse
from api.schemas.detail import GameLogEntry
from api.schemas.nba.player_stats import (
    ClutchResponse,
    DefensiveTrackingResponse,
    HustleStatsResponse,
    OnOffResponse,
    PlayTypesResponse,
    ShotChartResponse,
    ShotLocationsResponse,
    TrackingResponse,
)
from api.schemas.players import PlayerProfileResponse, SignalHistoryEntry, TrendPoint
from api.schemas.rotation import RotationProfile
from api.services import player_analytics_service, player_service, player_stats_service
from database.db import get_db

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/{player_id}", response_model=PlayerProfileResponse)
def get_player_profile(player_id: PlayerIdPath, db: Session = Depends(get_db)) -> PlayerProfileResponse:
    result = player_service.get_player_profile(db, player_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result


@router.get("/{player_id}/game-log", response_model=list[GameLogEntry])
def get_player_game_log(
    player_id: PlayerIdPath,
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[GameLogEntry]:
    return player_service.get_player_game_log(db, player_id, limit=limit, offset=offset)


@router.get("/{player_id}/trends", response_model=list[TrendPoint])
def get_player_trends(
    player_id: PlayerIdPath,
    stat_type: TrendStatTypeQuery = "points",
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[TrendPoint]:
    return player_service.get_player_trends(db, player_id, stat_type=stat_type, limit=limit, offset=offset)


@router.get("/{player_id}/signal-history", response_model=list[SignalHistoryEntry])
def get_player_signal_history(
    player_id: PlayerIdPath,
    stat_type: SignalHistoryStatTypeQuery = "points",
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[SignalHistoryEntry]:
    return player_service.get_player_signal_history(
        db,
        player_id,
        stat_type=stat_type,
        limit=limit,
        offset=offset,
    )


@router.get("/{player_id}/advanced-trends", response_model=AdvancedTrendsResponse)
def get_player_advanced_trends(
    player_id: PlayerIdPath,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> AdvancedTrendsResponse:
    result = player_analytics_service.get_advanced_trends(db, player_id, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result


@router.get("/{player_id}/rotation-profile", response_model=RotationProfile)
def get_player_rotation_profile(
    player_id: PlayerIdPath,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> RotationProfile:
    result = player_analytics_service.get_rotation_profile(db, player_id, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result


@router.get("/{player_id}/absence-impact", response_model=AbsenceImpactResponse)
def get_player_absence_impact(
    player_id: PlayerIdPath,
    db: Session = Depends(get_db),
) -> AbsenceImpactResponse:
    result = player_analytics_service.get_absence_impact(db, player_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result


# ---------------------------------------------------------------------------
# New stats endpoints
# ---------------------------------------------------------------------------


@router.get("/{player_id}/shot-chart", response_model=ShotChartResponse)
def get_player_shot_chart(
    player_id: PlayerIdPath,
    last_n: int | None = Query(default=None, ge=1, le=82, description="Last N games"),
    game_id: ShotChartGameIdQuery = None,
    db: Session = Depends(get_db),
) -> ShotChartResponse:
    result = player_stats_service.get_player_shot_chart(db, player_id, last_n=last_n, game_id=game_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result


@router.get("/{player_id}/shot-locations", response_model=ShotLocationsResponse)
def get_player_shot_locations(
    player_id: PlayerIdPath,
    db: Session = Depends(get_db),
) -> ShotLocationsResponse:
    result = player_stats_service.get_player_shot_locations(db, player_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result


@router.get("/{player_id}/play-types", response_model=PlayTypesResponse)
def get_player_play_types(
    player_id: PlayerIdPath,
    db: Session = Depends(get_db),
) -> PlayTypesResponse:
    result = player_stats_service.get_player_play_types(db, player_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result


@router.get("/{player_id}/hustle", response_model=HustleStatsResponse)
def get_player_hustle(
    player_id: PlayerIdPath,
    db: Session = Depends(get_db),
) -> HustleStatsResponse:
    result = player_stats_service.get_player_hustle(db, player_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result


@router.get("/{player_id}/tracking", response_model=TrackingResponse)
def get_player_tracking(
    player_id: PlayerIdPath,
    db: Session = Depends(get_db),
) -> TrackingResponse:
    result = player_stats_service.get_player_tracking(db, player_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result


@router.get("/{player_id}/defense", response_model=DefensiveTrackingResponse)
def get_player_defense(
    player_id: PlayerIdPath,
    db: Session = Depends(get_db),
) -> DefensiveTrackingResponse:
    result = player_stats_service.get_player_defense(db, player_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result


@router.get("/{player_id}/on-off", response_model=OnOffResponse)
def get_player_on_off(
    player_id: PlayerIdPath,
    db: Session = Depends(get_db),
) -> OnOffResponse:
    result = player_stats_service.get_player_on_off(db, player_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result


@router.get("/{player_id}/clutch", response_model=ClutchResponse)
def get_player_clutch(
    player_id: PlayerIdPath,
    db: Session = Depends(get_db),
) -> ClutchResponse:
    result = player_stats_service.get_player_clutch(db, player_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id!r} not found")
    return result
