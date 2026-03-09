from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from statistics import mean, median
from typing import Any

from analytics.features_opportunity import _build_shared_advanced_aggregates, _build_shared_log_aggregates
from analytics.features_pregame import PregamePointsFeatures, _build_points_advanced_aggregates, _build_points_log_aggregates
from analytics.pregame_model import project_pregame_points
from database.db import session_scope
from database.models import Game, HistoricalAdvancedLog, HistoricalGameLog, OddsSnapshot, Team, TeamDefensiveStat


@dataclass(slots=True)
class PregamePointsBacktestRow:
    game_id: str
    game_date: datetime
    player_id: str
    player_name: str
    team_abbreviation: str
    opponent_abbreviation: str
    projected_points: float
    actual_points: float
    actual_minutes: float | None
    expected_minutes: float | None
    error: float
    abs_error: float
    line: float | None
    line_available: bool
    recent_form_adjustment: float
    minutes_adjustment: float
    usage_adjustment: float
    efficiency_adjustment: float
    opponent_adjustment: float
    pace_adjustment: float
    context_adjustment: float
    breakdown: dict[str, float]


@dataclass(slots=True)
class PregamePointsBacktestSummary:
    sample_size: int
    line_available_count: int
    line_available_pct: float
    mae: float
    rmse: float
    bias: float
    median_abs_error: float
    within_two_points_pct: float
    within_four_points_pct: float
    average_absolute_recent_form_adjustment: float
    average_absolute_minutes_adjustment: float
    average_absolute_usage_adjustment: float
    average_absolute_efficiency_adjustment: float
    average_absolute_opponent_adjustment: float
    average_absolute_pace_adjustment: float
    average_absolute_context_adjustment: float
    largest_misses: list[dict[str, Any]]
    notes: list[str]


@dataclass(slots=True)
class PregamePointsBacktestResult:
    summary: PregamePointsBacktestSummary
    rows: list[PregamePointsBacktestRow]


def _season_from_game_date(game_date: datetime) -> str:
    if game_date.month >= 10:
        return f"{game_date.year}-{str(game_date.year + 1)[-2:]}"
    return f"{game_date.year - 1}-{str(game_date.year)[-2:]}"


def _round(value: float) -> float:
    return round(float(value), 4)


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


def backtest_pregame_points(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_history: int = 8,
    min_expected_minutes: float = 12.0,
    limit: int | None = None,
) -> PregamePointsBacktestResult:
    with session_scope() as session:
        target_query = session.query(HistoricalGameLog).filter(HistoricalGameLog.points.is_not(None))
        if start_date is not None:
            target_query = target_query.filter(HistoricalGameLog.game_date >= start_date)
        if end_date is not None:
            target_query = target_query.filter(HistoricalGameLog.game_date <= end_date)
        target_logs = target_query.order_by(HistoricalGameLog.game_date, HistoricalGameLog.game_id, HistoricalGameLog.player_name).all()

        all_logs = (
            session.query(HistoricalGameLog)
            .filter(HistoricalGameLog.points.is_not(None))
            .order_by(HistoricalGameLog.player_id, HistoricalGameLog.game_date, HistoricalGameLog.game_id)
            .all()
        )
        advanced_rows = session.query(HistoricalAdvancedLog).all()
        games = session.query(Game).all()
        teams = session.query(Team).all()
        team_defense_rows = session.query(TeamDefensiveStat).all()
        odds_rows = (
            session.query(OddsSnapshot)
            .filter(OddsSnapshot.market_phase == "pregame", OddsSnapshot.stat_type == "points")
            .order_by(OddsSnapshot.captured_at)
            .all()
        )

    logs_by_player: dict[str, list[HistoricalGameLog]] = defaultdict(list)
    log_index_by_player_game: dict[tuple[str, str], int] = {}
    for log in all_logs:
        player_logs = logs_by_player[log.player_id]
        log_index_by_player_game[(log.player_id, log.game_id)] = len(player_logs)
        player_logs.append(log)

    advanced_by_player_game = {(row.player_id, row.game_id): row for row in advanced_rows}
    games_by_id = {game.game_id: game for game in games}
    team_id_by_abbreviation = {team.abbreviation: team.team_id for team in teams if team.abbreviation}

    defense_by_season_team: dict[tuple[str, str], TeamDefensiveStat] = {}
    season_rows: dict[str, list[TeamDefensiveStat]] = defaultdict(list)
    for row in team_defense_rows:
        defense_by_season_team[(row.season, row.team_id)] = row
        season_rows[row.season].append(row)

    league_averages: dict[str, dict[str, float | None]] = {}
    for season, rows in season_rows.items():
        def_ratings = [float(row.defensive_rating) for row in rows if row.defensive_rating is not None]
        paces = [float(row.pace) for row in rows if row.pace is not None]
        opponent_points = [float(row.opponent_points_per_game) for row in rows if row.opponent_points_per_game is not None]
        league_averages[season] = {
            "def_rating": mean(def_ratings) if def_ratings else None,
            "pace": mean(paces) if paces else None,
            "opponent_points": mean(opponent_points) if opponent_points else None,
        }

    latest_odds_by_market: dict[tuple[str, str], OddsSnapshot] = {}
    for row in odds_rows:
        latest_odds_by_market[(row.game_id, row.player_id)] = row

    rows: list[PregamePointsBacktestRow] = []
    for target in target_logs:
        history = logs_by_player.get(target.player_id, [])
        history_index = log_index_by_player_game.get((target.player_id, target.game_id))
        if history_index is None or history_index < min_history:
            continue

        prior_logs = list(reversed(history[max(0, history_index - 15):history_index]))
        if len(prior_logs) < min_history:
            continue

        shared_log_aggregates = _build_shared_log_aggregates(prior_logs)
        expected_minutes_proxy = _weighted_average(
            [
                (0.50, shared_log_aggregates.get("season_minutes_avg")),
                (0.30, shared_log_aggregates.get("last10_minutes_avg")),
                (0.20, shared_log_aggregates.get("last5_minutes_avg")),
            ]
        )
        if expected_minutes_proxy is None or expected_minutes_proxy < min_expected_minutes:
            continue

        advanced_history = [
            advanced_by_player_game[(target.player_id, log.game_id)]
            for log in prior_logs
            if (target.player_id, log.game_id) in advanced_by_player_game
        ]
        shared_advanced_aggregates = _build_shared_advanced_aggregates(advanced_history)
        points_log_aggregates = _build_points_log_aggregates(prior_logs)
        points_advanced_aggregates = _build_points_advanced_aggregates(advanced_history)

        target_game = games_by_id.get(target.game_id)
        season = target_game.season if target_game and target_game.season else _season_from_game_date(target.game_date)
        opponent_team_id = team_id_by_abbreviation.get(target.opponent)
        opponent_row = defense_by_season_team.get((season, opponent_team_id)) if opponent_team_id else None
        league_row = league_averages.get(season, {})

        previous_game = prior_logs[0]
        days_rest = (target.game_date.date() - previous_game.game_date.date()).days if previous_game else None
        odds_row = latest_odds_by_market.get((target.game_id, target.player_id))

        feature = PregamePointsFeatures(
            game_id=target.game_id,
            player_id=target.player_id,
            player_name=target.player_name,
            line=float(odds_row.line) if odds_row is not None else float(target.points or 0.0),
            over_odds=int(odds_row.over_odds) if odds_row is not None else -110,
            under_odds=int(odds_row.under_odds) if odds_row is not None else -110,
            captured_at=target.game_date,
            game_date=target.game_date,
            team_abbreviation=target.team,
            opponent_abbreviation=target.opponent,
            is_home=target.is_home,
            days_rest=days_rest,
            back_to_back=bool(days_rest is not None and days_rest <= 1),
            team_pace=None,
            opponent_def_rating=float(opponent_row.defensive_rating) if opponent_row and opponent_row.defensive_rating is not None else None,
            opponent_pace=float(opponent_row.pace) if opponent_row and opponent_row.pace is not None else None,
            opponent_points_allowed=float(opponent_row.opponent_points_per_game) if opponent_row and opponent_row.opponent_points_per_game is not None else None,
            opponent_fg_pct_allowed=float(opponent_row.opponent_field_goal_percentage) if opponent_row and opponent_row.opponent_field_goal_percentage is not None else None,
            opponent_3pt_pct_allowed=float(opponent_row.opponent_three_point_percentage) if opponent_row and opponent_row.opponent_three_point_percentage is not None else None,
            league_avg_def_rating=league_row.get("def_rating"),
            league_avg_pace=league_row.get("pace"),
            league_avg_opponent_points=league_row.get("opponent_points"),
            **shared_log_aggregates,
            **shared_advanced_aggregates,
            **points_log_aggregates,
            **points_advanced_aggregates,
        )

        if target_game is not None:
            if target.team == target_game.home_team_abbreviation:
                team_team_id = target_game.home_team_id
            elif target.team == target_game.away_team_abbreviation:
                team_team_id = target_game.away_team_id
            else:
                team_team_id = team_id_by_abbreviation.get(target.team)
            team_row = defense_by_season_team.get((season, team_team_id)) if team_team_id else None
            if team_row and team_row.pace is not None:
                feature.team_pace = float(team_row.pace)

        projection = project_pregame_points(feature)
        actual_points = float(target.points or 0.0)
        error = projection.projected_value - actual_points
        breakdown = projection.breakdown.to_dict()
        rows.append(
            PregamePointsBacktestRow(
                game_id=target.game_id,
                game_date=target.game_date,
                player_id=target.player_id,
                player_name=target.player_name,
                team_abbreviation=target.team,
                opponent_abbreviation=target.opponent,
                projected_points=projection.projected_value,
                actual_points=actual_points,
                actual_minutes=float(target.minutes) if target.minutes is not None else None,
                expected_minutes=float(breakdown.get("expected_minutes", 0.0)) if breakdown.get("expected_minutes") is not None else expected_minutes_proxy,
                error=_round(error),
                abs_error=_round(abs(error)),
                line=float(odds_row.line) if odds_row is not None else None,
                line_available=odds_row is not None,
                recent_form_adjustment=float(breakdown.get("recent_form_adjustment", 0.0)),
                minutes_adjustment=float(breakdown.get("minutes_adjustment", 0.0)),
                usage_adjustment=float(breakdown.get("usage_adjustment", 0.0)),
                efficiency_adjustment=float(breakdown.get("efficiency_adjustment", 0.0)),
                opponent_adjustment=float(breakdown.get("opponent_adjustment", 0.0)),
                pace_adjustment=float(breakdown.get("pace_adjustment", 0.0)),
                context_adjustment=float(breakdown.get("context_adjustment", 0.0)),
                breakdown=breakdown,
            )
        )
        if limit is not None and len(rows) >= limit:
            break

    if not rows:
        notes = ["No eligible historical player games were found for the requested backtest window."]
        return PregamePointsBacktestResult(
            summary=PregamePointsBacktestSummary(
                sample_size=0,
                line_available_count=0,
                line_available_pct=0.0,
                mae=0.0,
                rmse=0.0,
                bias=0.0,
                median_abs_error=0.0,
                within_two_points_pct=0.0,
                within_four_points_pct=0.0,
                average_absolute_recent_form_adjustment=0.0,
                average_absolute_minutes_adjustment=0.0,
                average_absolute_usage_adjustment=0.0,
                average_absolute_efficiency_adjustment=0.0,
                average_absolute_opponent_adjustment=0.0,
                average_absolute_pace_adjustment=0.0,
                average_absolute_context_adjustment=0.0,
                largest_misses=[],
                notes=notes,
            ),
            rows=[],
        )

    absolute_errors = [row.abs_error for row in rows]
    signed_errors = [row.error for row in rows]
    squared_errors = [row.error ** 2 for row in rows]
    line_available_count = sum(1 for row in rows if row.line_available)
    line_available_pct = line_available_count / len(rows)

    def average_absolute_component(name: str) -> float:
        return _round(mean(abs(float(getattr(row, name))) for row in rows))

    largest_misses = [
        {
            "game_id": row.game_id,
            "game_date": row.game_date.isoformat(),
            "player_name": row.player_name,
            "team_abbreviation": row.team_abbreviation,
            "opponent_abbreviation": row.opponent_abbreviation,
            "projected_points": row.projected_points,
            "actual_points": row.actual_points,
            "actual_minutes": row.actual_minutes,
            "expected_minutes": row.expected_minutes,
            "error": row.error,
            "abs_error": row.abs_error,
        }
        for row in sorted(rows, key=lambda item: item.abs_error, reverse=True)[:10]
    ]

    notes = []
    if line_available_pct == 0:
        notes.append("No historical pregame points lines were available in the local database, so this backtest measures projection accuracy only.")
    elif line_available_pct < 0.10:
        notes.append("Historical pregame points line coverage is still too thin for a serious betting-edge backtest, so these results should be treated as projection-only validation.")
    if season_rows:
        notes.append("Opponent defense is evaluated from season-level team defensive stats, not daily snapshots, so older games may include mild lookahead bias in opponent context.")
    notes.append(f"Backtest excludes players whose pregame minutes profile projected below {min_expected_minutes:.1f} minutes to stay closer to real points-market availability.")

    summary = PregamePointsBacktestSummary(
        sample_size=len(rows),
        line_available_count=line_available_count,
        line_available_pct=_round(line_available_pct),
        mae=_round(mean(absolute_errors)),
        rmse=_round(sqrt(mean(squared_errors))),
        bias=_round(mean(signed_errors)),
        median_abs_error=_round(median(absolute_errors)),
        within_two_points_pct=_round(sum(1 for value in absolute_errors if value <= 2.0) / len(rows)),
        within_four_points_pct=_round(sum(1 for value in absolute_errors if value <= 4.0) / len(rows)),
        average_absolute_recent_form_adjustment=average_absolute_component("recent_form_adjustment"),
        average_absolute_minutes_adjustment=average_absolute_component("minutes_adjustment"),
        average_absolute_usage_adjustment=average_absolute_component("usage_adjustment"),
        average_absolute_efficiency_adjustment=average_absolute_component("efficiency_adjustment"),
        average_absolute_opponent_adjustment=average_absolute_component("opponent_adjustment"),
        average_absolute_pace_adjustment=average_absolute_component("pace_adjustment"),
        average_absolute_context_adjustment=average_absolute_component("context_adjustment"),
        largest_misses=largest_misses,
        notes=notes,
    )
    return PregamePointsBacktestResult(summary=summary, rows=rows)
