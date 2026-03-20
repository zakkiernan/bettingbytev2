from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.schemas.audit import SignalAuditEntry
from api.services import audit_service
from database.db import get_db

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/player/{player_id}/game/{game_id}", response_model=list[SignalAuditEntry])
def get_player_game_audit(
    player_id: str,
    game_id: str,
    db: Session = Depends(get_db),
) -> list[SignalAuditEntry]:
    return audit_service.get_player_game_audit_rows(db, player_id=player_id, game_id=game_id)


@router.get("/game/{game_id}", response_model=list[SignalAuditEntry])
def get_game_audit(
    game_id: str,
    db: Session = Depends(get_db),
) -> list[SignalAuditEntry]:
    return audit_service.get_game_audit_rows(db, game_id=game_id)


@router.get("/recent", response_model=list[SignalAuditEntry])
def get_recent_audit(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[SignalAuditEntry]:
    return audit_service.get_recent_audit_rows(db, limit=limit)
