from __future__ import annotations

from fastapi import FastAPI

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

app = FastAPI(title="BettingByte API", version="0.1.0")

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


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
