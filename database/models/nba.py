from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.db import Base


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        Index("ix_team_abbreviation", "abbreviation"),
    )

    team_id: Mapped[str] = mapped_column(String, primary_key=True)
    abbreviation: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    nickname: Mapped[str | None] = mapped_column(String, nullable=True)
    conference: Mapped[str | None] = mapped_column(String, nullable=True)
    division: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (
        Index("ix_player_full_name", "full_name"),
    )

    player_id: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    first_name: Mapped[str | None] = mapped_column(String, nullable=True)
    last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        Index("ix_games_season_date", "season", "game_date"),
        Index("ix_games_status_date", "game_status", "game_date"),
    )

    game_id: Mapped[str] = mapped_column(String, primary_key=True)
    season: Mapped[str | None] = mapped_column(String, nullable=True)
    game_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    home_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.team_id"), nullable=True)
    away_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.team_id"), nullable=True)
    home_team_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True)
    away_team_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True)
    game_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status_text: Mapped[str | None] = mapped_column(String, nullable=True)
    game_time_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_in_season_tournament: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class SourcePayload(Base):
    __tablename__ = "source_payloads"
    __table_args__ = (
        Index("ix_source_payload_lookup", "source", "payload_type", "captured_at"),
        Index("ix_source_payload_external", "source", "external_id", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    payload_type: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    context_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PlayerPropSnapshot(Base):
    __tablename__ = "player_prop_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "player_id",
            "stat_type",
            "is_live",
            "snapshot_phase",
            name="uq_player_prop_snapshot_market_phase",
        ),
        Index("ix_player_prop_snapshot_lookup", "game_id", "player_id", "stat_type", "is_live", "snapshot_phase"),
        Index("ix_player_prop_snapshot_stat_live_capture", "stat_type", "is_live", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    team: Mapped[str | None] = mapped_column(String, nullable=True)
    opponent: Mapped[str | None] = mapped_column(String, nullable=True)
    stat_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    line: Mapped[float] = mapped_column(Float, nullable=False)
    over_odds: Mapped[int] = mapped_column(Integer, nullable=False)
    under_odds: Mapped[int] = mapped_column(Integer, nullable=False)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    snapshot_phase: Mapped[str] = mapped_column(String, default="current", nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"
    __table_args__ = (
        Index("ix_odds_snapshot_lookup", "game_id", "player_id", "stat_type", "captured_at"),
        Index("ix_odds_snapshot_phase_stat_capture", "market_phase", "stat_type", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    stat_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    line: Mapped[float] = mapped_column(Float, nullable=False)
    over_odds: Mapped[int] = mapped_column(Integer, nullable=False)
    under_odds: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String, default="fanduel", nullable=False)
    market_phase: Mapped[str] = mapped_column(String, default="pregame", nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class HistoricalGameLog(Base):
    __tablename__ = "historical_game_logs"
    __table_args__ = (
        UniqueConstraint("game_id", "player_id", name="uq_historical_game_log_player_game"),
        Index("ix_historical_game_log_player_date", "player_id", "game_date"),
        Index("ix_historical_game_log_team_date", "team", "game_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    game_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    team: Mapped[str] = mapped_column(String, nullable=False)
    opponent: Mapped[str] = mapped_column(String, nullable=False)
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False)
    minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    points: Mapped[float | None] = mapped_column(Float, nullable=True)
    rebounds: Mapped[float | None] = mapped_column(Float, nullable=True)
    assists: Mapped[float | None] = mapped_column(Float, nullable=True)
    steals: Mapped[float | None] = mapped_column(Float, nullable=True)
    blocks: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnovers: Mapped[float | None] = mapped_column(Float, nullable=True)
    threes_made: Mapped[float | None] = mapped_column(Float, nullable=True)
    threes_attempted: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_goals_made: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_goals_attempted: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_throws_made: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_throws_attempted: Mapped[float | None] = mapped_column(Float, nullable=True)
    plus_minus: Mapped[float | None] = mapped_column(Float, nullable=True)
    fantasy_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class HistoricalAdvancedLog(Base):
    __tablename__ = "historical_advanced_logs"
    __table_args__ = (
        UniqueConstraint("game_id", "player_id", name="uq_historical_advanced_player_game"),
        Index("ix_historical_advanced_player_game", "player_id", "game_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str | None] = mapped_column(String, nullable=True)

    usage_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_usage_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    pace: Mapped[float | None] = mapped_column(Float, nullable=True)
    pace_per40: Mapped[float | None] = mapped_column(Float, nullable=True)
    possessions: Mapped[float | None] = mapped_column(Float, nullable=True)
    offensive_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    defensive_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    true_shooting_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    effective_field_goal_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    assist_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    assist_to_turnover: Mapped[float | None] = mapped_column(Float, nullable=True)
    offensive_rebound_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    defensive_rebound_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    pie: Mapped[float | None] = mapped_column(Float, nullable=True)

    speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    touches: Mapped[float | None] = mapped_column(Float, nullable=True)
    passes: Mapped[float | None] = mapped_column(Float, nullable=True)
    secondary_assists: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_throw_assists: Mapped[float | None] = mapped_column(Float, nullable=True)
    rebound_chances_offensive: Mapped[float | None] = mapped_column(Float, nullable=True)
    rebound_chances_defensive: Mapped[float | None] = mapped_column(Float, nullable=True)
    rebound_chances_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    contested_field_goals_made: Mapped[float | None] = mapped_column(Float, nullable=True)
    contested_field_goals_attempted: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncontested_field_goals_made: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncontested_field_goals_attempted: Mapped[float | None] = mapped_column(Float, nullable=True)
    defended_at_rim_field_goals_made: Mapped[float | None] = mapped_column(Float, nullable=True)
    defended_at_rim_field_goals_attempted: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class TeamRotationGame(Base):
    __tablename__ = "team_rotation_games"
    __table_args__ = (
        UniqueConstraint("game_id", "team_id", name="uq_team_rotation_game"),
        Index("ix_team_rotation_game_lookup", "game_id", "team_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True)
    team_name: Mapped[str | None] = mapped_column(String, nullable=True)
    rotation_player_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starter_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    closing_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_stints: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_out_time_real: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_shift_duration_real: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PlayerRotationGame(Base):
    __tablename__ = "player_rotation_games"
    __table_args__ = (
        UniqueConstraint("game_id", "player_id", name="uq_player_rotation_game"),
        Index("ix_player_rotation_game_lookup", "game_id", "player_id"),
        Index("ix_player_rotation_game_team", "team_id", "game_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True)
    team_name: Mapped[str | None] = mapped_column(String, nullable=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    started: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    played_opening_stint: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    closed_game: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stint_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_in_time_real: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_out_time_real: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_shift_duration_real: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_shift_duration_real: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PlayerRotationStint(Base):
    __tablename__ = "player_rotation_stints"
    __table_args__ = (
        UniqueConstraint("game_id", "player_id", "stint_number", name="uq_player_rotation_stint"),
        Index("ix_player_rotation_stint_lookup", "game_id", "player_id", "stint_number"),
        Index("ix_player_rotation_stint_team", "team_id", "game_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True)
    team_name: Mapped[str | None] = mapped_column(String, nullable=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    stint_number: Mapped[int] = mapped_column(Integer, nullable=False)
    in_time_real: Mapped[float | None] = mapped_column(Float, nullable=True)
    out_time_real: Mapped[float | None] = mapped_column(Float, nullable=True)
    shift_duration_real: Mapped[float | None] = mapped_column(Float, nullable=True)
    player_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    point_differential: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class TeamDefensiveStat(Base):
    __tablename__ = "team_defensive_stats"
    __table_args__ = (
        UniqueConstraint("team_id", "season", name="uq_team_defensive_stat_team_season"),
        Index("ix_team_defensive_stat_season", "season", "team_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_name: Mapped[str] = mapped_column(String, nullable=False)
    season: Mapped[str] = mapped_column(String, nullable=False)

    defensive_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_defensive_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    pace: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_pace: Mapped[float | None] = mapped_column(Float, nullable=True)
    opponent_points_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)
    opponent_field_goal_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    opponent_three_point_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)

    d_fg_pct_overall: Mapped[float | None] = mapped_column(Float, nullable=True)
    defended_field_goal_attempts: Mapped[float | None] = mapped_column(Float, nullable=True)
    normal_fg_pct_overall: Mapped[float | None] = mapped_column(Float, nullable=True)
    d_pct_plusminus_overall: Mapped[float | None] = mapped_column(Float, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class ShotChartDetail(Base):
    __tablename__ = "shot_chart_details"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "player_id",
            "period",
            "minutes_remaining",
            "seconds_remaining",
            "loc_x",
            "loc_y",
            name="uq_shot_chart_detail_event_location",
        ),
        Index("ix_shot_chart_detail_game_player", "game_id", "player_id"),
        Index("ix_shot_chart_detail_game_zone", "game_id", "shot_zone_basic"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    team_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_type: Mapped[str | None] = mapped_column(String, nullable=True)
    action_type: Mapped[str | None] = mapped_column(String, nullable=True)
    shot_type: Mapped[str | None] = mapped_column(String, nullable=True)
    shot_zone_basic: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    shot_zone_area: Mapped[str | None] = mapped_column(String, nullable=True)
    shot_zone_range: Mapped[str | None] = mapped_column(String, nullable=True)
    shot_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    loc_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    loc_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    shot_made_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minutes_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seconds_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    htm: Mapped[str | None] = mapped_column(String, nullable=True)
    vtm: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class HustleStatsBoxscore(Base):
    __tablename__ = "hustle_stats_boxscores"
    __table_args__ = (
        UniqueConstraint("game_id", "player_id", name="uq_hustle_stats_boxscore_game_player"),
        Index("ix_hustle_stats_boxscore_player_game", "player_id", "game_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    team_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    contested_shots_2pt: Mapped[float | None] = mapped_column(Float, nullable=True)
    contested_shots_3pt: Mapped[float | None] = mapped_column(Float, nullable=True)
    contested_shots: Mapped[float | None] = mapped_column(Float, nullable=True)
    deflections: Mapped[float | None] = mapped_column(Float, nullable=True)
    charges_drawn: Mapped[float | None] = mapped_column(Float, nullable=True)
    screen_assists: Mapped[float | None] = mapped_column(Float, nullable=True)
    screen_ast_pts: Mapped[float | None] = mapped_column(Float, nullable=True)
    loose_balls_recovered_offensive: Mapped[float | None] = mapped_column(Float, nullable=True)
    loose_balls_recovered_defensive: Mapped[float | None] = mapped_column(Float, nullable=True)
    loose_balls_recovered: Mapped[float | None] = mapped_column(Float, nullable=True)
    box_outs_offensive: Mapped[float | None] = mapped_column(Float, nullable=True)
    box_outs_defensive: Mapped[float | None] = mapped_column(Float, nullable=True)
    box_outs: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class MatchupBoxscore(Base):
    __tablename__ = "matchup_boxscores"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "offense_player_id",
            "defense_player_id",
            name="uq_matchup_boxscore_game_players",
        ),
        Index("ix_matchup_boxscore_game_offense", "game_id", "offense_player_id"),
        Index("ix_matchup_boxscore_game_defense", "game_id", "defense_player_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    offense_player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    offense_player_name: Mapped[str] = mapped_column(String, nullable=False)
    defense_player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    defense_player_name: Mapped[str] = mapped_column(String, nullable=False)
    matchup_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    matchup_minutes_sort: Mapped[float | None] = mapped_column(Float, nullable=True)
    partial_possessions: Mapped[float | None] = mapped_column(Float, nullable=True)
    player_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    switches_on: Mapped[float | None] = mapped_column(Float, nullable=True)
    matchup_field_goals_made: Mapped[float | None] = mapped_column(Float, nullable=True)
    matchup_field_goals_attempted: Mapped[float | None] = mapped_column(Float, nullable=True)
    matchup_field_goal_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    matchup_assists: Mapped[float | None] = mapped_column(Float, nullable=True)
    matchup_turnovers: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class WinProbabilityEntry(Base):
    __tablename__ = "win_probability_entries"
    __table_args__ = (
        UniqueConstraint("game_id", "event_num", name="uq_win_probability_entry_game_event"),
        Index("ix_win_probability_entry_game", "game_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_num: Mapped[int] = mapped_column(Integer, nullable=False)
    home_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    visitor_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_pts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visitor_pts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seconds_remaining: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    visitor_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    neutral_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PlayerClutchStats(Base):
    __tablename__ = "player_clutch_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "clutch_time", "point_diff", name="uq_player_clutch_stats_key"),
        Index("ix_player_clutch_stats_player_season", "player_id", "season"),
        Index("ix_player_clutch_stats_team_season", "team_id", "season"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    team_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True)
    season: Mapped[str] = mapped_column(String, nullable=False, index=True)
    clutch_time: Mapped[str] = mapped_column(String, nullable=False)
    point_diff: Mapped[int] = mapped_column(Integer, nullable=False)
    gp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    l: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min: Mapped[float | None] = mapped_column(Float, nullable=True)
    fgm: Mapped[float | None] = mapped_column(Float, nullable=True)
    fga: Mapped[float | None] = mapped_column(Float, nullable=True)
    fg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    fg3m: Mapped[float | None] = mapped_column(Float, nullable=True)
    fg3a: Mapped[float | None] = mapped_column(Float, nullable=True)
    fg3_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ftm: Mapped[float | None] = mapped_column(Float, nullable=True)
    fta: Mapped[float | None] = mapped_column(Float, nullable=True)
    ft_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    oreb: Mapped[float | None] = mapped_column(Float, nullable=True)
    dreb: Mapped[float | None] = mapped_column(Float, nullable=True)
    reb: Mapped[float | None] = mapped_column(Float, nullable=True)
    ast: Mapped[float | None] = mapped_column(Float, nullable=True)
    tov: Mapped[float | None] = mapped_column(Float, nullable=True)
    stl: Mapped[float | None] = mapped_column(Float, nullable=True)
    blk: Mapped[float | None] = mapped_column(Float, nullable=True)
    pf: Mapped[float | None] = mapped_column(Float, nullable=True)
    pts: Mapped[float | None] = mapped_column(Float, nullable=True)
    plus_minus: Mapped[float | None] = mapped_column(Float, nullable=True)
    nba_fantasy_pts: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class PlayerHustleStats(Base):
    __tablename__ = "player_hustle_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_player_hustle_stats_player_season"),
        Index("ix_player_hustle_stats_player_season", "player_id", "season"),
        Index("ix_player_hustle_stats_team_season", "team_id", "season"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    team_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True)
    season: Mapped[str] = mapped_column(String, nullable=False, index=True)
    games_played: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    contested_shots_2pt: Mapped[float | None] = mapped_column(Float, nullable=True)
    contested_shots_3pt: Mapped[float | None] = mapped_column(Float, nullable=True)
    contested_shots: Mapped[float | None] = mapped_column(Float, nullable=True)
    deflections: Mapped[float | None] = mapped_column(Float, nullable=True)
    charges_drawn: Mapped[float | None] = mapped_column(Float, nullable=True)
    screen_assists: Mapped[float | None] = mapped_column(Float, nullable=True)
    screen_ast_pts: Mapped[float | None] = mapped_column(Float, nullable=True)
    loose_balls_recovered_off: Mapped[float | None] = mapped_column(Float, nullable=True)
    loose_balls_recovered_def: Mapped[float | None] = mapped_column(Float, nullable=True)
    loose_balls_recovered: Mapped[float | None] = mapped_column(Float, nullable=True)
    box_outs_off: Mapped[float | None] = mapped_column(Float, nullable=True)
    box_outs_def: Mapped[float | None] = mapped_column(Float, nullable=True)
    box_outs: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class PlayerPlayType(Base):
    __tablename__ = "player_play_types"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "play_type", "type_grouping", name="uq_player_play_types_key"),
        Index("ix_player_play_types_player_season_play_type", "player_id", "season", "play_type"),
        Index("ix_player_play_types_team_season", "team_id", "season"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    team_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True)
    season: Mapped[str] = mapped_column(String, nullable=False, index=True)
    play_type: Mapped[str] = mapped_column(String, nullable=False)
    type_grouping: Mapped[str] = mapped_column(String, nullable=False)
    gp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    poss_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ppp: Mapped[float | None] = mapped_column(Float, nullable=True)
    fg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ft_poss_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    tov_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    sf_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    plusone_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    efg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    poss: Mapped[float | None] = mapped_column(Float, nullable=True)
    pts: Mapped[float | None] = mapped_column(Float, nullable=True)
    percentile: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class PlayerTrackingStats(Base):
    __tablename__ = "player_tracking_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "measure_type", name="uq_player_tracking_stats_key"),
        Index("ix_player_tracking_stats_player_measure", "player_id", "season", "measure_type"),
        Index("ix_player_tracking_stats_team_season", "team_id", "season"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    team_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True)
    season: Mapped[str] = mapped_column(String, nullable=False, index=True)
    measure_type: Mapped[str] = mapped_column(String, nullable=False)
    gp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    fgm: Mapped[float | None] = mapped_column(Float, nullable=True)
    fga: Mapped[float | None] = mapped_column(Float, nullable=True)
    fg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    fg3m: Mapped[float | None] = mapped_column(Float, nullable=True)
    fg3a: Mapped[float | None] = mapped_column(Float, nullable=True)
    fg3_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    efg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    pts: Mapped[float | None] = mapped_column(Float, nullable=True)
    drives: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_fgm: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_fga: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_fg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_ftm: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_fta: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_ft_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_pts: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_pts_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_passes: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_passes_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_ast: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_ast_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_tov: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_tov_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_pf: Mapped[float | None] = mapped_column(Float, nullable=True)
    drive_pf_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class PlayerOnOffStats(Base):
    __tablename__ = "player_on_off_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "team_id", "season", "court_status", name="uq_player_on_off_stats_key"),
        Index("ix_player_on_off_stats_player_season", "player_id", "season"),
        Index("ix_player_on_off_stats_team_season", "team_id", "season"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    team_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    season: Mapped[str] = mapped_column(String, nullable=False, index=True)
    court_status: Mapped[str] = mapped_column(String, nullable=False)
    gp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min: Mapped[float | None] = mapped_column(Float, nullable=True)
    off_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    def_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    ast_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ast_to: Mapped[float | None] = mapped_column(Float, nullable=True)
    ast_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    oreb_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    dreb_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    reb_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    tov_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    efg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ts_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    pace: Mapped[float | None] = mapped_column(Float, nullable=True)
    pie: Mapped[float | None] = mapped_column(Float, nullable=True)
    plus_minus: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class PlayerDefensiveTracking(Base):
    __tablename__ = "player_defensive_tracking"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "defense_category", name="uq_player_defensive_tracking_key"),
        Index("ix_player_defensive_tracking_player_season_category", "player_id", "season", "defense_category"),
        Index("ix_player_defensive_tracking_team_season", "team_id", "season"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    team_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True)
    season: Mapped[str] = mapped_column(String, nullable=False, index=True)
    defense_category: Mapped[str] = mapped_column(String, nullable=False)
    gp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    freq: Mapped[float | None] = mapped_column(Float, nullable=True)
    d_fgm: Mapped[float | None] = mapped_column(Float, nullable=True)
    d_fga: Mapped[float | None] = mapped_column(Float, nullable=True)
    d_fg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    normal_fg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_plusminus: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class PlayerShotLocationStats(Base):
    __tablename__ = "player_shot_location_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_player_shot_location_stats_player_season"),
        Index("ix_player_shot_location_stats_player_season", "player_id", "season"),
        Index("ix_player_shot_location_stats_team_season", "team_id", "season"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    team_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True)
    season: Mapped[str] = mapped_column(String, nullable=False, index=True)
    restricted_area_fgm: Mapped[float | None] = mapped_column(Float, nullable=True)
    restricted_area_fga: Mapped[float | None] = mapped_column(Float, nullable=True)
    restricted_area_fg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    in_the_paint_fgm: Mapped[float | None] = mapped_column(Float, nullable=True)
    in_the_paint_fga: Mapped[float | None] = mapped_column(Float, nullable=True)
    in_the_paint_fg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    mid_range_fgm: Mapped[float | None] = mapped_column(Float, nullable=True)
    mid_range_fga: Mapped[float | None] = mapped_column(Float, nullable=True)
    mid_range_fg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    left_corner_3_fgm: Mapped[float | None] = mapped_column(Float, nullable=True)
    left_corner_3_fga: Mapped[float | None] = mapped_column(Float, nullable=True)
    left_corner_3_fg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    right_corner_3_fgm: Mapped[float | None] = mapped_column(Float, nullable=True)
    right_corner_3_fga: Mapped[float | None] = mapped_column(Float, nullable=True)
    right_corner_3_fg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    above_the_break_3_fgm: Mapped[float | None] = mapped_column(Float, nullable=True)
    above_the_break_3_fga: Mapped[float | None] = mapped_column(Float, nullable=True)
    above_the_break_3_fg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    backcourt_fgm: Mapped[float | None] = mapped_column(Float, nullable=True)
    backcourt_fga: Mapped[float | None] = mapped_column(Float, nullable=True)
    backcourt_fg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class LineupStats(Base):
    __tablename__ = "lineup_stats"
    __table_args__ = (
        UniqueConstraint("group_id", "season", name="uq_lineup_stats_group_season"),
        Index("ix_lineup_stats_team_season_group", "team_id", "season", "group_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    group_name: Mapped[str] = mapped_column(String, nullable=False)
    team_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True)
    season: Mapped[str] = mapped_column(String, nullable=False, index=True)
    gp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min: Mapped[float | None] = mapped_column(Float, nullable=True)
    off_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    def_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    ast_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ast_to: Mapped[float | None] = mapped_column(Float, nullable=True)
    ast_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    oreb_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    dreb_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    reb_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    tov_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    efg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ts_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    pace: Mapped[float | None] = mapped_column(Float, nullable=True)
    pie: Mapped[float | None] = mapped_column(Float, nullable=True)
    plus_minus: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class SportsbookEventMap(Base):
    __tablename__ = "sportsbook_event_maps"
    __table_args__ = (
        UniqueConstraint("sportsbook", "event_id", name="uq_sportsbook_event_map"),
        Index("ix_sportsbook_event_map_lookup", "sportsbook", "nba_game_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sportsbook: Mapped[str] = mapped_column(String, nullable=False)
    event_id: Mapped[str] = mapped_column(String, nullable=False)
    event_name: Mapped[str] = mapped_column(String, nullable=False)
    nba_game_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class LiveGameSnapshot(Base):
    __tablename__ = "live_game_snapshots"
    __table_args__ = (
        Index("ix_live_game_snapshot_game_time", "game_id", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    home_team_id: Mapped[str] = mapped_column(String, nullable=False)
    away_team_id: Mapped[str] = mapped_column(String, nullable=False)
    home_team_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_team_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    game_clock: Mapped[str | None] = mapped_column(String, nullable=True)
    game_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status_text: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class LivePlayerSnapshot(Base):
    __tablename__ = "live_player_snapshots"
    __table_args__ = (
        Index("ix_live_player_snapshot_player_time", "game_id", "player_id", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    team_id: Mapped[str] = mapped_column(String, nullable=False)
    minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    points: Mapped[float | None] = mapped_column(Float, nullable=True)
    rebounds: Mapped[float | None] = mapped_column(Float, nullable=True)
    assists: Mapped[float | None] = mapped_column(Float, nullable=True)
    steals: Mapped[float | None] = mapped_column(Float, nullable=True)
    blocks: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnovers: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_goals_made: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_goals_attempted: Mapped[float | None] = mapped_column(Float, nullable=True)
    threes_made: Mapped[float | None] = mapped_column(Float, nullable=True)
    threes_attempted: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_throws_made: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_throws_attempted: Mapped[float | None] = mapped_column(Float, nullable=True)
    fouls: Mapped[float | None] = mapped_column(Float, nullable=True)
    plus_minus: Mapped[float | None] = mapped_column(Float, nullable=True)
    on_court: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    starter: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class OfficialInjuryReport(Base):
    __tablename__ = "official_injury_reports"
    __table_args__ = (
        UniqueConstraint("pdf_url", name="uq_official_injury_report_pdf_url"),
        Index("ix_official_injury_report_datetime", "report_datetime_utc"),
        Index("ix_official_injury_report_date", "report_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season: Mapped[str | None] = mapped_column(String, nullable=True)
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    report_time_et: Mapped[str | None] = mapped_column(String, nullable=True)
    report_datetime_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    pdf_url: Mapped[str] = mapped_column(String, nullable=False)
    pdf_sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    game_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class OfficialInjuryReportEntry(Base):
    __tablename__ = "official_injury_report_entries"
    __table_args__ = (
        Index("ix_official_injury_report_entry_report", "report_id", "team_abbreviation"),
        Index("ix_official_injury_report_entry_player", "player_id", "report_datetime_utc"),
        Index("ix_official_injury_report_entry_team_date", "team_abbreviation", "game_date", "report_datetime_utc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("official_injury_reports.id"), nullable=False, index=True)
    season: Mapped[str | None] = mapped_column(String, nullable=True)
    report_datetime_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    game_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    game_time_et: Mapped[str | None] = mapped_column(String, nullable=True)
    matchup: Mapped[str | None] = mapped_column(String, nullable=True)
    team_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    team_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    team_name: Mapped[str | None] = mapped_column(String, nullable=True)
    player_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    player_name: Mapped[str | None] = mapped_column(String, nullable=True)
    current_status: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_submitted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False, default="official_nba_pdf")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)



class PregameContextSnapshot(Base):
    __tablename__ = "pregame_context_snapshots"
    __table_args__ = (
        UniqueConstraint("game_id", "player_key", "captured_at", name="uq_pregame_context_snapshot_capture"),
        Index("ix_pregame_context_snapshot_game_capture", "game_id", "captured_at"),
        Index("ix_pregame_context_snapshot_player_lookup", "game_id", "team_abbreviation", "player_id", "captured_at"),
        Index("ix_pregame_context_snapshot_name_lookup", "game_id", "team_abbreviation", "normalized_player_name", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    team_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    opponent_team_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    player_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    player_key: Mapped[str] = mapped_column(String, nullable=False)
    normalized_player_name: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    player_name: Mapped[str | None] = mapped_column(String, nullable=True)
    expected_start: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    starter_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    official_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    projected_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    late_scratch_risk: Mapped[float | None] = mapped_column(Float, nullable=True)
    teammate_out_count_top7: Mapped[float | None] = mapped_column(Float, nullable=True)
    teammate_out_count_top9: Mapped[float | None] = mapped_column(Float, nullable=True)
    missing_high_usage_teammates: Mapped[float | None] = mapped_column(Float, nullable=True)
    missing_primary_ballhandler: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    missing_frontcourt_rotation_piece: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    vacated_minutes_proxy: Mapped[float | None] = mapped_column(Float, nullable=True)
    vacated_usage_proxy: Mapped[float | None] = mapped_column(Float, nullable=True)
    role_replacement_minutes_proxy: Mapped[float | None] = mapped_column(Float, nullable=True)
    role_replacement_usage_proxy: Mapped[float | None] = mapped_column(Float, nullable=True)
    role_replacement_touches_proxy: Mapped[float | None] = mapped_column(Float, nullable=True)
    role_replacement_passes_proxy: Mapped[float | None] = mapped_column(Float, nullable=True)
    projected_lineup_confirmed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    official_starter_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    pregame_context_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AbsenceImpactSummary(Base):
    __tablename__ = "absence_impact_summaries"
    __table_args__ = (
        UniqueConstraint(
            "source_player_id",
            "beneficiary_player_id",
            "team_abbreviation",
            "window_start_date",
            "window_end_date",
            name="uq_absence_impact_summary_window",
        ),
        Index(
            "ix_absence_impact_source_lookup",
            "source_player_id",
            "team_abbreviation",
            "window_end_date",
        ),
        Index(
            "ix_absence_impact_beneficiary_lookup",
            "beneficiary_player_id",
            "team_abbreviation",
            "window_end_date",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_player_name: Mapped[str] = mapped_column(String, nullable=False)
    beneficiary_player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    beneficiary_player_name: Mapped[str] = mapped_column(String, nullable=False)
    team_abbreviation: Mapped[str] = mapped_column(String, nullable=False, index=True)
    window_start_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    window_end_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    source_out_game_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_active_game_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    beneficiary_out_game_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    beneficiary_active_game_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minutes_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    points_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    rebounds_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    assists_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    blocks_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    touches_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    passes_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    impact_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    build_version: Mapped[str] = mapped_column(String, nullable=False, default="absence-impact-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class AbsenceSourceOverride(Base):
    __tablename__ = "absence_source_overrides"
    __table_args__ = (
        Index("ix_absence_source_override_team_date", "team_abbreviation", "start_date", "end_date"),
        Index("ix_absence_source_override_team_player_id", "team_abbreviation", "player_id"),
        Index("ix_absence_source_override_team_normalized_name", "team_abbreviation", "normalized_player_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_abbreviation: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    player_name: Mapped[str | None] = mapped_column(String, nullable=True)
    normalized_player_name: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    include_as_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("ix_ingestion_run_job_started", "job_name", "started_at"),
        Index("ix_ingestion_run_status_started", "status", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    items: Mapped[list["IngestionRunItem"]] = relationship("IngestionRunItem", back_populates="run")


class IngestionRunItem(Base):
    __tablename__ = "ingestion_run_items"
    __table_args__ = (
        Index("ix_ingestion_run_item_run_stage", "run_id", "stage", "created_at"),
        Index("ix_ingestion_run_item_status", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_key: Mapped[str] = mapped_column(String, nullable=False)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    run: Mapped[IngestionRun] = relationship("IngestionRun", back_populates="items")


class RotationSyncState(Base):
    __tablename__ = "rotation_sync_states"
    __table_args__ = (
        Index("ix_rotation_sync_state_season", "season"),
        Index("ix_rotation_sync_state_season_status", "season", "status", "next_retry_at"),
        Index("ix_rotation_sync_state_status_due", "status", "next_retry_at"),
    )

    game_id: Mapped[str] = mapped_column(String, primary_key=True)
    season: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_succeeded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error_type: Mapped[str | None] = mapped_column(String, nullable=True)
    last_error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class ModelSignal(Base):
    __tablename__ = "model_signals"
    __table_args__ = (
        Index("ix_model_signal_lookup", "game_id", "player_id", "stat_type", "market_phase", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    market_phase: Mapped[str] = mapped_column(String, nullable=False)
    sportsbook: Mapped[str] = mapped_column(String, nullable=False, default="fanduel")
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    stat_type: Mapped[str] = mapped_column(String, nullable=False)
    line: Mapped[float] = mapped_column(Float, nullable=False)
    projected_value: Mapped[float] = mapped_column(Float, nullable=False)
    over_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    under_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    edge_over: Mapped[float | None] = mapped_column(Float, nullable=True)
    edge_under: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_side: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class StatsSignalSnapshot(Base):
    __tablename__ = "stats_signal_snapshots"
    __table_args__ = (
        Index("ix_stats_signal_snapshot_player_created", "player_id", "created_at"),
        Index("ix_stats_signal_snapshot_game_created", "game_id", "created_at"),
        Index("ix_stats_signal_snapshot_status_created", "readiness_status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    team_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True)
    opponent_abbreviation: Mapped[str | None] = mapped_column(String, nullable=True)
    stat_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    snapshot_phase: Mapped[str] = mapped_column(String, nullable=False, default="current")
    line: Mapped[float] = mapped_column(Float, nullable=False)
    over_odds: Mapped[int] = mapped_column(Integer, nullable=False)
    under_odds: Mapped[int] = mapped_column(Integer, nullable=False)
    projected_value: Mapped[float] = mapped_column(Float, nullable=False)
    edge_over: Mapped[float | None] = mapped_column(Float, nullable=True)
    edge_under: Mapped[float | None] = mapped_column(Float, nullable=True)
    over_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    under_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_side: Mapped[str | None] = mapped_column(String, nullable=True)
    recent_hit_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    recent_games_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    key_factor: Mapped[str | None] = mapped_column(String, nullable=True)
    is_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    readiness_status: Mapped[str] = mapped_column(String, nullable=False, default="ready")
    using_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    readiness_json: Mapped[str] = mapped_column(Text, nullable=False)
    breakdown_json: Mapped[str] = mapped_column(Text, nullable=False)
    opportunity_json: Mapped[str] = mapped_column(Text, nullable=False)
    features_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_prop_captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    source_context_captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_injury_report_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class SignalAuditTrail(Base):
    __tablename__ = "signal_audit_trail"
    __table_args__ = (
        Index("ix_signal_audit_trail_game_captured", "game_id", "captured_at"),
        Index("ix_signal_audit_trail_player_captured", "player_id", "captured_at"),
        Index("ix_signal_audit_trail_phase_captured", "snapshot_phase", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    stat_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    snapshot_phase: Mapped[str] = mapped_column(String, nullable=False, default="current")
    line: Mapped[float] = mapped_column(Float, nullable=False)
    projected_value: Mapped[float] = mapped_column(Float, nullable=False)
    edge: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    recommended_side: Mapped[str | None] = mapped_column(String, nullable=True)
    readiness_status: Mapped[str] = mapped_column(String, nullable=False, default="ready")
    blockers_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    breakdown_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_context_captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_injury_report_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


