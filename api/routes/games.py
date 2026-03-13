from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from api.schemas import GameDetailResponse, GameResponse, TeamBrief

router = APIRouter(prefix="/games", tags=["games"])


LAKERS = TeamBrief(team_id="1610612747", abbreviation="LAL", full_name="Los Angeles Lakers", city="Los Angeles", nickname="Lakers")
MAVERICKS = TeamBrief(team_id="1610612742", abbreviation="DAL", full_name="Dallas Mavericks", city="Dallas", nickname="Mavericks")

GAME = GameDetailResponse(
    game_id="0022500001",
    season="2025-26",
    game_date=datetime(2026, 3, 13, 0, 0, tzinfo=timezone.utc),
    game_time_utc=datetime(2026, 3, 13, 23, 30, tzinfo=timezone.utc),
    home_team=MAVERICKS,
    away_team=LAKERS,
    game_status=1,
    status_text="7:30 PM ET",
    home_team_score=None,
    away_team_score=None,
    period=None,
    game_clock=None,
    prop_count=0,
    edge_count=0,
)


@router.get("/today", response_model=list[GameResponse])
def get_games_today() -> list[GameResponse]:
    return [GAME]


@router.get("/{game_id}", response_model=GameDetailResponse)
def get_game_detail(game_id: str) -> GameDetailResponse:
    return GAME.model_copy(update={"game_id": game_id})
