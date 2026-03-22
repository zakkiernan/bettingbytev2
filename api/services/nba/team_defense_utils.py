from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database.models import Game

_HIGH_OPP_PPG_THRESHOLD = 300.0


def completed_team_games(db: Session, team_id: str | None, season: str) -> int | None:
    if not team_id:
        return None

    completed_games = db.execute(
        select(func.count(Game.game_id)).where(
            Game.season == season,
            Game.game_status == 3,
            or_(Game.home_team_id == team_id, Game.away_team_id == team_id),
        )
    ).scalar_one()

    return int(completed_games) if completed_games else None


def normalize_opponent_points_per_game(
    raw_value: float | None,
    completed_games: int | None,
) -> float | None:
    if raw_value is None:
        return None

    value = float(raw_value)
    if value <= _HIGH_OPP_PPG_THRESHOLD or not completed_games:
        return value

    return round(value / completed_games, 1)
