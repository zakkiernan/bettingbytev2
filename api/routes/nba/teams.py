from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas.nba.team_stats import TeamLineupsResponse, TeamProfileResponse
from api.services import team_stats_service
from database.db import get_db

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/{team_id}", response_model=TeamProfileResponse)
def get_team_profile(team_id: str, db: Session = Depends(get_db)) -> TeamProfileResponse:
    result = team_stats_service.get_team_profile(db, team_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Team {team_id!r} not found")
    return result


@router.get("/{team_id}/lineups", response_model=TeamLineupsResponse)
def get_team_lineups(team_id: str, db: Session = Depends(get_db)) -> TeamLineupsResponse:
    result = team_stats_service.get_team_lineups(db, team_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Team {team_id!r} not found")
    return result
