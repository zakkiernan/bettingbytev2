from api.routes.auth import router as auth_router
from api.routes.edges import router as edges_router
from api.routes.games import router as games_router
from api.routes.health import router as health_router
from api.routes.live import router as live_router
from api.routes.players import router as players_router
from api.routes.props import router as props_router

__all__ = [
    "auth_router",
    "edges_router",
    "games_router",
    "health_router",
    "live_router",
    "players_router",
    "props_router",
]
