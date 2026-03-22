from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.games import GameDetailResponse, GameResponse, TeamBrief
from api.services import stats_signal_service
from database.models import Game, Team

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UNKNOWN_TEAM = TeamBrief(
    team_id="",
    abbreviation="???",
    full_name="Unknown",
)


def _today_window() -> tuple[datetime, datetime]:
    """Return [start, end) UTC datetimes covering today's NBA slate.

    NBA games span roughly 17:00–03:00 UTC.  Using a 24-hour window anchored
    to today's date is sufficient for the internal dashboard.
    """
    today = date.today()
    start = datetime(today.year, today.month, today.day, 0, 0, 0)
    end = start + timedelta(days=1)
    return start, end


def _team_brief(team: Team | None) -> TeamBrief:
    if team is None:
        return _UNKNOWN_TEAM
    return TeamBrief(
        team_id=team.team_id,
        abbreviation=team.abbreviation,
        full_name=team.full_name,
        city=team.city,
        nickname=team.nickname,
    )

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_games_today(db: Session, *, limit: int = 50, offset: int = 0) -> list[GameDetailResponse]:
    """Return all games scheduled for today with prop/edge counts."""
    start, end = _today_window()

    games = (
        db.execute(
            select(Game)
            .where(
                Game.game_date >= start,
                Game.game_date < end,
            )
            .order_by(Game.game_time_utc.asc(), Game.game_id.asc())
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )

    if not games:
        return []

    # Batch-load teams to avoid N+1 queries
    team_ids = {g.home_team_id for g in games} | {g.away_team_id for g in games}
    team_ids.discard(None)
    teams_by_id: dict[str, Team] = {}
    if team_ids:
        teams_by_id = {
            t.team_id: t
            for t in db.execute(
                select(Team).where(Team.team_id.in_(team_ids))
            ).scalars().all()
        }

    game_ids = [g.game_id for g in games]
    counts = stats_signal_service.get_prop_counts_by_game(db, game_ids)

    results: list[GameDetailResponse] = []
    for game in sorted(games, key=lambda g: g.game_time_utc or datetime.max):
        prop_count, edge_count = counts.get(game.game_id, (0, 0))
        results.append(
            GameDetailResponse(
                game_id=game.game_id,
                season=game.season,
                game_date=game.game_date,
                game_time_utc=game.game_time_utc,
                home_team=_team_brief(teams_by_id.get(game.home_team_id or "")),
                away_team=_team_brief(teams_by_id.get(game.away_team_id or "")),
                game_status=game.game_status,
                status_text=game.status_text,
                prop_count=prop_count,
                edge_count=edge_count,
            )
        )

    return results


def get_game_detail(db: Session, game_id: str) -> GameDetailResponse | None:
    """Return a single game by ID, or None if not found."""
    game = db.get(Game, game_id)
    if game is None:
        return None

    teams_by_id: dict[str, Team] = {}
    team_ids = {game.home_team_id, game.away_team_id} - {None}
    if team_ids:
        teams_by_id = {
            t.team_id: t
            for t in db.execute(
                select(Team).where(Team.team_id.in_(team_ids))
            ).scalars().all()
        }

    counts = stats_signal_service.get_prop_counts_by_game(db, [game_id])
    prop_count, edge_count = counts.get(game_id, (0, 0))

    return GameDetailResponse(
        game_id=game.game_id,
        season=game.season,
        game_date=game.game_date,
        game_time_utc=game.game_time_utc,
        home_team=_team_brief(teams_by_id.get(game.home_team_id or "")),
        away_team=_team_brief(teams_by_id.get(game.away_team_id or "")),
        game_status=game.game_status,
        status_text=game.status_text,
        prop_count=prop_count,
        edge_count=edge_count,
    )
