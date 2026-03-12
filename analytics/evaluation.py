from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from math import sqrt
from statistics import mean, median
from typing import Any

from analytics.features_opportunity import (
    PregameOpportunityFeatures,
    _build_official_injury_aggregates,
    _build_rotation_aggregates,
    _build_shared_advanced_aggregates,
    _build_shared_log_aggregates,
)
from analytics.injury_report_loader import (
    build_official_injury_report_index,
    get_official_team_summary,
    match_official_injury_row,
)
from analytics.features_pregame import PregamePointsFeatures, _build_points_advanced_aggregates, _build_points_log_aggregates
from analytics.opportunity_model import project_pregame_opportunity
from analytics.pregame_model import project_pregame_points
from database.db import session_scope
from database.models import (
    Game,
    HistoricalAdvancedLog,
    HistoricalGameLog,
    OddsSnapshot,
    OfficialInjuryReportEntry,
    PlayerRotationGame,
    Team,
    TeamDefensiveStat,
)


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


@dataclass(slots=True)
class PregameOpportunityBacktestRow:
    game_id: str
    game_date: datetime
    player_id: str
    player_name: str
    team_abbreviation: str
    opponent_abbreviation: str
    expected_minutes: float
    expected_rotation_minutes: float
    actual_minutes: float | None
    minutes_error: float | None
    abs_minutes_error: float | None
    expected_usage_pct: float
    actual_usage_pct: float | None
    usage_error: float | None
    abs_usage_error: float | None
    expected_est_usage_pct: float
    actual_est_usage_pct: float | None
    est_usage_error: float | None
    abs_est_usage_error: float | None
    expected_touches: float
    actual_touches: float | None
    touches_error: float | None
    abs_touches_error: float | None
    expected_passes: float
    actual_passes: float | None
    passes_error: float | None
    abs_passes_error: float | None
    expected_stint_count: float
    actual_stint_count: float | None
    expected_start_rate: float
    actual_started: bool | None
    expected_close_rate: float
    actual_closed: bool | None
    role_stability: float
    rotation_role_score: float
    opportunity_score: float
    confidence: float
    official_injury_status: str | None
    official_report_datetime_utc: datetime | None
    official_teammate_out_count: float | None
    late_scratch_risk: float | None
    pregame_context_confidence: float | None
    breakdown: dict[str, float]


@dataclass(slots=True)
class PregameOpportunityBacktestSummary:
    sample_size: int
    advanced_target_count: int
    advanced_target_pct: float
    rotation_target_count: int
    rotation_target_pct: float
    minutes_mae: float
    minutes_rmse: float
    minutes_bias: float
    usage_mae: float
    est_usage_mae: float
    touches_mae: float
    passes_mae: float
    start_accuracy: float
    close_accuracy: float
    average_opportunity_score: float
    average_confidence: float
    official_injury_player_match_count: int
    official_injury_player_match_pct: float
    official_injury_team_context_count: int
    official_injury_team_context_pct: float
    official_injury_risk_count: int
    largest_minutes_misses: list[dict[str, Any]]
    notes: list[str]


@dataclass(slots=True)
class PregameOpportunityBacktestResult:
    summary: PregameOpportunityBacktestSummary
    rows: list[PregameOpportunityBacktestRow]


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


def _optional_errors(
    rows: list[Any],
    *,
    error_attr: str,
    abs_error_attr: str,
) -> tuple[list[float], list[float]]:
    signed = [float(getattr(row, error_attr)) for row in rows if getattr(row, error_attr) is not None]
    absolute = [float(getattr(row, abs_error_attr)) for row in rows if getattr(row, abs_error_attr) is not None]
    return signed, absolute


def _optional_accuracy(rows: list[Any], *, expected_attr: str, actual_attr: str, threshold: float = 0.5) -> tuple[int, float]:
    eligible = [row for row in rows if getattr(row, actual_attr) is not None]
    if not eligible:
        return 0, 0.0
    correct = sum(1 for row in eligible if (float(getattr(row, expected_attr)) >= threshold) == bool(getattr(row, actual_attr)))
    return len(eligible), correct / len(eligible)


def _build_historical_injury_report_indexes(
    rows: list[OfficialInjuryReportEntry],
) -> tuple[dict[int, list[dict[str, Any]]], dict[str, list[tuple[int, datetime]]]]:
    rows_by_report_id: dict[int, list[dict[str, Any]]] = defaultdict(list)
    report_refs_by_game_date: dict[str, dict[int, datetime]] = defaultdict(dict)

    for entry in rows:
        if entry.report_id is None:
            continue
        row = {
            "report_id": entry.report_id,
            "report_datetime_utc": entry.report_datetime_utc,
            "game_date": entry.game_date,
            "matchup": entry.matchup,
            "team_abbreviation": entry.team_abbreviation,
            "team_name": entry.team_name,
            "player_id": entry.player_id,
            "player_name": entry.player_name,
            "current_status": entry.current_status,
            "reason": entry.reason,
            "report_submitted": entry.report_submitted,
        }
        rows_by_report_id[int(entry.report_id)].append(row)
        if entry.game_date is not None and entry.report_datetime_utc is not None:
            report_refs_by_game_date[entry.game_date.isoformat()][int(entry.report_id)] = entry.report_datetime_utc

    sorted_report_refs = {
        game_date: sorted(refs.items(), key=lambda item: item[1])
        for game_date, refs in report_refs_by_game_date.items()
    }
    return rows_by_report_id, sorted_report_refs


def _select_historical_injury_index(
    *,
    game_date: date | None,
    captured_at: datetime,
    rows_by_report_id: dict[int, list[dict[str, Any]]],
    report_refs_by_game_date: dict[str, list[tuple[int, datetime]]],
    index_cache: dict[int, Any],
) -> Any | None:
    if game_date is None:
        return None

    refs = report_refs_by_game_date.get(game_date.isoformat(), [])
    selected_report_id: int | None = None
    for report_id, report_datetime in refs:
        if report_datetime <= captured_at:
            selected_report_id = int(report_id)
        else:
            break

    if selected_report_id is None:
        return None
    if selected_report_id not in index_cache:
        index_cache[selected_report_id] = build_official_injury_report_index(rows_by_report_id.get(selected_report_id, []))
    return index_cache[selected_report_id]


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



def backtest_pregame_opportunity(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_history: int = 8,
    min_expected_minutes: float = 8.0,
    limit: int | None = None,
) -> PregameOpportunityBacktestResult:
    with session_scope() as session:
        target_query = session.query(HistoricalGameLog).filter(HistoricalGameLog.minutes.is_not(None))
        if start_date is not None:
            target_query = target_query.filter(HistoricalGameLog.game_date >= start_date)
        if end_date is not None:
            target_query = target_query.filter(HistoricalGameLog.game_date <= end_date)
        target_logs = target_query.order_by(HistoricalGameLog.game_date, HistoricalGameLog.game_id, HistoricalGameLog.player_name).all()

        all_logs = (
            session.query(HistoricalGameLog)
            .filter(HistoricalGameLog.minutes.is_not(None))
            .order_by(HistoricalGameLog.player_id, HistoricalGameLog.game_date, HistoricalGameLog.game_id)
            .all()
        )
        advanced_rows = session.query(HistoricalAdvancedLog).all()
        rotation_rows = session.query(PlayerRotationGame).all()
        games = session.query(Game).all()
        teams = session.query(Team).all()
        team_defense_rows = session.query(TeamDefensiveStat).all()

        target_game_dates = sorted({log.game_date.date() for log in target_logs if log.game_date is not None})
        max_target_datetime = max((log.game_date for log in target_logs if log.game_date is not None), default=None)
        injury_entries = []
        if target_game_dates and max_target_datetime is not None:
            injury_entries = (
                session.query(OfficialInjuryReportEntry)
                .filter(
                    OfficialInjuryReportEntry.game_date.in_(target_game_dates),
                    OfficialInjuryReportEntry.report_datetime_utc <= max_target_datetime,
                )
                .all()
            )

    logs_by_player: dict[str, list[HistoricalGameLog]] = defaultdict(list)
    log_index_by_player_game: dict[tuple[str, str], int] = {}
    for log in all_logs:
        player_logs = logs_by_player[log.player_id]
        log_index_by_player_game[(log.player_id, log.game_id)] = len(player_logs)
        player_logs.append(log)

    advanced_by_player_game = {(row.player_id, row.game_id): row for row in advanced_rows}
    rotation_by_player_game = {(row.player_id, row.game_id): row for row in rotation_rows}
    games_by_id = {game.game_id: game for game in games}
    team_id_by_abbreviation = {team.abbreviation: team.team_id for team in teams if team.abbreviation}

    defense_by_season_team: dict[tuple[str, str], TeamDefensiveStat] = {}
    season_rows: dict[str, list[TeamDefensiveStat]] = defaultdict(list)
    for row in team_defense_rows:
        defense_by_season_team[(row.season, row.team_id)] = row
        season_rows[row.season].append(row)

    league_averages: dict[str, dict[str, float | None]] = {}
    for season, rows_for_season in season_rows.items():
        def_ratings = [float(row.defensive_rating) for row in rows_for_season if row.defensive_rating is not None]
        paces = [float(row.pace) for row in rows_for_season if row.pace is not None]
        opponent_points = [float(row.opponent_points_per_game) for row in rows_for_season if row.opponent_points_per_game is not None]
        league_averages[season] = {
            "def_rating": mean(def_ratings) if def_ratings else None,
            "pace": mean(paces) if paces else None,
            "opponent_points": mean(opponent_points) if opponent_points else None,
        }

    injury_rows_by_report_id, injury_report_refs_by_game_date = _build_historical_injury_report_indexes(injury_entries)
    injury_index_cache: dict[int, Any] = {}

    rows: list[PregameOpportunityBacktestRow] = []
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
        rotation_history = [
            rotation_by_player_game[(target.player_id, log.game_id)]
            for log in prior_logs
            if (target.player_id, log.game_id) in rotation_by_player_game
        ]

        shared_advanced_aggregates = _build_shared_advanced_aggregates(advanced_history)
        rotation_aggregates = _build_rotation_aggregates(rotation_history)

        target_game = games_by_id.get(target.game_id)
        target_context_time = (
            target_game.game_time_utc
            if target_game and target_game.game_time_utc is not None
            else target_game.game_date
            if target_game and target_game.game_date is not None
            else target.game_date
        )
        season = target_game.season if target_game and target_game.season else _season_from_game_date(target_context_time)
        opponent_team_id = team_id_by_abbreviation.get(target.opponent)
        opponent_row = defense_by_season_team.get((season, opponent_team_id)) if opponent_team_id else None
        league_row = league_averages.get(season, {})

        team_row = None
        if target_game is not None:
            if target.team == target_game.home_team_abbreviation:
                team_team_id = target_game.home_team_id
            elif target.team == target_game.away_team_abbreviation:
                team_team_id = target_game.away_team_id
            else:
                team_team_id = team_id_by_abbreviation.get(target.team)
            team_row = defense_by_season_team.get((season, team_team_id)) if team_team_id else None

        previous_game = prior_logs[0]
        days_rest = (target_context_time.date() - previous_game.game_date.date()).days if previous_game else None
        injury_index = _select_historical_injury_index(
            game_date=target_context_time.date() if target_context_time is not None else None,
            captured_at=target_context_time,
            rows_by_report_id=injury_rows_by_report_id,
            report_refs_by_game_date=injury_report_refs_by_game_date,
            index_cache=injury_index_cache,
        )
        official_injury_row = None
        official_injury_team_summary = None
        if injury_index is not None:
            official_injury_row = match_official_injury_row(
                injury_index,
                game_date=target_context_time.date() if target_context_time is not None else None,
                player_id=target.player_id,
                team_abbreviation=target.team,
                player_name=target.player_name,
            )
            official_injury_team_summary = get_official_team_summary(
                injury_index,
                game_date=target_context_time.date() if target_context_time is not None else None,
                team_abbreviation=target.team,
            )
        injury_aggregates = _build_official_injury_aggregates(
            official_injury_row,
            official_injury_team_summary,
            captured_at=target_context_time,
        )
        feature = PregameOpportunityFeatures(
            game_id=target.game_id,
            player_id=target.player_id,
            player_name=target.player_name,
            captured_at=target_context_time,
            game_date=target_context_time,
            team_abbreviation=target.team,
            opponent_abbreviation=target.opponent,
            is_home=target.is_home,
            days_rest=days_rest,
            back_to_back=bool(days_rest is not None and days_rest <= 1),
            team_pace=float(team_row.pace) if team_row and team_row.pace is not None else None,
            opponent_def_rating=float(opponent_row.defensive_rating) if opponent_row and opponent_row.defensive_rating is not None else None,
            opponent_pace=float(opponent_row.pace) if opponent_row and opponent_row.pace is not None else None,
            opponent_points_allowed=float(opponent_row.opponent_points_per_game) if opponent_row and opponent_row.opponent_points_per_game is not None else None,
            opponent_fg_pct_allowed=float(opponent_row.opponent_field_goal_percentage) if opponent_row and opponent_row.opponent_field_goal_percentage is not None else None,
            opponent_3pt_pct_allowed=float(opponent_row.opponent_three_point_percentage) if opponent_row and opponent_row.opponent_three_point_percentage is not None else None,
            league_avg_def_rating=league_row.get("def_rating"),
            league_avg_pace=league_row.get("pace"),
            league_avg_opponent_points=league_row.get("opponent_points"),
            **shared_log_aggregates,
            **rotation_aggregates,
            **shared_advanced_aggregates,
            **injury_aggregates,
        )
        projection = project_pregame_opportunity(feature)
        breakdown = projection.breakdown.to_dict()

        target_advanced = advanced_by_player_game.get((target.player_id, target.game_id))
        target_rotation = rotation_by_player_game.get((target.player_id, target.game_id))
        actual_minutes = float(target.minutes) if target.minutes is not None else None
        actual_usage_pct = float(target_advanced.usage_percentage) if target_advanced and target_advanced.usage_percentage is not None else None
        actual_est_usage_pct = (
            float(target_advanced.estimated_usage_percentage)
            if target_advanced and target_advanced.estimated_usage_percentage is not None
            else None
        )
        actual_touches = float(target_advanced.touches) if target_advanced and target_advanced.touches is not None else None
        actual_passes = float(target_advanced.passes) if target_advanced and target_advanced.passes is not None else None
        actual_stint_count = float(target_rotation.stint_count) if target_rotation and target_rotation.stint_count is not None else None
        actual_started = bool(target_rotation.started) if target_rotation and target_rotation.started is not None else None
        actual_closed = bool(target_rotation.closed_game) if target_rotation and target_rotation.closed_game is not None else None

        def compute_error(expected: float, actual: float | None) -> tuple[float | None, float | None]:
            if actual is None:
                return None, None
            delta = expected - actual
            return _round(delta), _round(abs(delta))

        minutes_error, abs_minutes_error = compute_error(float(breakdown["expected_minutes"]), actual_minutes)
        usage_error, abs_usage_error = compute_error(float(breakdown["expected_usage_pct"]), actual_usage_pct)
        est_usage_error, abs_est_usage_error = compute_error(float(breakdown["expected_est_usage_pct"]), actual_est_usage_pct)
        touches_error, abs_touches_error = compute_error(float(breakdown["expected_touches"]), actual_touches)
        passes_error, abs_passes_error = compute_error(float(breakdown["expected_passes"]), actual_passes)

        rows.append(
            PregameOpportunityBacktestRow(
                game_id=target.game_id,
                game_date=target.game_date,
                player_id=target.player_id,
                player_name=target.player_name,
                team_abbreviation=target.team,
                opponent_abbreviation=target.opponent,
                expected_minutes=float(breakdown["expected_minutes"]),
                expected_rotation_minutes=float(breakdown["expected_rotation_minutes"]),
                actual_minutes=actual_minutes,
                minutes_error=minutes_error,
                abs_minutes_error=abs_minutes_error,
                expected_usage_pct=float(breakdown["expected_usage_pct"]),
                actual_usage_pct=actual_usage_pct,
                usage_error=usage_error,
                abs_usage_error=abs_usage_error,
                expected_est_usage_pct=float(breakdown["expected_est_usage_pct"]),
                actual_est_usage_pct=actual_est_usage_pct,
                est_usage_error=est_usage_error,
                abs_est_usage_error=abs_est_usage_error,
                expected_touches=float(breakdown["expected_touches"]),
                actual_touches=actual_touches,
                touches_error=touches_error,
                abs_touches_error=abs_touches_error,
                expected_passes=float(breakdown["expected_passes"]),
                actual_passes=actual_passes,
                passes_error=passes_error,
                abs_passes_error=abs_passes_error,
                expected_stint_count=float(breakdown["expected_stint_count"]),
                actual_stint_count=actual_stint_count,
                expected_start_rate=float(breakdown["expected_start_rate"]),
                actual_started=actual_started,
                expected_close_rate=float(breakdown["expected_close_rate"]),
                actual_closed=actual_closed,
                role_stability=float(breakdown["role_stability"]),
                rotation_role_score=float(breakdown["rotation_role_score"]),
                opportunity_score=float(breakdown["opportunity_score"]),
                confidence=float(breakdown["confidence"]),
                official_injury_status=feature.official_injury_status,
                official_report_datetime_utc=feature.official_report_datetime_utc,
                official_teammate_out_count=feature.official_teammate_out_count,
                late_scratch_risk=feature.late_scratch_risk,
                pregame_context_confidence=feature.pregame_context_confidence,
                breakdown=breakdown,
            )
        )
        if limit is not None and len(rows) >= limit:
            break

    if not rows:
        notes = ["No eligible historical player games were found for the requested opportunity backtest window."]
        return PregameOpportunityBacktestResult(
            summary=PregameOpportunityBacktestSummary(
                sample_size=0,
                advanced_target_count=0,
                advanced_target_pct=0.0,
                rotation_target_count=0,
                rotation_target_pct=0.0,
                minutes_mae=0.0,
                minutes_rmse=0.0,
                minutes_bias=0.0,
                usage_mae=0.0,
                est_usage_mae=0.0,
                touches_mae=0.0,
                passes_mae=0.0,
                start_accuracy=0.0,
                close_accuracy=0.0,
                average_opportunity_score=0.0,
                average_confidence=0.0,
                official_injury_player_match_count=0,
                official_injury_player_match_pct=0.0,
                official_injury_team_context_count=0,
                official_injury_team_context_pct=0.0,
                official_injury_risk_count=0,
                largest_minutes_misses=[],
                notes=notes,
            ),
            rows=[],
        )

    minutes_signed_errors, minutes_absolute_errors = _optional_errors(rows, error_attr="minutes_error", abs_error_attr="abs_minutes_error")
    _, usage_absolute_errors = _optional_errors(rows, error_attr="usage_error", abs_error_attr="abs_usage_error")
    _, est_usage_absolute_errors = _optional_errors(rows, error_attr="est_usage_error", abs_error_attr="abs_est_usage_error")
    _, touches_absolute_errors = _optional_errors(rows, error_attr="touches_error", abs_error_attr="abs_touches_error")
    _, passes_absolute_errors = _optional_errors(rows, error_attr="passes_error", abs_error_attr="abs_passes_error")
    start_target_count, start_accuracy = _optional_accuracy(rows, expected_attr="expected_start_rate", actual_attr="actual_started")
    close_target_count, close_accuracy = _optional_accuracy(rows, expected_attr="expected_close_rate", actual_attr="actual_closed")

    advanced_target_count = sum(
        1
        for row in rows
        if row.actual_usage_pct is not None
        or row.actual_est_usage_pct is not None
        or row.actual_touches is not None
        or row.actual_passes is not None
    )
    rotation_target_count = sum(1 for row in rows if row.actual_started is not None or row.actual_closed is not None)
    official_injury_player_match_count = sum(1 for row in rows if row.official_injury_status is not None)
    official_injury_team_context_count = sum(1 for row in rows if row.official_teammate_out_count is not None)
    official_injury_risk_count = sum(
        1
        for row in rows
        if row.official_injury_status not in (None, "AVAILABLE")
        or (row.late_scratch_risk is not None and float(row.late_scratch_risk) >= 0.15)
    )

    largest_minutes_misses = [
        {
            "game_id": row.game_id,
            "game_date": row.game_date.isoformat(),
            "player_name": row.player_name,
            "team_abbreviation": row.team_abbreviation,
            "opponent_abbreviation": row.opponent_abbreviation,
            "expected_minutes": row.expected_minutes,
            "actual_minutes": row.actual_minutes,
            "minutes_error": row.minutes_error,
            "abs_minutes_error": row.abs_minutes_error,
            "expected_usage_pct": row.expected_usage_pct,
            "actual_usage_pct": row.actual_usage_pct,
            "expected_start_rate": row.expected_start_rate,
            "actual_started": row.actual_started,
            "expected_close_rate": row.expected_close_rate,
            "actual_closed": row.actual_closed,
            "opportunity_score": row.opportunity_score,
            "confidence": row.confidence,
            "official_injury_status": row.official_injury_status,
            "official_teammate_out_count": row.official_teammate_out_count,
            "late_scratch_risk": row.late_scratch_risk,
        }
        for row in sorted(
            rows,
            key=lambda item: float(item.abs_minutes_error) if item.abs_minutes_error is not None else -1.0,
            reverse=True,
        )[:10]
    ]

    notes = []
    if advanced_target_count == 0:
        notes.append("No historical advanced logs were available for the target rows, so opportunity usage/touches diagnostics could not be evaluated.")
    elif advanced_target_count / len(rows) < 0.9:
        notes.append("Historical advanced-log coverage is incomplete for some target rows, so usage and touches metrics reflect a partial sample.")
    if rotation_target_count == 0:
        notes.append("No target rotation rows were available, so starter/closer validation could not be evaluated.")
    elif rotation_target_count / len(rows) < 0.9:
        notes.append("Target rotation coverage is incomplete for some opportunity rows, so start/close accuracy reflects a partial sample.")
    if official_injury_team_context_count == 0:
        notes.append("No historical official injury context attached to the opportunity backtest rows, so injury-aware calibration could not be evaluated.")
    elif official_injury_team_context_count / len(rows) < 0.9:
        notes.append("Historical official injury coverage is partial for this backtest window, so injury-aware opportunity metrics reflect a mixed sample.")
    if season_rows:
        notes.append("Opponent context is still based on season-level team defensive stats rather than daily snapshots, so older opportunity rows may include mild lookahead bias.")
    notes.append(
        f"Opportunity backtest excludes players whose pregame minutes profile projected below {min_expected_minutes:.1f} minutes to stay focused on meaningful role predictions."
    )

    summary = PregameOpportunityBacktestSummary(
        sample_size=len(rows),
        advanced_target_count=advanced_target_count,
        advanced_target_pct=_round(advanced_target_count / len(rows)),
        rotation_target_count=rotation_target_count,
        rotation_target_pct=_round(rotation_target_count / len(rows)),
        minutes_mae=_round(mean(minutes_absolute_errors)) if minutes_absolute_errors else 0.0,
        minutes_rmse=_round(sqrt(mean(error ** 2 for error in minutes_signed_errors))) if minutes_signed_errors else 0.0,
        minutes_bias=_round(mean(minutes_signed_errors)) if minutes_signed_errors else 0.0,
        usage_mae=_round(mean(usage_absolute_errors)) if usage_absolute_errors else 0.0,
        est_usage_mae=_round(mean(est_usage_absolute_errors)) if est_usage_absolute_errors else 0.0,
        touches_mae=_round(mean(touches_absolute_errors)) if touches_absolute_errors else 0.0,
        passes_mae=_round(mean(passes_absolute_errors)) if passes_absolute_errors else 0.0,
        start_accuracy=_round(start_accuracy) if start_target_count else 0.0,
        close_accuracy=_round(close_accuracy) if close_target_count else 0.0,
        average_opportunity_score=_round(mean(row.opportunity_score for row in rows)),
        average_confidence=_round(mean(row.confidence for row in rows)),
        official_injury_player_match_count=official_injury_player_match_count,
        official_injury_player_match_pct=_round(official_injury_player_match_count / len(rows)),
        official_injury_team_context_count=official_injury_team_context_count,
        official_injury_team_context_pct=_round(official_injury_team_context_count / len(rows)),
        official_injury_risk_count=official_injury_risk_count,
        largest_minutes_misses=largest_minutes_misses,
        notes=notes,
    )
    return PregameOpportunityBacktestResult(summary=summary, rows=rows)
