from datetime import datetime
from sqlalchemy import Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import mapped_column, relationship
from database.db import Base

class User(Base):
    __tablename__ = "users"

    id = mapped_column(Integer, primary_key=True, index=True)
    email = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash = mapped_column(String, nullable=False)
    tier = mapped_column(String, default="FREE", nullable=False)
    is_active = mapped_column(Boolean, default=True, nullable=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    subscription = relationship("Subscription", back_populates="user", uselist=False)

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = mapped_column(Integer, primary_key=True, index=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    stripe_customer_id = mapped_column(String, unique=True, nullable=True)
    stripe_subscription_id = mapped_column(String, unique=True, nullable=True)
    tier = mapped_column(String, default="FREE", nullable=False)
    status = mapped_column(String, default="active", nullable=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="subscription")

class PlayerPropSnapshot(Base): 
    __tablename__ = "player_prop_snapshots"

    id = mapped_column(Integer, primary_key=True, index=True)
    game_id = mapped_column(String, nullable=False, index=True)
    player_id = mapped_column(String, nullable=False, index=True)
    player_name = mapped_column(String, nullable=False)
    team = mapped_column(String, nullable=True)
    opponent = mapped_column(String, nullable=True)
    stat_type = mapped_column(String, nullable=False)
    line = mapped_column(Float, nullable=False)
    over_odds = mapped_column(Integer, nullable=False)
    under_odds = mapped_column(Integer, nullable=False)
    is_live = mapped_column(Boolean, default=False, nullable=False)
    captured_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id = mapped_column(Integer, primary_key=True, index=True)
    game_id = mapped_column(String, nullable=False, index=True)
    player_id = mapped_column(String, nullable=False, index=True)
    player_name = mapped_column(String, nullable=False)
    stat_type = mapped_column(String, nullable=False)
    line = mapped_column(Float, nullable=False)
    over_odds = mapped_column(Integer, nullable=False)
    under_odds = mapped_column(Integer, nullable=False)
    source = mapped_column(String, default="fanduel", nullable=False)
    captured_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

class HistoricalGameLog(Base):
    __tablename__ = "historical_game_logs"

    id = mapped_column(Integer, primary_key=True, index=True)
    game_id = mapped_column(String, nullable=False, index=True)
    game_date = mapped_column(DateTime, nullable=False, index=True)
    player_id = mapped_column(String, nullable=False, index=True)
    player_name = mapped_column(String, nullable=False)
    team = mapped_column(String, nullable=False)
    opponent = mapped_column(String, nullable=False)
    is_home = mapped_column(Boolean, nullable=False)
    minutes = mapped_column(Float, nullable=True)
    points = mapped_column(Float, nullable=True)
    rebounds = mapped_column(Float, nullable=True)
    assists = mapped_column(Float, nullable=True)
    steals = mapped_column(Float, nullable=True)
    blocks = mapped_column(Float, nullable=True)
    turnovers = mapped_column(Float, nullable=True)
    threes_made = mapped_column(Float, nullable=True)
    threes_attempted = mapped_column(Float, nullable=True)
    field_goals_made = mapped_column(Float, nullable=True)
    field_goals_attempted = mapped_column(Float, nullable=True)
    free_throws_made = mapped_column(Float, nullable=True)
    free_throws_attempted = mapped_column(Float, nullable=True)
    fantasy_points = mapped_column(Float, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

class HistoricalAdvancedLog(Base):
    __tablename__ = "historical_advanced_logs"

    id = mapped_column(Integer, primary_key=True, index=True)
    game_id = mapped_column(String, nullable=False, index=True)
    player_id = mapped_column(String, nullable=False, index=True)

    # From BoxScoreAdvancedV3
    usage_percentage = mapped_column(Float, nullable=True)
    estimated_usage_percentage = mapped_column(Float, nullable=True)
    pace = mapped_column(Float, nullable=True)
    pace_per40 = mapped_column(Float, nullable=True)
    possessions = mapped_column(Float, nullable=True)
    offensive_rating = mapped_column(Float, nullable=True)
    defensive_rating = mapped_column(Float, nullable=True)
    net_rating = mapped_column(Float, nullable=True)
    true_shooting_percentage = mapped_column(Float, nullable=True)
    effective_field_goal_percentage = mapped_column(Float, nullable=True)
    assist_percentage = mapped_column(Float, nullable=True)
    assist_to_turnover = mapped_column(Float, nullable=True)
    offensive_rebound_percentage = mapped_column(Float, nullable=True)
    defensive_rebound_percentage = mapped_column(Float, nullable=True)
    pie = mapped_column(Float, nullable=True)

    # From BoxScorePlayerTrackV3
    speed = mapped_column(Float, nullable=True)
    distance = mapped_column(Float, nullable=True)
    touches = mapped_column(Float, nullable=True)
    passes = mapped_column(Float, nullable=True)
    secondary_assists = mapped_column(Float, nullable=True)
    free_throw_assists = mapped_column(Float, nullable=True)
    rebound_chances_offensive = mapped_column(Float, nullable=True)
    rebound_chances_defensive = mapped_column(Float, nullable=True)
    rebound_chances_total = mapped_column(Float, nullable=True)
    contested_field_goals_made = mapped_column(Float, nullable=True)
    contested_field_goals_attempted = mapped_column(Float, nullable=True)
    uncontested_field_goals_made = mapped_column(Float, nullable=True)
    uncontested_field_goals_attempted = mapped_column(Float, nullable=True)
    defended_at_rim_field_goals_made = mapped_column(Float, nullable=True)
    defended_at_rim_field_goals_attempted = mapped_column(Float, nullable=True)

    created_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

class TeamDefensiveStat(Base):
    __tablename__ = "team_defensive_stats"

    id = mapped_column(Integer, primary_key=True, index=True)
    team_id = mapped_column(String, nullable=False, index=True)
    team_name = mapped_column(String, nullable=False)
    season = mapped_column(String, nullable=False)

    # Overall defensive ratings - from LeagueDashTeamStats
    defensive_rating = mapped_column(Float, nullable=True)
    opponent_pace = mapped_column(Float, nullable=True)
    points_allowed_per_game = mapped_column(Float, nullable=True)
    opponent_field_goal_percentage = mapped_column(Float, nullable=True)
    opponent_three_point_percentage = mapped_column(Float, nullable=True)

    # Shot zone defense - from LeagueDashPtDefend
    # How opponent shoots against this team by zone
    d_fg_pct_overall = mapped_column(Float, nullable=True)
    d_fg_pct_3pt = mapped_column(Float, nullable=True)
    d_fg_pct_2pt = mapped_column(Float, nullable=True)
    d_fg_pct_lt6ft = mapped_column(Float, nullable=True)
    d_fg_pct_lt10ft = mapped_column(Float, nullable=True)
    d_fg_pct_gt15ft = mapped_column(Float, nullable=True)

    # Deviation from normal FG% - how much better/worse than average
    # Negative = good defense (holding below average), Positive = bad defense
    d_pct_plusminus_overall = mapped_column(Float, nullable=True)
    d_pct_plusminus_3pt = mapped_column(Float, nullable=True)
    d_pct_plusminus_2pt = mapped_column(Float, nullable=True)
    d_pct_plusminus_lt6ft = mapped_column(Float, nullable=True)

    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)