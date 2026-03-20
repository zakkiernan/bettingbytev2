from api.routes.audit import router as audit_router
from api.routes.auth import router as auth_router
from api.routes.health import router as health_router
from api.routes.nba.edges import router as nba_edges_router
from api.routes.nba.games import router as nba_games_router
from api.routes.nba.live import router as nba_live_router
from api.routes.nba.players import router as nba_players_router
from api.routes.nba.props import router as nba_props_router

edges_router = nba_edges_router
games_router = nba_games_router
live_router = nba_live_router
players_router = nba_players_router
props_router = nba_props_router

__all__ = [
    "auth_router",
    "audit_router",
    "health_router",
    "nba_edges_router",
    "nba_games_router",
    "nba_live_router",
    "nba_players_router",
    "nba_props_router",
    "edges_router",
    "games_router",
    "live_router",
    "players_router",
    "props_router",
]
