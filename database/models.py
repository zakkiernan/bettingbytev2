from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, default="FREE", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    subscription: Mapped["Subscription | None"] = relationship(
        "Subscription",
        back_populates="user",
        uselist=False,
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    tier: Mapped[str] = mapped_column(String, default="FREE", nullable=False)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user: Mapped[User] = relationship("User", back_populates="subscription")


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
    game_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
            name="uq_player_prop_snapshot_market",
        ),
        Index("ix_player_prop_snapshot_lookup", "game_id", "player_id", "stat_type", "is_live"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    team: Mapped[str | None] = mapped_column(String, nullable=True)
    opponent: Mapped[str | None] = mapped_column(String, nullable=True)
    stat_type: Mapped[str] = mapped_column(String, nullable=False)
    line: Mapped[float] = mapped_column(Float, nullable=False)
    over_odds: Mapped[int] = mapped_column(Integer, nullable=False)
    under_odds: Mapped[int] = mapped_column(Integer, nullable=False)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"
    __table_args__ = (
        Index("ix_odds_snapshot_lookup", "game_id", "player_id", "stat_type", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    stat_type: Mapped[str] = mapped_column(String, nullable=False)
    line: Mapped[float] = mapped_column(Float, nullable=False)
    over_odds: Mapped[int] = mapped_column(Integer, nullable=False)
    under_odds: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String, default="fanduel", nullable=False)
    market_phase: Mapped[str] = mapped_column(String, default="pregame", nullable=False)
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
