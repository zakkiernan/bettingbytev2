from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
except ModuleNotFoundError:  # pragma: no cover - optional local dependency
    _rate_limit_exceeded_handler = None
    RateLimitExceeded = None
    SlowAPIMiddleware = None

from api.rate_limit import limiter
from api.routes import (
    audit_router,
    auth_router,
    health_router,
    nba_edges_router,
    nba_games_router,
    nba_live_router,
    nba_players_router,
    nba_props_router,
    nba_teams_router,
)
from api.schemas.health import SystemHealthResponse
from config import get_settings, validate_startup_settings
from database.db import get_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("bettingbyte.api")

settings = validate_startup_settings(get_settings())

app = FastAPI(title="BettingByte API", version=settings.api_version)
app.state.limiter = limiter
if RateLimitExceeded is not None and _rate_limit_exceeded_handler is not None:
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
if SlowAPIMiddleware is not None:
    app.add_middleware(SlowAPIMiddleware)
else:
    logger.warning("slowapi is not installed; API rate limiting is disabled for this local run")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allow_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_unhandled_exceptions(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled request error for %s %s", request.method, request.url.path)
        raise

# Shared routes at /api
app.include_router(auth_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(health_router, prefix="/api")

# NBA routes at /api/nba
app.include_router(nba_games_router, prefix="/api/nba")
app.include_router(nba_props_router, prefix="/api/nba")
app.include_router(nba_edges_router, prefix="/api/nba")
app.include_router(nba_players_router, prefix="/api/nba")
app.include_router(nba_live_router, prefix="/api/nba")
app.include_router(nba_teams_router, prefix="/api/nba")

# Backward-compat NBA routes at /api
app.include_router(nba_games_router, prefix="/api")
app.include_router(nba_props_router, prefix="/api")
app.include_router(nba_edges_router, prefix="/api")
app.include_router(nba_players_router, prefix="/api")
app.include_router(nba_live_router, prefix="/api")


@app.get("/health", response_model=SystemHealthResponse)
def healthcheck(response: Response, db: Session = Depends(get_db)) -> SystemHealthResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check database probe failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return SystemHealthResponse(
            status="degraded",
            db="disconnected",
            version=settings.api_version,
        )

    return SystemHealthResponse(
        status="ok",
        db="connected",
        version=settings.api_version,
    )
