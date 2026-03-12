from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from statistics import mean, median, pstdev
from typing import Any

from analytics.injury_report_loader import (
    build_official_injury_report_index,
    get_official_team_summary,
    load_latest_official_injury_report_rows,
    match_official_injury_row,
)
from analytics.pregame_context_loader import build_pregame_context_index, load_pregame_context_feature_rows, match_pregame_context_row
from database.db import session_scope
from database.models import (
    Game,
    HistoricalAdvancedLog,
    HistoricalGameLog,
    PlayerPropSnapshot,
    PlayerRotationGame,
    Team,
    TeamDefensiveStat,
)


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
    rotation_sample_size: int = 0
    season_rotation_minutes_avg: float | None = None
    last10_rotation_minutes_avg: float | None = None
    last5_rotation_minutes_avg: float | None = None
    last10_rotation_minutes_std: float | None = None
    season_stint_count_avg: float | None = None
    last10_stint_count_avg: float | None = None
    last5_stint_count_avg: float | None = None
    season_started_rate: float | None = None
    last10_started_rate: float | None = None
    last5_started_rate: float | None = None
    season_closed_rate: float | None = None
    last10_closed_rate: float | None = None
    last5_closed_rate: float | None = None
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
    official_injury_status: str | None = None
    official_injury_reason: str | None = None
    official_report_datetime_utc: datetime | None = None
    official_teammate_out_count: float | None = None
    official_teammate_doubtful_count: float | None = None
    official_teammate_questionable_count: float | None = None
    expected_start: bool | None = None
    starter_confidence: float | None = None
    official_available: bool | None = None
    projected_available: bool | None = None
    late_scratch_risk: float | None = None
    teammate_out_count_top7: float | None = None
    teammate_out_count_top9: float | None = None
    missing_high_usage_teammates: float | None = None
    missing_primary_ballhandler: bool | None = None
    missing_frontcourt_rotation_piece: bool | None = None
    vacated_minutes_proxy: float | None = None
    vacated_usage_proxy: float | None = None
    projected_lineup_confirmed: bool | None = None
    official_starter_flag: bool | None = None
    pregame_context_confidence: float | None = None

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
    rotation_rows: list[PlayerRotationGame]
    team_defense: TeamDefensiveStat | None
    opponent_defense: TeamDefensiveStat | None
    league_avg_def_rating: float | None
    league_avg_pace: float | None
    league_avg_opponent_points: float | None
    pregame_context_row: dict[str, Any] | None = None
    official_injury_row: dict[str, Any] | None = None
    official_injury_team_summary: dict[str, Any] | None = None

    def build_opportunity_features(self) -> PregameOpportunityFeatures:
        context_aggregates = _merge_context_aggregates(
            _build_pregame_context_aggregates(self.pregame_context_row),
            _build_official_injury_aggregates(
                self.official_injury_row,
                self.official_injury_team_summary,
                captured_at=self.captured_at,
            ),
        )
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
            **_build_rotation_aggregates(self.rotation_rows),
            **_build_shared_advanced_aggregates(self.advanced_rows),
            **context_aggregates,
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


def _build_rotation_aggregates(rows: list[PlayerRotationGame]) -> dict[str, float | int | None]:
    last10 = rows[:10]
    last5 = rows[:5]

    def rotation_minutes(sample: list[PlayerRotationGame]) -> list[float]:
        values: list[float] = []
        for row in sample:
            if row.total_shift_duration_real is None:
                continue
            values.append(float(row.total_shift_duration_real) / 600.0)
        return values

    def flag_rate(sample: list[PlayerRotationGame], attr: str) -> float | None:
        values = [1.0 if getattr(row, attr) else 0.0 for row in sample if getattr(row, attr) is not None]
        return _mean(values)

    return {
        "rotation_sample_size": len(rows),
        "season_rotation_minutes_avg": _mean(rotation_minutes(rows)),
        "last10_rotation_minutes_avg": _mean(rotation_minutes(last10)),
        "last5_rotation_minutes_avg": _mean(rotation_minutes(last5)),
        "last10_rotation_minutes_std": _std(rotation_minutes(last10)),
        "season_stint_count_avg": _mean(_values(rows, "stint_count")),
        "last10_stint_count_avg": _mean(_values(last10, "stint_count")),
        "last5_stint_count_avg": _mean(_values(last5, "stint_count")),
        "season_started_rate": flag_rate(rows, "started"),
        "last10_started_rate": flag_rate(last10, "started"),
        "last5_started_rate": flag_rate(last5, "started"),
        "season_closed_rate": flag_rate(rows, "closed_game"),
        "last10_closed_rate": flag_rate(last10, "closed_game"),
        "last5_closed_rate": flag_rate(last5, "closed_game"),
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


def _build_official_injury_aggregates(
    row: dict[str, Any] | None,
    team_summary: dict[str, Any] | None,
    *,
    captured_at: datetime,
) -> dict[str, Any]:
    base = {
        "official_injury_status": None,
        "official_injury_reason": None,
        "official_report_datetime_utc": None,
        "official_teammate_out_count": None,
        "official_teammate_doubtful_count": None,
        "official_teammate_questionable_count": None,
        "official_available": None,
        "late_scratch_risk": None,
        "teammate_out_count_top7": None,
        "teammate_out_count_top9": None,
        "pregame_context_confidence": None,
    }
    if row is None and team_summary is None:
        return base

    report_datetime = None
    if row is not None:
        report_datetime = row.get("report_datetime_utc")
    if report_datetime is None and team_summary is not None:
        report_datetime = team_summary.get("report_datetime_utc")

    confidence = None
    if isinstance(report_datetime, datetime):
        age_hours = max((captured_at - report_datetime).total_seconds() / 3600.0, 0.0)
        confidence = max(0.35, min(0.92, 0.92 - 0.06 * age_hours))
    elif row is not None or team_summary is not None:
        confidence = 0.5

    if team_summary is not None:
        out_count = float(team_summary.get("out_count") or 0.0)
        doubtful_count = float(team_summary.get("doubtful_count") or 0.0)
        questionable_count = float(team_summary.get("questionable_count") or 0.0)
        base["official_teammate_out_count"] = out_count
        base["official_teammate_doubtful_count"] = doubtful_count
        base["official_teammate_questionable_count"] = questionable_count

    if row is None:
        base["official_report_datetime_utc"] = report_datetime
        base["pregame_context_confidence"] = min(float(confidence), 0.25) if confidence is not None else 0.25
        return base

    status = str(row.get("current_status") or "").upper()
    base["official_injury_status"] = status or None
    base["official_injury_reason"] = row.get("reason")
    base["official_report_datetime_utc"] = report_datetime
    base["pregame_context_confidence"] = confidence

    if status in {"OUT", "SUSPENDED"}:
        base["official_available"] = False
        base["late_scratch_risk"] = 1.0
    elif status == "AVAILABLE":
        base["official_available"] = True
        base["late_scratch_risk"] = 0.0
    elif status == "PROBABLE":
        base["official_available"] = True
        base["late_scratch_risk"] = 0.15
    elif status == "QUESTIONABLE":
        base["late_scratch_risk"] = 0.65
    elif status == "DOUBTFUL":
        base["late_scratch_risk"] = 0.85

    if status == "NOT_YET_SUBMITTED" and confidence is not None:
        base["pregame_context_confidence"] = min(confidence, 0.35)

    return base


def _merge_context_aggregates(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = dict(fallback)
    merged.update({key: value for key, value in primary.items() if key not in {"late_scratch_risk", "pregame_context_confidence", "teammate_out_count_top7", "teammate_out_count_top9"}})

    for key in ("official_available", "projected_available", "expected_start", "starter_confidence", "missing_high_usage_teammates", "missing_primary_ballhandler", "missing_frontcourt_rotation_piece", "vacated_minutes_proxy", "vacated_usage_proxy", "projected_lineup_confirmed", "official_starter_flag"):
        primary_value = primary.get(key)
        if primary_value is not None:
            merged[key] = primary_value

    primary_late = primary.get("late_scratch_risk")
    fallback_late = fallback.get("late_scratch_risk")
    if primary_late is None:
        merged["late_scratch_risk"] = fallback_late
    elif fallback_late is None:
        merged["late_scratch_risk"] = primary_late
    else:
        merged["late_scratch_risk"] = max(float(primary_late), float(fallback_late))

    primary_confidence = primary.get("pregame_context_confidence")
    fallback_confidence = fallback.get("pregame_context_confidence")
    if primary_confidence is None:
        merged["pregame_context_confidence"] = fallback_confidence
    elif fallback_confidence is None:
        merged["pregame_context_confidence"] = primary_confidence
    else:
        merged["pregame_context_confidence"] = max(float(primary_confidence), float(fallback_confidence))

    for key in ("teammate_out_count_top7", "teammate_out_count_top9"):
        primary_value = primary.get(key)
        fallback_value = fallback.get(key)
        if primary_value is None:
            merged[key] = fallback_value
        elif fallback_value is None:
            merged[key] = primary_value
        else:
            merged[key] = max(float(primary_value), float(fallback_value))

    return merged


def _build_pregame_context_aggregates(row: dict[str, Any] | None) -> dict[str, float | bool | None]:
    if row is None:
        return {
            "expected_start": None,
            "starter_confidence": None,
            "official_available": None,
            "projected_available": None,
            "late_scratch_risk": None,
            "teammate_out_count_top7": None,
            "teammate_out_count_top9": None,
            "missing_high_usage_teammates": None,
            "missing_primary_ballhandler": None,
            "missing_frontcourt_rotation_piece": None,
            "vacated_minutes_proxy": None,
            "vacated_usage_proxy": None,
            "projected_lineup_confirmed": None,
            "official_starter_flag": None,
            "pregame_context_confidence": None,
        }

    return {
        "expected_start": bool(row.get("expected_start")) if row.get("expected_start") is not None else None,
        "starter_confidence": float(row.get("starter_confidence")) if row.get("starter_confidence") is not None else None,
        "official_available": bool(row.get("official_available")) if row.get("official_available") is not None else None,
        "projected_available": bool(row.get("projected_available")) if row.get("projected_available") is not None else None,
        "late_scratch_risk": float(row.get("late_scratch_risk")) if row.get("late_scratch_risk") is not None else None,
        "teammate_out_count_top7": float(row.get("teammate_out_count_top7")) if row.get("teammate_out_count_top7") is not None else None,
        "teammate_out_count_top9": float(row.get("teammate_out_count_top9")) if row.get("teammate_out_count_top9") is not None else None,
        "missing_high_usage_teammates": float(row.get("missing_high_usage_teammates")) if row.get("missing_high_usage_teammates") is not None else None,
        "missing_primary_ballhandler": bool(row.get("missing_primary_ballhandler")) if row.get("missing_primary_ballhandler") is not None else None,
        "missing_frontcourt_rotation_piece": bool(row.get("missing_frontcourt_rotation_piece")) if row.get("missing_frontcourt_rotation_piece") is not None else None,
        "vacated_minutes_proxy": float(row.get("vacated_minutes_proxy")) if row.get("vacated_minutes_proxy") is not None else None,
        "vacated_usage_proxy": float(row.get("vacated_usage_proxy")) if row.get("vacated_usage_proxy") is not None else None,
        "projected_lineup_confirmed": bool(row.get("projected_lineup_confirmed")) if row.get("projected_lineup_confirmed") is not None else None,
        "official_starter_flag": bool(row.get("official_starter_flag")) if row.get("official_starter_flag") is not None else None,
        "pregame_context_confidence": float(row.get("pregame_context_confidence")) if row.get("pregame_context_confidence") is not None else None,
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

        pregame_context_index = build_pregame_context_index(load_pregame_context_feature_rows())
        official_injury_dates = sorted({(game.game_date if game and game.game_date else latest_captured_at).date() for game in games_by_id.values()} | {latest_captured_at.date()})
        official_injury_index = build_official_injury_report_index(
            load_latest_official_injury_report_rows(
                session,
                report_dates=official_injury_dates,
                captured_at=latest_captured_at,
            )
        )

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
            rotation_rows: list[PlayerRotationGame] = []
            game_ids = [log.game_id for log in recent_logs]
            if game_ids:
                advanced_by_game = {
                    row.game_id: row
                    for row in session.query(HistoricalAdvancedLog)
                    .filter(HistoricalAdvancedLog.player_id == market.player_id, HistoricalAdvancedLog.game_id.in_(game_ids))
                    .all()
                }
                advanced_rows = [advanced_by_game[log.game_id] for log in recent_logs if log.game_id in advanced_by_game]

                rotation_by_game = {
                    row.game_id: row
                    for row in session.query(PlayerRotationGame)
                    .filter(PlayerRotationGame.player_id == market.player_id, PlayerRotationGame.game_id.in_(game_ids))
                    .all()
                }
                rotation_rows = [rotation_by_game[log.game_id] for log in recent_logs if log.game_id in rotation_by_game]

            days_rest = None
            if latest_log.game_date and cutoff:
                days_rest = max((cutoff.date() - latest_log.game_date.date()).days, 0)

            opponent_team_id = team_id_by_abbreviation.get(opponent_abbreviation or "")
            team_team_id = team_id_by_abbreviation.get(team_abbreviation or "")
            opponent_defense = defense_by_team_id.get(opponent_team_id) if opponent_team_id else None
            team_defense = defense_by_team_id.get(team_team_id) if team_team_id else None
            report_game_date = cutoff.date() if isinstance(cutoff, datetime) else None
            pregame_context_row = match_pregame_context_row(
                pregame_context_index,
                game_id=market.game_id,
                player_id=market.player_id,
                team_abbreviation=team_abbreviation,
                player_name=market.player_name,
            )
            official_injury_row = match_official_injury_row(
                official_injury_index,
                game_date=report_game_date,
                player_id=market.player_id,
                team_abbreviation=team_abbreviation,
                player_name=market.player_name,
            )
            official_injury_team_summary = get_official_team_summary(
                official_injury_index,
                game_date=report_game_date,
                team_abbreviation=team_abbreviation,
            )

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
                    rotation_rows=rotation_rows,
                    team_defense=team_defense,
                    opponent_defense=opponent_defense,
                    league_avg_def_rating=league_avg_def_rating,
                    league_avg_pace=league_avg_pace,
                    league_avg_opponent_points=league_avg_opponent_points,
                    pregame_context_row=pregame_context_row,
                    official_injury_row=official_injury_row,
                    official_injury_team_summary=official_injury_team_summary,
                )
            )

    return seeds


def build_pregame_opportunity_features(captured_at: datetime | None = None, stat_type: str = "points", limit: int | None = None) -> list[PregameOpportunityFeatures]:
    seeds = load_pregame_feature_seeds(captured_at=captured_at, stat_type=stat_type, limit=limit)
    return [seed.build_opportunity_features() for seed in seeds]
