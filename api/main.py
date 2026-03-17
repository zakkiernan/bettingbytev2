from __future__ import annotations

from fastapi import FastAPI

from api.routes import (
    auth_router,
    edges_router,
    games_router,
    health_router,
    live_router,
    players_router,
    props_router,
)

app = FastAPI(title="BettingByte API", version="0.1.0")

app.include_router(auth_router, prefix="/api")
app.include_router(games_router, prefix="/api")
app.include_router(props_router, prefix="/api")
app.include_router(edges_router, prefix="/api")
app.include_router(players_router, prefix="/api")
app.include_router(live_router, prefix="/api")
app.include_router(health_router, prefix="/api")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
