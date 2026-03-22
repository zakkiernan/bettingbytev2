from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.schemas import EdgeResponse
from api.services import stats_signal_service
from database.db import get_db

router = APIRouter(prefix="/edges", tags=["edges"])


@router.get("/today", response_model=list[EdgeResponse])
def get_edges_today(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[EdgeResponse]:
    return stats_signal_service.get_edges_today_response(db, limit=limit, offset=offset)
