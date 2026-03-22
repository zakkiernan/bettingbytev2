from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.board import PropBoardRow
from api.schemas.detail import GameLogEntry
from api.schemas.players import PlayerProfileResponse, SeasonAverages, SignalHistoryEntry, TrendPoint
from api.services.nba.stats_contracts import nba_season_start, resolve_nba_season
from api.services import stats_signal_service
from database.models import (
    Game,
    HistoricalGameLog,
    Player,
    Team,
)


def _today_window() -> tuple[datetime, datetime]:
    today = date.today()
    start = datetime(today.year, today.month, today.day, 0, 0, 0)
    end = start + timedelta(days=1)
    return start, end


def _compute_season_averages(logs: list[HistoricalGameLog]) -> SeasonAverages:
    """Compute per-game averages from a list of game log rows."""
    played = [row for row in logs if row.minutes and row.minutes > 0]
    if not played:
        return SeasonAverages()

    n = len(played)

    def _avg(attr: str) -> float:
        vals = [float(getattr(row, attr) or 0.0) for row in played]
        return round(sum(vals) / n, 3) if vals else 0.0

    def _pct(made_attr: str, att_attr: str) -> float:
        made = sum(float(getattr(r, made_attr) or 0.0) for r in played)
        att = sum(float(getattr(r, att_attr) or 0.0) for r in played)
        return round(made / att, 4) if att > 0 else 0.0

    ppg = _avg("points")
    rpg = _avg("rebounds")
    apg = _avg("assists")
    mpg = _avg("minutes")
    fg_pct = _pct("field_goals_made", "field_goals_attempted")
    ft_pct = _pct("free_throws_made", "free_throws_attempted")

    # TS% = points / (2 * (FGA + 0.44 * FTA))
    total_pts = sum(float(r.points or 0.0) for r in played)
    total_fga = sum(float(r.field_goals_attempted or 0.0) for r in played)
    total_fta = sum(float(r.free_throws_attempted or 0.0) for r in played)
    ts_denom = 2 * (total_fga + 0.44 * total_fta)
    ts_pct = round(total_pts / ts_denom, 4) if ts_denom > 0 else 0.0

    return SeasonAverages(
        games_played=n,
        ppg=ppg,
        rpg=rpg,
        apg=apg,
        mpg=mpg,
        fg_pct=fg_pct,
        ft_pct=ft_pct,
        ts_pct=ts_pct,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_player_profile(db: Session, player_id: str) -> PlayerProfileResponse | None:
    """Return a player profile with season averages and tonight's active props."""
    player = db.get(Player, player_id)
    if player is None:
        return None

    season_start = nba_season_start(resolve_nba_season())
    logs = (
        db.execute(
            select(HistoricalGameLog)
            .where(
                HistoricalGameLog.player_id == player_id,
                HistoricalGameLog.game_date >= season_start,
            )
            .order_by(HistoricalGameLog.game_date.desc())
        )
        .scalars()
        .all()
    )
    season_averages = _compute_season_averages(logs)

    # Team from most recent log
    team_abbr = logs[0].team if logs else "???"
    team_full_name = team_abbr
    team_row = (
        db.execute(
            select(Team).where(Team.abbreviation == team_abbr)
        )
        .scalars()
        .first()
    )
    if team_row:
        team_full_name = team_row.full_name

    # Tonight's active props
    start, end = _today_window()
    today_game_id_rows = db.execute(
        select(Game.game_id).where(
            Game.game_date >= start,
            Game.game_date < end,
        )
    ).all()
    today_game_ids = [row[0] for row in today_game_id_rows]

    active_props: list[PropBoardRow] = []
    if today_game_ids:
        active_props = stats_signal_service.get_active_prop_rows_for_player(db, player_id)

    return PlayerProfileResponse(
        player_id=player.player_id,
        full_name=player.full_name,
        first_name=player.first_name,
        last_name=player.last_name,
        team_abbreviation=team_abbr,
        team_full_name=team_full_name,
        season_averages=season_averages,
        active_props=active_props,
    )


def get_player_game_log(
    db: Session,
    player_id: str,
    limit: int = 10,
) -> list[GameLogEntry]:
    """Return the most recent game log entries for a player."""
    rows = (
        db.execute(
            select(HistoricalGameLog)
            .where(HistoricalGameLog.player_id == player_id)
            .order_by(HistoricalGameLog.game_date.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        GameLogEntry(
            game_id=row.game_id,
            game_date=row.game_date,
            opponent=row.opponent,
            is_home=row.is_home,
            minutes=float(row.minutes or 0.0),
            points=float(row.points or 0.0),
            rebounds=float(row.rebounds or 0.0),
            assists=float(row.assists or 0.0),
            steals=float(row.steals or 0.0),
            blocks=float(row.blocks or 0.0),
            turnovers=float(row.turnovers or 0.0),
            threes_made=float(row.threes_made or 0.0),
            field_goals_made=float(row.field_goals_made or 0.0),
            field_goals_attempted=float(row.field_goals_attempted or 0.0),
            free_throws_made=float(row.free_throws_made or 0.0),
            free_throws_attempted=float(row.free_throws_attempted or 0.0),
            plus_minus=float(row.plus_minus or 0.0),
        )
        for row in rows
    ]


def get_player_trends(
    db: Session,
    player_id: str,
    stat_type: str = "points",
    limit: int = 20,
) -> list[TrendPoint]:
    """Return per-game stat values with the line at time of play (if available).

    Matches each historical game log to the latest saved pregame market line for
    that game when historical odds coverage exists.
    """
    logs = (
        db.execute(
            select(HistoricalGameLog)
            .where(HistoricalGameLog.player_id == player_id)
            .order_by(HistoricalGameLog.game_date.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )

    if not logs:
        return []

    game_ids = [row.game_id for row in logs]
    signal_lines = stats_signal_service.get_historical_pregame_lines(
        db,
        player_id=player_id,
        stat_type=stat_type,
        game_ids=game_ids,
    )

    stat_attr = {
        "points": "points",
        "rebounds": "rebounds",
        "assists": "assists",
    }.get(stat_type, "points")

    return [
        TrendPoint(
            game_date=row.game_date,
            value=float(getattr(row, stat_attr) or 0.0),
            line=signal_lines.get(row.game_id),
            hit=(
                (float(getattr(row, stat_attr) or 0.0) > signal_lines[row.game_id])
                if row.game_id in signal_lines
                else None
            ),
        )
        for row in logs
    ]


def get_player_signal_history(
    db: Session,
    player_id: str,
    stat_type: str = "points",
    limit: int = 20,
) -> list[SignalHistoryEntry]:
    return stats_signal_service.get_player_signal_history(
        db,
        player_id=player_id,
        stat_type=stat_type,
        limit=limit,
    )
