from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from statistics import mean, median, pstdev
from typing import Any

from database.db import session_scope
from database.models import Game, HistoricalAdvancedLog, HistoricalGameLog, PlayerPropSnapshot, Team, TeamDefensiveStat


@dataclass(slots=True)
class PregameOpportunityFeatures:
    game_id: str
    player_id: str
    player_name: str
    captured_at: datetime
    game_date: datetime | None = None
    team_abbreviation: str | None = None
    opponent_abbreviation: str | None = None
    is_home: bool | None = None
    days_rest: int | None = None
    back_to_back: bool | None = None
    sample_size: int = 0
    last5_count: int = 0
    last10_count: int = 0
    season_minutes_avg: float | None = None
    last10_minutes_avg: float | None = None
    last5_minutes_avg: float | None = None
    last10_minutes_std: float | None = None
    season_usage_pct: float | None = None
    last10_usage_pct: float | None = None
    last5_usage_pct: float | None = None
    season_est_usage_pct: float | None = None
    last10_est_usage_pct: float | None = None
    last5_est_usage_pct: float | None = None
    season_touches: float | None = None
    last10_touches: float | None = None
    last5_touches: float | None = None
    season_passes: float | None = None
    last10_passes: float | None = None
    last5_passes: float | None = None
    season_off_rating: float | None = None
    last10_off_rating: float | None = None
    last5_off_rating: float | None = None
    team_pace: float | None = None
    opponent_def_rating: float | None = None
    opponent_pace: float | None = None
    opponent_points_allowed: float | None = None
    opponent_fg_pct_allowed: float | None = None
    opponent_3pt_pct_allowed: float | None = None
    league_avg_def_rating: float | None = None
    league_avg_pace: float | None = None
    league_avg_opponent_points: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PregameFeatureSeed:
    game_id: str
    player_id: str
    player_name: str
    stat_type: str
    line: float
    over_odds: int
    under_odds: int
    captured_at: datetime
    game_date: datetime | None
    team_abbreviation: str | None
    opponent_abbreviation: str | None
    is_home: bool | None
    days_rest: int | None
    back_to_back: bool | None
    recent_logs: list[HistoricalGameLog]
    advanced_rows: list[HistoricalAdvancedLog]
    team_defense: TeamDefensiveStat | None
    opponent_defense: TeamDefensiveStat | None
    league_avg_def_rating: float | None
    league_avg_pace: float | None
    league_avg_opponent_points: float | None

    def build_opportunity_features(self) -> PregameOpportunityFeatures:
        return PregameOpportunityFeatures(
            game_id=self.game_id,
            player_id=self.player_id,
            player_name=self.player_name,
            captured_at=self.captured_at,
            game_date=self.game_date,
            team_abbreviation=self.team_abbreviation,
            opponent_abbreviation=self.opponent_abbreviation,
            is_home=self.is_home,
            days_rest=self.days_rest,
            back_to_back=self.back_to_back,
            team_pace=self.team_defense.pace if self.team_defense else None,
            opponent_def_rating=self.opponent_defense.defensive_rating if self.opponent_defense else None,
            opponent_pace=self.opponent_defense.pace if self.opponent_defense else None,
            opponent_points_allowed=self.opponent_defense.opponent_points_per_game if self.opponent_defense else None,
            opponent_fg_pct_allowed=self.opponent_defense.opponent_field_goal_percentage if self.opponent_defense else None,
            opponent_3pt_pct_allowed=self.opponent_defense.opponent_three_point_percentage if self.opponent_defense else None,
            league_avg_def_rating=self.league_avg_def_rating,
            league_avg_pace=self.league_avg_pace,
            league_avg_opponent_points=self.league_avg_opponent_points,
            **_build_shared_log_aggregates(self.recent_logs),
            **_build_shared_advanced_aggregates(self.advanced_rows),
        )


def _values(rows: list[Any], attr: str) -> list[float]:
    collected: list[float] = []
    for row in rows:
        value = getattr(row, attr, None)
        if value is not None:
            collected.append(float(value))
    return collected


def _mean(values: list[float]) -> float | None:
    return mean(values) if values else None


def _median(values: list[float]) -> float | None:
    return median(values) if values else None


def _std(values: list[float]) -> float | None:
    return pstdev(values) if len(values) > 1 else 0.0 if values else None


def _safe_pct(makes: list[float], attempts: list[float]) -> float | None:
    total_attempts = sum(attempts)
    if total_attempts <= 0:
        return None
    return sum(makes) / total_attempts


def _weighted_average(weighted_values: list[tuple[float, float | None]]) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for weight, value in weighted_values:
        if value is None:
            continue
        numerator += weight * float(value)
        denominator += weight
    if denominator == 0:
        return None
    return numerator / denominator


def _resolve_team_context(snapshot: PlayerPropSnapshot, game: Game | None, latest_log: HistoricalGameLog | None) -> tuple[str | None, str | None, bool | None]:
    candidate_team = snapshot.team or (latest_log.team if latest_log else None)
    candidate_opponent = snapshot.opponent or (latest_log.opponent if latest_log else None)

    if game is None:
        return candidate_team, candidate_opponent, latest_log.is_home if latest_log else None

    home = game.home_team_abbreviation
    away = game.away_team_abbreviation
    teams = {home, away}

    if candidate_team in teams:
        opponent = away if candidate_team == home else home
        return candidate_team, opponent, candidate_team == home

    if candidate_opponent in teams:
        team = away if candidate_opponent == home else home
        return team, candidate_opponent, team == home

    if latest_log and latest_log.team in teams:
        opponent = away if latest_log.team == home else home
        return latest_log.team, opponent, latest_log.team == home

    return candidate_team, candidate_opponent, latest_log.is_home if latest_log else None


def _build_shared_log_aggregates(logs: list[HistoricalGameLog]) -> dict[str, float | int | None]:
    last10 = logs[:10]
    last5 = logs[:5]
    return {
        "sample_size": len(logs),
        "last10_count": len(last10),
        "last5_count": len(last5),
        "season_minutes_avg": _mean(_values(logs, "minutes")),
        "last10_minutes_avg": _mean(_values(last10, "minutes")),
        "last5_minutes_avg": _mean(_values(last5, "minutes")),
        "last10_minutes_std": _std(_values(last10, "minutes")),
    }


def _build_shared_advanced_aggregates(rows: list[HistoricalAdvancedLog]) -> dict[str, float | None]:
    last10 = rows[:10]
    last5 = rows[:5]
    return {
        "season_usage_pct": _mean(_values(rows, "usage_percentage")),
        "last10_usage_pct": _mean(_values(last10, "usage_percentage")),
        "last5_usage_pct": _mean(_values(last5, "usage_percentage")),
        "season_est_usage_pct": _mean(_values(rows, "estimated_usage_percentage")),
        "last10_est_usage_pct": _mean(_values(last10, "estimated_usage_percentage")),
        "last5_est_usage_pct": _mean(_values(last5, "estimated_usage_percentage")),
        "season_touches": _mean(_values(rows, "touches")),
        "last10_touches": _mean(_values(last10, "touches")),
        "last5_touches": _mean(_values(last5, "touches")),
        "season_passes": _mean(_values(rows, "passes")),
        "last10_passes": _mean(_values(last10, "passes")),
        "last5_passes": _mean(_values(last5, "passes")),
        "season_off_rating": _mean(_values(rows, "offensive_rating")),
        "last10_off_rating": _mean(_values(last10, "offensive_rating")),
        "last5_off_rating": _mean(_values(last5, "offensive_rating")),
    }


def load_pregame_feature_seeds(captured_at: datetime | None = None, stat_type: str = "points", limit: int | None = None) -> list[PregameFeatureSeed]:
    with session_scope() as session:
        latest_captured_at = captured_at
        if latest_captured_at is None:
            latest_captured_at = (
                session.query(PlayerPropSnapshot.captured_at)
                .filter(PlayerPropSnapshot.stat_type == stat_type, PlayerPropSnapshot.is_live.is_(False))
                .order_by(PlayerPropSnapshot.captured_at.desc())
                .limit(1)
                .scalar()
            )

        if latest_captured_at is None:
            return []

        market_query = (
            session.query(PlayerPropSnapshot)
            .filter(
                PlayerPropSnapshot.stat_type == stat_type,
                PlayerPropSnapshot.is_live.is_(False),
                PlayerPropSnapshot.captured_at == latest_captured_at,
            )
            .order_by(PlayerPropSnapshot.game_id, PlayerPropSnapshot.player_name)
        )
        if limit is not None:
            market_query = market_query.limit(limit)
        markets = market_query.all()
        if not markets:
            return []

        games_by_id = {
            game.game_id: game
            for game in session.query(Game)
            .filter(Game.game_id.in_([market.game_id for market in markets]))
            .all()
        }
        teams = session.query(Team).all()
        team_id_by_abbreviation = {team.abbreviation: team.team_id for team in teams if team.abbreviation}

        team_defense_rows = session.query(TeamDefensiveStat).all()
        defense_by_team_id: dict[str, TeamDefensiveStat] = {}
        for row in team_defense_rows:
            current = defense_by_team_id.get(row.team_id)
            if current is None or row.updated_at > current.updated_at:
                defense_by_team_id[row.team_id] = row

        league_avg_def_rating = _mean([float(row.defensive_rating) for row in defense_by_team_id.values() if row.defensive_rating is not None])
        league_avg_pace = _mean([float(row.pace) for row in defense_by_team_id.values() if row.pace is not None])
        league_avg_opponent_points = _mean([
            float(row.opponent_points_per_game)
            for row in defense_by_team_id.values()
            if row.opponent_points_per_game is not None
        ])

        seeds: list[PregameFeatureSeed] = []
        for market in markets:
            game = games_by_id.get(market.game_id)
            cutoff = game.game_date if game and game.game_date else market.captured_at
            recent_logs = (
                session.query(HistoricalGameLog)
                .filter(HistoricalGameLog.player_id == market.player_id, HistoricalGameLog.game_date < cutoff)
                .order_by(HistoricalGameLog.game_date.desc())
                .limit(15)
                .all()
            )
            if not recent_logs:
                continue

            latest_log = recent_logs[0]
            team_abbreviation, opponent_abbreviation, is_home = _resolve_team_context(market, game, latest_log)

            advanced_rows: list[HistoricalAdvancedLog] = []
            game_ids = [log.game_id for log in recent_logs]
            if game_ids:
                advanced_by_game = {
                    row.game_id: row
                    for row in session.query(HistoricalAdvancedLog)
                    .filter(HistoricalAdvancedLog.player_id == market.player_id, HistoricalAdvancedLog.game_id.in_(game_ids))
                    .all()
                }
                advanced_rows = [advanced_by_game[log.game_id] for log in recent_logs if log.game_id in advanced_by_game]

            days_rest = None
            if latest_log.game_date and cutoff:
                days_rest = max((cutoff.date() - latest_log.game_date.date()).days, 0)

            opponent_team_id = team_id_by_abbreviation.get(opponent_abbreviation or "")
            team_team_id = team_id_by_abbreviation.get(team_abbreviation or "")
            opponent_defense = defense_by_team_id.get(opponent_team_id) if opponent_team_id else None
            team_defense = defense_by_team_id.get(team_team_id) if team_team_id else None

            seeds.append(
                PregameFeatureSeed(
                    game_id=market.game_id,
                    player_id=market.player_id,
                    player_name=market.player_name,
                    stat_type=market.stat_type,
                    line=float(market.line),
                    over_odds=int(market.over_odds),
                    under_odds=int(market.under_odds),
                    captured_at=market.captured_at,
                    game_date=cutoff,
                    team_abbreviation=team_abbreviation,
                    opponent_abbreviation=opponent_abbreviation,
                    is_home=is_home,
                    days_rest=days_rest,
                    back_to_back=days_rest == 1 if days_rest is not None else None,
                    recent_logs=recent_logs,
                    advanced_rows=advanced_rows,
                    team_defense=team_defense,
                    opponent_defense=opponent_defense,
                    league_avg_def_rating=league_avg_def_rating,
                    league_avg_pace=league_avg_pace,
                    league_avg_opponent_points=league_avg_opponent_points,
                )
            )

    return seeds


def build_pregame_opportunity_features(captured_at: datetime | None = None, stat_type: str = "points", limit: int | None = None) -> list[PregameOpportunityFeatures]:
    seeds = load_pregame_feature_seeds(captured_at=captured_at, stat_type=stat_type, limit=limit)
    return [seed.build_opportunity_features() for seed in seeds]
