from __future__ import annotations

from typing import Literal

from api.schemas.base import APIModel


# ---------------------------------------------------------------------------
# Shot Chart
# ---------------------------------------------------------------------------

class ShotChartShot(APIModel):
    game_id: str
    loc_x: float
    loc_y: float
    shot_made: bool
    shot_type: str | None = None
    action_type: str | None = None
    shot_zone_basic: str | None = None
    shot_zone_area: str | None = None
    shot_zone_range: str | None = None
    shot_distance: float | None = None
    period: int | None = None
    minutes_remaining: int | None = None
    seconds_remaining: int | None = None


class ShotChartResponse(APIModel):
    player_id: str
    player_name: str
    total_shots: int
    field_goal_pct: float
    shots: list[ShotChartShot]


# ---------------------------------------------------------------------------
# Shot Locations (Zone Aggregates)
# ---------------------------------------------------------------------------

class ShotZone(APIModel):
    zone: str
    fgm: float
    fga: float
    fg_pct: float


class ShotLocationsResponse(APIModel):
    player_id: str
    player_name: str
    season: str
    zones: list[ShotZone]


# ---------------------------------------------------------------------------
# Play Types (Synergy)
# ---------------------------------------------------------------------------

class PlayTypeEntry(APIModel):
    play_type: str
    type_grouping: str
    gp: int | None = None
    poss_pct: float | None = None
    ppp: float | None = None
    fg_pct: float | None = None
    ft_poss_pct: float | None = None
    tov_pct: float | None = None
    sf_pct: float | None = None
    score_pct: float | None = None
    efg_pct: float | None = None
    poss: float | None = None
    pts: float | None = None
    percentile: float | None = None


class PlayTypesResponse(APIModel):
    player_id: str
    player_name: str
    season: str
    offensive: list[PlayTypeEntry]
    defensive: list[PlayTypeEntry]


# ---------------------------------------------------------------------------
# Hustle Stats
# ---------------------------------------------------------------------------

class HustleStatsSeason(APIModel):
    games_played: int | None = None
    minutes: float | None = None
    contested_shots_2pt: float | None = None
    contested_shots_3pt: float | None = None
    contested_shots: float | None = None
    deflections: float | None = None
    charges_drawn: float | None = None
    screen_assists: float | None = None
    screen_ast_pts: float | None = None
    loose_balls_recovered: float | None = None
    box_outs: float | None = None


class HustleStatsResponse(APIModel):
    player_id: str
    player_name: str
    season: str
    season_totals: HustleStatsSeason | None = None


# ---------------------------------------------------------------------------
# Tracking Stats
# ---------------------------------------------------------------------------

class TrackingMeasure(APIModel):
    measure_type: str
    gp: int | None = None
    minutes: float | None = None
    fgm: float | None = None
    fga: float | None = None
    fg_pct: float | None = None
    fg3m: float | None = None
    fg3a: float | None = None
    fg3_pct: float | None = None
    efg_pct: float | None = None
    pts: float | None = None
    drives: float | None = None
    drive_fgm: float | None = None
    drive_fga: float | None = None
    drive_fg_pct: float | None = None
    drive_ftm: float | None = None
    drive_fta: float | None = None
    drive_ft_pct: float | None = None
    drive_pts: float | None = None
    drive_ast: float | None = None
    drive_tov: float | None = None


class TrackingResponse(APIModel):
    player_id: str
    player_name: str
    season: str
    measures: list[TrackingMeasure]


# ---------------------------------------------------------------------------
# Defensive Tracking
# ---------------------------------------------------------------------------

class DefensiveZone(APIModel):
    defense_category: str
    gp: int | None = None
    freq: float | None = None
    d_fgm: float | None = None
    d_fga: float | None = None
    d_fg_pct: float | None = None
    normal_fg_pct: float | None = None
    pct_plusminus: float | None = None


class DefensiveTrackingResponse(APIModel):
    player_id: str
    player_name: str
    season: str
    zones: list[DefensiveZone]


# ---------------------------------------------------------------------------
# On/Off Court
# ---------------------------------------------------------------------------

class OnOffSplit(APIModel):
    court_status: Literal["on", "off"]
    gp: int | None = None
    min: float | None = None
    off_rating: float | None = None
    def_rating: float | None = None
    net_rating: float | None = None
    ast_pct: float | None = None
    ast_to: float | None = None
    oreb_pct: float | None = None
    dreb_pct: float | None = None
    reb_pct: float | None = None
    tov_pct: float | None = None
    efg_pct: float | None = None
    ts_pct: float | None = None
    pace: float | None = None
    pie: float | None = None
    plus_minus: float | None = None


class OnOffResponse(APIModel):
    player_id: str
    player_name: str
    season: str
    splits: list[OnOffSplit]


# ---------------------------------------------------------------------------
# Clutch Stats
# ---------------------------------------------------------------------------

class ClutchStatsEntry(APIModel):
    clutch_time: str
    point_diff: int
    gp: int | None = None
    w: int | None = None
    l: int | None = None
    min: float | None = None
    fgm: float | None = None
    fga: float | None = None
    fg_pct: float | None = None
    fg3m: float | None = None
    fg3a: float | None = None
    fg3_pct: float | None = None
    ftm: float | None = None
    fta: float | None = None
    ft_pct: float | None = None
    reb: float | None = None
    ast: float | None = None
    tov: float | None = None
    stl: float | None = None
    blk: float | None = None
    pts: float | None = None
    plus_minus: float | None = None


class ClutchResponse(APIModel):
    player_id: str
    player_name: str
    season: str
    entries: list[ClutchStatsEntry]
