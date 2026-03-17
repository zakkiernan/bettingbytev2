from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.schemas.health import IngestionHealthResponse
from api.services import health_service
from database.db import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=IngestionHealthResponse)
def get_ingestion_health(db: Session = Depends(get_db)) -> IngestionHealthResponse:
    """Pipeline health snapshot: lines, rotations, injury reports, context, signals."""
    return health_service.get_ingestion_health(db)
