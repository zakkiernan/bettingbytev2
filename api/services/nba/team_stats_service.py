from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.nba.team_stats import (
    LineupEntry,
    TeamDefenseProfile,
    TeamLineupsResponse,
    TeamProfileResponse,
)
from api.services.nba.stats_contracts import resolve_nba_season
from api.services.nba.team_defense_utils import (
    completed_team_games,
    normalize_opponent_points_per_game,
)
from database.models import (
    LineupStats,
    Team,
    TeamDefensiveStat,
)


def get_team_lineups(
    db: Session, team_id: str, season: str | None = None
) -> TeamLineupsResponse | None:
    season = resolve_nba_season(season)
    team = db.get(Team, team_id)
    if team is None:
        return None

    rows = db.execute(
        select(LineupStats)
        .where(LineupStats.team_id == team_id, LineupStats.season == season)
        .order_by(LineupStats.min.desc())
        .limit(15)
    ).scalars().all()

    lineups = [
        LineupEntry(
            group_id=r.group_id,
            group_name=r.group_name,
            gp=r.gp,
            min=r.min,
            off_rating=r.off_rating,
            def_rating=r.def_rating,
            net_rating=r.net_rating,
            pace=r.pace,
            ts_pct=r.ts_pct,
            efg_pct=r.efg_pct,
            plus_minus=r.plus_minus,
        )
        for r in rows
    ]

    return TeamLineupsResponse(
        team_id=team_id,
        team_abbreviation=team.abbreviation,
        season=season,
        lineups=lineups,
    )


def get_team_profile(
    db: Session, team_id: str, season: str | None = None
) -> TeamProfileResponse | None:
    season = resolve_nba_season(season)
    team = db.get(Team, team_id)
    if team is None:
        return None

    lineups_resp = get_team_lineups(db, team_id, season)
    if lineups_resp is None:
        lineups_resp = TeamLineupsResponse(
            team_id=team_id, team_abbreviation=team.abbreviation, season=season, lineups=[]
        )

    defense_row = db.execute(
        select(TeamDefensiveStat).where(
            TeamDefensiveStat.team_id == team_id,
            TeamDefensiveStat.season == season,
        )
    ).scalars().first()

    defense = None
    if defense_row:
        completed_games = completed_team_games(db, team_id, season)
        defense = TeamDefenseProfile(
            team_id=team_id,
            team_name=defense_row.team_name,
            season=season,
            defensive_rating=defense_row.defensive_rating,
            pace=defense_row.pace,
            opponent_points_per_game=normalize_opponent_points_per_game(
                defense_row.opponent_points_per_game,
                completed_games,
            ),
            opponent_field_goal_percentage=defense_row.opponent_field_goal_percentage,
            opponent_three_point_percentage=defense_row.opponent_three_point_percentage,
        )

    return TeamProfileResponse(
        team_id=team_id,
        team_abbreviation=team.abbreviation,
        team_name=team.full_name,
        lineups=lineups_resp,
        defense=defense,
    )
