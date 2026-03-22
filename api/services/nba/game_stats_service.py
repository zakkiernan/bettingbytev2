from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.nba.game_stats import (
    GameHustleResponse,
    GameHustleRow,
    GameMatchup,
    GameMatchupsResponse,
    GameShotChartResponse,
    WinProbPoint,
    WinProbResponse,
)
from api.schemas.nba.player_stats import ShotChartShot
from api.services.nba.stats_contracts import as_percentage_points
from database.models import (
    Game,
    HustleStatsBoxscore,
    MatchupBoxscore,
    ShotChartDetail,
    WinProbabilityEntry,
)


def get_game_matchups(db: Session, game_id: str) -> GameMatchupsResponse | None:
    game = db.get(Game, game_id)
    if game is None:
        return None

    rows = db.execute(
        select(MatchupBoxscore)
        .where(MatchupBoxscore.game_id == game_id)
        .order_by(MatchupBoxscore.matchup_minutes_sort.desc())
    ).scalars().all()

    matchups = [
        GameMatchup(
            offense_player_id=r.offense_player_id,
            offense_player_name=r.offense_player_name,
            defense_player_id=r.defense_player_id,
            defense_player_name=r.defense_player_name,
            matchup_minutes=float(r.matchup_minutes or 0),
            partial_possessions=r.partial_possessions,
            player_points=r.player_points,
            switches_on=r.switches_on,
            matchup_field_goals_made=r.matchup_field_goals_made,
            matchup_field_goals_attempted=r.matchup_field_goals_attempted,
            matchup_field_goal_percentage=r.matchup_field_goal_percentage,
            matchup_assists=r.matchup_assists,
            matchup_turnovers=r.matchup_turnovers,
        )
        for r in rows
    ]

    return GameMatchupsResponse(game_id=game_id, matchups=matchups)


def get_game_win_probability(db: Session, game_id: str) -> WinProbResponse | None:
    game = db.get(Game, game_id)
    if game is None:
        return None

    rows = db.execute(
        select(WinProbabilityEntry)
        .where(WinProbabilityEntry.game_id == game_id)
        .order_by(WinProbabilityEntry.event_num.asc())
    ).scalars().all()

    points = [
        WinProbPoint(
            event_num=r.event_num,
            home_pct=as_percentage_points(r.home_pct, default=50.0),
            visitor_pct=as_percentage_points(r.visitor_pct, default=50.0),
            home_pts=r.home_pts or 0,
            visitor_pts=r.visitor_pts or 0,
            period=r.period or 1,
            seconds_remaining=float(r.seconds_remaining or 0),
            description=r.home_description or r.visitor_description or r.neutral_description,
        )
        for r in rows
    ]

    return WinProbResponse(game_id=game_id, points=points)


def get_game_hustle(db: Session, game_id: str) -> GameHustleResponse | None:
    game = db.get(Game, game_id)
    if game is None:
        return None

    rows = db.execute(
        select(HustleStatsBoxscore)
        .where(HustleStatsBoxscore.game_id == game_id)
        .order_by(HustleStatsBoxscore.minutes.desc())
    ).scalars().all()

    players = [
        GameHustleRow(
            player_id=r.player_id,
            player_name=r.player_name,
            team_id=r.team_id,
            minutes=r.minutes,
            contested_shots=r.contested_shots,
            contested_shots_2pt=r.contested_shots_2pt,
            contested_shots_3pt=r.contested_shots_3pt,
            deflections=r.deflections,
            charges_drawn=r.charges_drawn,
            screen_assists=r.screen_assists,
            loose_balls_recovered=r.loose_balls_recovered,
            box_outs=r.box_outs,
        )
        for r in rows
    ]

    return GameHustleResponse(game_id=game_id, players=players)


def get_game_shot_chart(db: Session, game_id: str) -> GameShotChartResponse | None:
    game = db.get(Game, game_id)
    if game is None:
        return None

    rows = db.execute(
        select(ShotChartDetail)
        .where(ShotChartDetail.game_id == game_id)
        .order_by(ShotChartDetail.period.asc(), ShotChartDetail.minutes_remaining.desc())
    ).scalars().all()

    shots = [
        ShotChartShot(
            game_id=r.game_id,
            loc_x=float(r.loc_x or 0),
            loc_y=float(r.loc_y or 0),
            shot_made=bool(r.shot_made_flag),
            shot_type=r.shot_type,
            action_type=r.action_type,
            shot_zone_basic=r.shot_zone_basic,
            shot_zone_area=r.shot_zone_area,
            shot_zone_range=r.shot_zone_range,
            shot_distance=float(r.shot_distance) if r.shot_distance is not None else None,
            period=r.period,
            minutes_remaining=r.minutes_remaining,
            seconds_remaining=r.seconds_remaining,
        )
        for r in rows
    ]

    return GameShotChartResponse(game_id=game_id, total_shots=len(shots), shots=shots)
