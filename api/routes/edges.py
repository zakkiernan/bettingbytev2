from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from api.schemas import EdgeResponse
from api.services import stats_signal_service
from database.db import get_db

router = APIRouter(prefix="/edges", tags=["edges"])


@router.get("/today", response_model=list[EdgeResponse])
def get_edges_today(db: Session = Depends(get_db)) -> list[EdgeResponse]:
    return stats_signal_service.get_edges_today_response(db)
