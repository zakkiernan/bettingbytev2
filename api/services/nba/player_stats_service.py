from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.nba.player_stats import (
    ClutchResponse,
    ClutchStatsEntry,
    DefensiveTrackingResponse,
    DefensiveZone,
    HustleStatsResponse,
    HustleStatsSeason,
    OnOffResponse,
    OnOffSplit,
    PlayTypeEntry,
    PlayTypesResponse,
    ShotChartResponse,
    ShotChartShot,
    ShotLocationsResponse,
    ShotZone,
    TrackingMeasure,
    TrackingResponse,
)
from api.services.nba.stats_contracts import normalize_court_status, resolve_nba_season
from database.models import (
    Game,
    Player,
    PlayerClutchStats,
    PlayerDefensiveTracking,
    PlayerHustleStats,
    PlayerOnOffStats,
    PlayerPlayType,
    PlayerShotLocationStats,
    PlayerTrackingStats,
    ShotChartDetail,
)


# ---------------------------------------------------------------------------
# Shot Chart
# ---------------------------------------------------------------------------


def get_player_shot_chart(
    db: Session,
    player_id: str,
    *,
    last_n: int | None = None,
    game_id: str | None = None,
) -> ShotChartResponse | None:
    player = db.get(Player, player_id)
    if player is None:
        return None

    def _ordered_shot_chart_query(query):
        return query.outerjoin(Game, Game.game_id == ShotChartDetail.game_id).order_by(
            Game.game_date.desc().nullslast(),
            Game.game_time_utc.desc().nullslast(),
            ShotChartDetail.period.asc(),
            ShotChartDetail.minutes_remaining.desc(),
            ShotChartDetail.seconds_remaining.desc(),
            ShotChartDetail.created_at.desc(),
        )

    q = select(ShotChartDetail).where(ShotChartDetail.player_id == player_id)
    if game_id:
        q = q.where(ShotChartDetail.game_id == game_id)
        rows = db.execute(_ordered_shot_chart_query(q)).scalars().all()
    elif last_n:
        recent_game_ids = db.execute(
            select(ShotChartDetail.game_id)
            .outerjoin(Game, Game.game_id == ShotChartDetail.game_id)
            .where(ShotChartDetail.player_id == player_id)
            .group_by(
                ShotChartDetail.game_id,
                Game.game_date,
                Game.game_time_utc,
            )
            .order_by(
                Game.game_date.desc().nullslast(),
                Game.game_time_utc.desc().nullslast(),
                func.max(ShotChartDetail.created_at).desc(),
            )
            .limit(last_n)
        ).scalars().all()

        if not recent_game_ids:
            rows = []
        else:
            q = q.where(ShotChartDetail.game_id.in_(recent_game_ids))
            rows = db.execute(_ordered_shot_chart_query(q)).scalars().all()
    else:
        rows = db.execute(_ordered_shot_chart_query(q)).scalars().all()

    made = sum(1 for r in rows if r.shot_made_flag)
    total = len(rows)

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

    return ShotChartResponse(
        player_id=player_id,
        player_name=player.full_name,
        total_shots=total,
        field_goal_pct=round(made / total, 4) if total > 0 else 0.0,
        shots=shots,
    )


# ---------------------------------------------------------------------------
# Shot Locations
# ---------------------------------------------------------------------------


def get_player_shot_locations(
    db: Session, player_id: str, season: str | None = None
) -> ShotLocationsResponse | None:
    season = resolve_nba_season(season)
    player = db.get(Player, player_id)
    if player is None:
        return None

    row = db.execute(
        select(PlayerShotLocationStats).where(
            PlayerShotLocationStats.player_id == player_id,
            PlayerShotLocationStats.season == season,
        )
    ).scalars().first()

    if row is None:
        return ShotLocationsResponse(
            player_id=player_id, player_name=player.full_name, season=season, zones=[]
        )

    zone_defs = [
        ("Restricted Area", row.restricted_area_fgm, row.restricted_area_fga, row.restricted_area_fg_pct),
        ("In The Paint", row.in_the_paint_fgm, row.in_the_paint_fga, row.in_the_paint_fg_pct),
        ("Mid-Range", row.mid_range_fgm, row.mid_range_fga, row.mid_range_fg_pct),
        ("Left Corner 3", row.left_corner_3_fgm, row.left_corner_3_fga, row.left_corner_3_fg_pct),
        ("Right Corner 3", row.right_corner_3_fgm, row.right_corner_3_fga, row.right_corner_3_fg_pct),
        ("Above the Break 3", row.above_the_break_3_fgm, row.above_the_break_3_fga, row.above_the_break_3_fg_pct),
        ("Backcourt", row.backcourt_fgm, row.backcourt_fga, row.backcourt_fg_pct),
    ]

    zones = [
        ShotZone(
            zone=name,
            fgm=float(fgm or 0),
            fga=float(fga or 0),
            fg_pct=float(pct or 0),
        )
        for name, fgm, fga, pct in zone_defs
        if (fga or 0) > 0
    ]

    return ShotLocationsResponse(
        player_id=player_id, player_name=player.full_name, season=season, zones=zones
    )


# ---------------------------------------------------------------------------
# Play Types
# ---------------------------------------------------------------------------


def get_player_play_types(
    db: Session, player_id: str, season: str | None = None
) -> PlayTypesResponse | None:
    season = resolve_nba_season(season)
    player = db.get(Player, player_id)
    if player is None:
        return None

    rows = db.execute(
        select(PlayerPlayType).where(
            PlayerPlayType.player_id == player_id,
            PlayerPlayType.season == season,
        )
    ).scalars().all()

    def _to_entry(r: PlayerPlayType) -> PlayTypeEntry:
        return PlayTypeEntry(
            play_type=r.play_type,
            type_grouping=r.type_grouping,
            gp=r.gp,
            poss_pct=r.poss_pct,
            ppp=r.ppp,
            fg_pct=r.fg_pct,
            ft_poss_pct=r.ft_poss_pct,
            tov_pct=r.tov_pct,
            sf_pct=r.sf_pct,
            score_pct=r.score_pct,
            efg_pct=r.efg_pct,
            poss=r.poss,
            pts=r.pts,
            percentile=r.percentile,
        )

    offensive = [_to_entry(r) for r in rows if r.type_grouping == "offensive"]
    defensive = [_to_entry(r) for r in rows if r.type_grouping == "defensive"]

    return PlayTypesResponse(
        player_id=player_id,
        player_name=player.full_name,
        season=season,
        offensive=offensive,
        defensive=defensive,
    )


# ---------------------------------------------------------------------------
# Hustle
# ---------------------------------------------------------------------------


def get_player_hustle(
    db: Session, player_id: str, season: str | None = None
) -> HustleStatsResponse | None:
    season = resolve_nba_season(season)
    player = db.get(Player, player_id)
    if player is None:
        return None

    row = db.execute(
        select(PlayerHustleStats).where(
            PlayerHustleStats.player_id == player_id,
            PlayerHustleStats.season == season,
        )
    ).scalars().first()

    season_totals = None
    if row:
        season_totals = HustleStatsSeason(
            games_played=row.games_played,
            minutes=row.minutes,
            contested_shots_2pt=row.contested_shots_2pt,
            contested_shots_3pt=row.contested_shots_3pt,
            contested_shots=row.contested_shots,
            deflections=row.deflections,
            charges_drawn=row.charges_drawn,
            screen_assists=row.screen_assists,
            screen_ast_pts=row.screen_ast_pts,
            loose_balls_recovered=row.loose_balls_recovered,
            box_outs=row.box_outs,
        )

    return HustleStatsResponse(
        player_id=player_id,
        player_name=player.full_name,
        season=season,
        season_totals=season_totals,
    )


# ---------------------------------------------------------------------------
# Tracking
# ---------------------------------------------------------------------------


def get_player_tracking(
    db: Session, player_id: str, season: str | None = None
) -> TrackingResponse | None:
    season = resolve_nba_season(season)
    player = db.get(Player, player_id)
    if player is None:
        return None

    rows = db.execute(
        select(PlayerTrackingStats).where(
            PlayerTrackingStats.player_id == player_id,
            PlayerTrackingStats.season == season,
        )
    ).scalars().all()

    measures = [
        TrackingMeasure(
            measure_type=r.measure_type,
            gp=r.gp,
            minutes=r.minutes,
            fgm=r.fgm,
            fga=r.fga,
            fg_pct=r.fg_pct,
            fg3m=r.fg3m,
            fg3a=r.fg3a,
            fg3_pct=r.fg3_pct,
            efg_pct=r.efg_pct,
            pts=r.pts,
            drives=r.drives,
            drive_fgm=r.drive_fgm,
            drive_fga=r.drive_fga,
            drive_fg_pct=r.drive_fg_pct,
            drive_ftm=r.drive_ftm,
            drive_fta=r.drive_fta,
            drive_ft_pct=r.drive_ft_pct,
            drive_pts=r.drive_pts,
            drive_ast=r.drive_ast,
            drive_tov=r.drive_tov,
        )
        for r in rows
    ]

    return TrackingResponse(
        player_id=player_id,
        player_name=player.full_name,
        season=season,
        measures=measures,
    )


# ---------------------------------------------------------------------------
# Defensive Tracking
# ---------------------------------------------------------------------------


def get_player_defense(
    db: Session, player_id: str, season: str | None = None
) -> DefensiveTrackingResponse | None:
    season = resolve_nba_season(season)
    player = db.get(Player, player_id)
    if player is None:
        return None

    rows = db.execute(
        select(PlayerDefensiveTracking).where(
            PlayerDefensiveTracking.player_id == player_id,
            PlayerDefensiveTracking.season == season,
        )
    ).scalars().all()

    zones = [
        DefensiveZone(
            defense_category=r.defense_category,
            gp=r.gp,
            freq=r.freq,
            d_fgm=r.d_fgm,
            d_fga=r.d_fga,
            d_fg_pct=r.d_fg_pct,
            normal_fg_pct=r.normal_fg_pct,
            pct_plusminus=r.pct_plusminus,
        )
        for r in rows
    ]

    return DefensiveTrackingResponse(
        player_id=player_id,
        player_name=player.full_name,
        season=season,
        zones=zones,
    )


# ---------------------------------------------------------------------------
# On/Off
# ---------------------------------------------------------------------------


def get_player_on_off(
    db: Session, player_id: str, season: str | None = None
) -> OnOffResponse | None:
    season = resolve_nba_season(season)
    player = db.get(Player, player_id)
    if player is None:
        return None

    rows = db.execute(
        select(PlayerOnOffStats).where(
            PlayerOnOffStats.player_id == player_id,
            PlayerOnOffStats.season == season,
        )
    ).scalars().all()

    splits = [
        OnOffSplit(
            court_status=normalize_court_status(r.court_status),
            gp=r.gp,
            min=r.min,
            off_rating=r.off_rating,
            def_rating=r.def_rating,
            net_rating=r.net_rating,
            ast_pct=r.ast_pct,
            ast_to=r.ast_to,
            oreb_pct=r.oreb_pct,
            dreb_pct=r.dreb_pct,
            reb_pct=r.reb_pct,
            tov_pct=r.tov_pct,
            efg_pct=r.efg_pct,
            ts_pct=r.ts_pct,
            pace=r.pace,
            pie=r.pie,
            plus_minus=r.plus_minus,
        )
        for r in rows
    ]

    return OnOffResponse(
        player_id=player_id,
        player_name=player.full_name,
        season=season,
        splits=splits,
    )


# ---------------------------------------------------------------------------
# Clutch
# ---------------------------------------------------------------------------


def get_player_clutch(
    db: Session, player_id: str, season: str | None = None
) -> ClutchResponse | None:
    season = resolve_nba_season(season)
    player = db.get(Player, player_id)
    if player is None:
        return None

    rows = db.execute(
        select(PlayerClutchStats).where(
            PlayerClutchStats.player_id == player_id,
            PlayerClutchStats.season == season,
        )
    ).scalars().all()

    entries = [
        ClutchStatsEntry(
            clutch_time=r.clutch_time,
            point_diff=r.point_diff,
            gp=r.gp,
            w=r.w,
            l=r.l,
            min=r.min,
            fgm=r.fgm,
            fga=r.fga,
            fg_pct=r.fg_pct,
            fg3m=r.fg3m,
            fg3a=r.fg3a,
            fg3_pct=r.fg3_pct,
            ftm=r.ftm,
            fta=r.fta,
            ft_pct=r.ft_pct,
            reb=r.reb,
            ast=r.ast,
            tov=r.tov,
            stl=r.stl,
            blk=r.blk,
            pts=r.pts,
            plus_minus=r.plus_minus,
        )
        for r in rows
    ]

    return ClutchResponse(
        player_id=player_id,
        player_name=player.full_name,
        season=season,
        entries=entries,
    )
