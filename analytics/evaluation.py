from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import sqrt
from statistics import mean, median
from typing import Any

from analytics.features_opportunity import PregameFeatureRequest, _build_defense_context, build_pregame_feature_seed
from analytics.features_pregame import build_pregame_points_features_from_seed
from analytics.injury_report_loader import build_official_injury_report_index
from analytics.opportunity_model import project_pregame_opportunity
from analytics.pregame_context_loader import build_pregame_context_index, load_pregame_context_snapshot_rows
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
    pregame_context_attached: bool
    recent_form_adjustment: float
    minutes_adjustment: float
    usage_adjustment: float
    efficiency_adjustment: float
    opponent_adjustment: float
    pace_adjustment: float
    context_adjustment: float
    breakdown: dict[str, float]


@dataclass(slots=True)
class PregamePointsErrorSlice:
    sample_size: int
    mae: float
    rmse: float
    bias: float
    median_abs_error: float
    within_two_points_pct: float
    within_four_points_pct: float


@dataclass(slots=True)
class PregamePointsBacktestSummary:
    sample_size: int
    line_available_count: int
    line_available_pct: float
    line_missing_count: int
    line_missing_pct: float
    pregame_context_attached_count: int
    pregame_context_attached_pct: float
    mae: float
    rmse: float
    bias: float
    median_abs_error: float
    within_two_points_pct: float
    within_four_points_pct: float
    projection_error: PregamePointsErrorSlice
    line_available_error: PregamePointsErrorSlice
    line_missing_error: PregamePointsErrorSlice
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
    pregame_context_attached: bool
    breakdown: dict[str, float]


@dataclass(slots=True)
class PregameOpportunityBacktestSummary:
    sample_size: int
    advanced_target_count: int
    advanced_target_pct: float
    rotation_target_count: int
    rotation_target_pct: float
    pregame_context_attached_count: int
    pregame_context_attached_pct: float
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



def _empty_points_error_slice() -> PregamePointsErrorSlice:
    return PregamePointsErrorSlice(
        sample_size=0,
        mae=0.0,
        rmse=0.0,
        bias=0.0,
        median_abs_error=0.0,
        within_two_points_pct=0.0,
        within_four_points_pct=0.0,
    )



def _summarize_points_errors(rows: list[PregamePointsBacktestRow]) -> PregamePointsErrorSlice:
    if not rows:
        return _empty_points_error_slice()

    absolute_errors = [row.abs_error for row in rows]
    signed_errors = [row.error for row in rows]
    squared_errors = [row.error ** 2 for row in rows]
    return PregamePointsErrorSlice(
        sample_size=len(rows),
        mae=_round(mean(absolute_errors)),
        rmse=_round(sqrt(mean(squared_errors))),
        bias=_round(mean(signed_errors)),
        median_abs_error=_round(median(absolute_errors)),
        within_two_points_pct=_round(sum(1 for value in absolute_errors if value <= 2.0) / len(rows)),
        within_four_points_pct=_round(sum(1 for value in absolute_errors if value <= 4.0) / len(rows)),
    )



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



def _sort_logs_desc(rows: list[HistoricalGameLog]) -> list[HistoricalGameLog]:
    return sorted(rows, key=lambda row: (row.game_date, row.game_id), reverse=True)



def _build_odds_index(rows: list[OddsSnapshot]) -> dict[tuple[str, str], list[OddsSnapshot]]:
    index: dict[tuple[str, str], list[OddsSnapshot]] = defaultdict(list)
    for row in rows:
        index[(row.game_id, row.player_id)].append(row)
    for snapshots in index.values():
        snapshots.sort(key=lambda row: row.captured_at)
    return index



def _select_latest_pregame_odds_snapshot(
    odds_index: dict[tuple[str, str], list[OddsSnapshot]],
    *,
    game_id: str,
    player_id: str,
    cutoff: datetime,
    max_minutes_before_tip: int | None = None,
    min_minutes_before_tip: int | None = None,
) -> OddsSnapshot | None:
    snapshots = odds_index.get((game_id, player_id), [])
    selected: OddsSnapshot | None = None
    for snapshot in snapshots:
        if snapshot.captured_at > cutoff:
            break
        delta_minutes = (cutoff - snapshot.captured_at).total_seconds() / 60.0
        if max_minutes_before_tip is not None and delta_minutes > max_minutes_before_tip:
            continue
        if min_minutes_before_tip is not None and delta_minutes < min_minutes_before_tip:
            continue
        selected = snapshot
    return selected



def _target_context_time(game: Game | None, target_log: HistoricalGameLog) -> datetime:
    if game is not None and game.game_time_utc is not None:
        return game.game_time_utc
    if game is not None and game.game_date is not None:
        return game.game_date
    return target_log.game_date



def _compute_error(expected: float, actual: float | None) -> tuple[float | None, float | None]:
    if actual is None:
        return None, None
    delta = expected - actual
    return _round(delta), _round(abs(delta))


def backtest_pregame_points(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_history: int = 8,
    min_expected_minutes: float = 12.0,
    limit: int | None = None,
    max_minutes_before_tip: int | None = None,
    min_minutes_before_tip: int | None = None,
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
        rotation_rows = session.query(PlayerRotationGame).all()
        games = session.query(Game).all()
        teams = session.query(Team).all()
        team_defense_rows = session.query(TeamDefensiveStat).all()
        odds_rows = (
            session.query(OddsSnapshot)
            .filter(OddsSnapshot.market_phase == "pregame", OddsSnapshot.stat_type == "points")
            .order_by(OddsSnapshot.captured_at)
            .all()
        )

        target_game_ids = sorted({log.game_id for log in target_logs})
        max_target_datetime = max((_target_context_time(next((game for game in games if game.game_id == log.game_id), None), log) for log in target_logs), default=None)
        pregame_context_rows = load_pregame_context_snapshot_rows(
            session,
            game_ids=target_game_ids,
            captured_at=max_target_datetime,
        )

        target_game_dates = sorted({_target_context_time(next((game for game in games if game.game_id == log.game_id), None), log).date() for log in target_logs})
        injury_entries: list[OfficialInjuryReportEntry] = []
        if target_game_dates and max_target_datetime is not None:
            injury_entries = (
                session.query(OfficialInjuryReportEntry)
                .filter(
                    OfficialInjuryReportEntry.game_date.in_(target_game_dates),
                    OfficialInjuryReportEntry.report_datetime_utc <= max_target_datetime,
                )
                .all()
            )

    games_by_id = {game.game_id: game for game in games}
    team_id_by_abbreviation = {team.abbreviation: team.team_id for team in teams if team.abbreviation}
    defense_by_season_team, league_avg_def_rating_by_season, league_avg_pace_by_season, league_avg_opponent_points_by_season = _build_defense_context(team_defense_rows)
    odds_index = _build_odds_index(odds_rows)
    pregame_context_index = build_pregame_context_index(pregame_context_rows)

    logs_by_player: dict[str, list[HistoricalGameLog]] = defaultdict(list)
    logs_by_team: dict[str, list[HistoricalGameLog]] = defaultdict(list)
    for log in all_logs:
        logs_by_player[log.player_id].append(log)
        logs_by_team[log.team].append(log)

    advanced_by_player_game = {(row.player_id, row.game_id): row for row in advanced_rows}
    rotation_by_player_game = {(row.player_id, row.game_id): row for row in rotation_rows}
    rotation_by_team_game_player = {(row.team_id, row.game_id, row.player_id): row for row in rotation_rows if row.team_id}
    injury_rows_by_report_id, injury_report_refs_by_game_date = _build_historical_injury_report_indexes(injury_entries)
    injury_index_cache: dict[int, Any] = {}
    team_role_prior_cache: dict[tuple[str, str], Any] = {}

    rows: list[PregamePointsBacktestRow] = []
    with session_scope() as session:
        for target in target_logs:
            target_game = games_by_id.get(target.game_id)
            target_context_time = _target_context_time(target_game, target)
            odds_row = _select_latest_pregame_odds_snapshot(
                odds_index,
                game_id=target.game_id,
                player_id=target.player_id,
                cutoff=target_context_time,
                max_minutes_before_tip=max_minutes_before_tip,
                min_minutes_before_tip=min_minutes_before_tip,
            )
            request_captured_at = odds_row.captured_at if odds_row is not None else target_context_time
            injury_index = _select_historical_injury_index(
                game_date=target_context_time.date(),
                captured_at=request_captured_at,
                rows_by_report_id=injury_rows_by_report_id,
                report_refs_by_game_date=injury_report_refs_by_game_date,
                index_cache=injury_index_cache,
            )
            seed = build_pregame_feature_seed(
                session,
                PregameFeatureRequest(
                    game_id=target.game_id,
                    player_id=target.player_id,
                    player_name=target.player_name,
                    stat_type="points",
                    captured_at=request_captured_at,
                    line=float(odds_row.line) if odds_row is not None else 0.0,
                    over_odds=int(odds_row.over_odds) if odds_row is not None else 0,
                    under_odds=int(odds_row.under_odds) if odds_row is not None else 0,
                    game_date=target_context_time,
                    team_abbreviation=target.team,
                    opponent_abbreviation=target.opponent,
                    is_home=target.is_home,
                ),
                games_by_id=games_by_id,
                team_id_by_abbreviation=team_id_by_abbreviation,
                defense_by_season_team=defense_by_season_team,
                league_avg_def_rating_by_season=league_avg_def_rating_by_season,
                league_avg_pace_by_season=league_avg_pace_by_season,
                league_avg_opponent_points_by_season=league_avg_opponent_points_by_season,
                pregame_context_index=pregame_context_index,
                official_injury_index=injury_index,
                team_role_prior_cache=team_role_prior_cache,
                logs_by_player=logs_by_player,
                advanced_by_player_game=advanced_by_player_game,
                rotation_by_player_game=rotation_by_player_game,
                logs_by_team=logs_by_team,
                rotation_by_team_game_player=rotation_by_team_game_player,
            )
            if seed is None or len(seed.recent_logs) < min_history:
                continue

            features = build_pregame_points_features_from_seed(seed)
            projection = project_pregame_points(features)
            if projection.breakdown.expected_minutes < min_expected_minutes:
                continue

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
                    expected_minutes=float(breakdown.get("expected_minutes", 0.0)) if breakdown.get("expected_minutes") is not None else None,
                    error=_round(error),
                    abs_error=_round(abs(error)),
                    line=float(odds_row.line) if odds_row is not None else None,
                    line_available=odds_row is not None,
                    pregame_context_attached=bool(features.pregame_context_attached),
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
                line_missing_count=0,
                line_missing_pct=0.0,
                pregame_context_attached_count=0,
                pregame_context_attached_pct=0.0,
                mae=0.0,
                rmse=0.0,
                bias=0.0,
                median_abs_error=0.0,
                within_two_points_pct=0.0,
                within_four_points_pct=0.0,
                projection_error=_empty_points_error_slice(),
                line_available_error=_empty_points_error_slice(),
                line_missing_error=_empty_points_error_slice(),
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

    projection_error = _summarize_points_errors(rows)
    line_available_rows = [row for row in rows if row.line_available]
    line_missing_rows = [row for row in rows if not row.line_available]
    line_available_error = _summarize_points_errors(line_available_rows)
    line_missing_error = _summarize_points_errors(line_missing_rows)
    line_available_count = len(line_available_rows)
    line_missing_count = len(line_missing_rows)
    pregame_context_attached_count = sum(1 for row in rows if row.pregame_context_attached)

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
            "pregame_context_attached": row.pregame_context_attached,
            "line_available": row.line_available,
            "error": row.error,
            "abs_error": row.abs_error,
        }
        for row in sorted(rows, key=lambda item: item.abs_error, reverse=True)[:10]
    ]

    notes = []
    line_available_pct = line_available_count / len(rows)
    line_missing_pct = line_missing_count / len(rows)
    pregame_context_attached_pct = pregame_context_attached_count / len(rows)
    if line_available_pct == 0:
        notes.append("No historical pregame points lines were available in the local database, so this backtest measures projection accuracy only.")
    elif line_available_pct < 0.10:
        notes.append("Historical pregame points line coverage is still too thin for a serious betting-edge backtest, so these results should be treated as projection-only validation.")
    elif line_missing_pct > 0:
        notes.append("Overall projection metrics cover all eligible rows; use the line-available and line-missing slices to separate market-covered validation from projection-only rows.")
    if pregame_context_attached_count == 0:
        notes.append("No persisted pregame context snapshots attached to this window, so context-aware validation is limited to injury and rotation signals only.")
    elif pregame_context_attached_pct < 0.9:
        notes.append("Persisted pregame context only covers part of this backtest window, so context-aware metrics reflect a mixed sample.")
    notes.append(f"Backtest excludes players whose projected pregame role stayed below {min_expected_minutes:.1f} expected minutes.")

    summary = PregamePointsBacktestSummary(
        sample_size=len(rows),
        line_available_count=line_available_count,
        line_available_pct=_round(line_available_pct),
        line_missing_count=line_missing_count,
        line_missing_pct=_round(line_missing_pct),
        pregame_context_attached_count=pregame_context_attached_count,
        pregame_context_attached_pct=_round(pregame_context_attached_pct),
        mae=projection_error.mae,
        rmse=projection_error.rmse,
        bias=projection_error.bias,
        median_abs_error=projection_error.median_abs_error,
        within_two_points_pct=projection_error.within_two_points_pct,
        within_four_points_pct=projection_error.within_four_points_pct,
        projection_error=projection_error,
        line_available_error=line_available_error,
        line_missing_error=line_missing_error,
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
    max_minutes_before_tip: int | None = None,
    min_minutes_before_tip: int | None = None,
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
        odds_rows = (
            session.query(OddsSnapshot)
            .filter(OddsSnapshot.market_phase == "pregame", OddsSnapshot.stat_type == "points")
            .order_by(OddsSnapshot.captured_at)
            .all()
        )

        target_game_ids = sorted({log.game_id for log in target_logs})
        max_target_datetime = max((_target_context_time(next((game for game in games if game.game_id == log.game_id), None), log) for log in target_logs), default=None)
        pregame_context_rows = load_pregame_context_snapshot_rows(
            session,
            game_ids=target_game_ids,
            captured_at=max_target_datetime,
        )

        target_game_dates = sorted({_target_context_time(next((game for game in games if game.game_id == log.game_id), None), log).date() for log in target_logs})
        injury_entries: list[OfficialInjuryReportEntry] = []
        if target_game_dates and max_target_datetime is not None:
            injury_entries = (
                session.query(OfficialInjuryReportEntry)
                .filter(
                    OfficialInjuryReportEntry.game_date.in_(target_game_dates),
                    OfficialInjuryReportEntry.report_datetime_utc <= max_target_datetime,
                )
                .all()
            )

    games_by_id = {game.game_id: game for game in games}
    team_id_by_abbreviation = {team.abbreviation: team.team_id for team in teams if team.abbreviation}
    defense_by_season_team, league_avg_def_rating_by_season, league_avg_pace_by_season, league_avg_opponent_points_by_season = _build_defense_context(team_defense_rows)
    odds_index = _build_odds_index(odds_rows)
    pregame_context_index = build_pregame_context_index(pregame_context_rows)

    logs_by_player: dict[str, list[HistoricalGameLog]] = defaultdict(list)
    logs_by_team: dict[str, list[HistoricalGameLog]] = defaultdict(list)
    for log in all_logs:
        logs_by_player[log.player_id].append(log)
        logs_by_team[log.team].append(log)

    advanced_by_player_game = {(row.player_id, row.game_id): row for row in advanced_rows}
    rotation_by_player_game = {(row.player_id, row.game_id): row for row in rotation_rows}
    rotation_by_team_game_player = {(row.team_id, row.game_id, row.player_id): row for row in rotation_rows if row.team_id}
    injury_rows_by_report_id, injury_report_refs_by_game_date = _build_historical_injury_report_indexes(injury_entries)
    injury_index_cache: dict[int, Any] = {}
    team_role_prior_cache: dict[tuple[str, str], Any] = {}

    rows: list[PregameOpportunityBacktestRow] = []
    with session_scope() as session:
        for target in target_logs:
            target_game = games_by_id.get(target.game_id)
            target_context_time = _target_context_time(target_game, target)
            odds_row = _select_latest_pregame_odds_snapshot(
                odds_index,
                game_id=target.game_id,
                player_id=target.player_id,
                cutoff=target_context_time,
                max_minutes_before_tip=max_minutes_before_tip,
                min_minutes_before_tip=min_minutes_before_tip,
            )
            request_captured_at = odds_row.captured_at if odds_row is not None else target_context_time
            injury_index = _select_historical_injury_index(
                game_date=target_context_time.date(),
                captured_at=request_captured_at,
                rows_by_report_id=injury_rows_by_report_id,
                report_refs_by_game_date=injury_report_refs_by_game_date,
                index_cache=injury_index_cache,
            )
            seed = build_pregame_feature_seed(
                session,
                PregameFeatureRequest(
                    game_id=target.game_id,
                    player_id=target.player_id,
                    player_name=target.player_name,
                    stat_type="points",
                    captured_at=request_captured_at,
                    line=float(odds_row.line) if odds_row is not None else 0.0,
                    over_odds=int(odds_row.over_odds) if odds_row is not None else 0,
                    under_odds=int(odds_row.under_odds) if odds_row is not None else 0,
                    game_date=target_context_time,
                    team_abbreviation=target.team,
                    opponent_abbreviation=target.opponent,
                    is_home=target.is_home,
                ),
                games_by_id=games_by_id,
                team_id_by_abbreviation=team_id_by_abbreviation,
                defense_by_season_team=defense_by_season_team,
                league_avg_def_rating_by_season=league_avg_def_rating_by_season,
                league_avg_pace_by_season=league_avg_pace_by_season,
                league_avg_opponent_points_by_season=league_avg_opponent_points_by_season,
                pregame_context_index=pregame_context_index,
                official_injury_index=injury_index,
                team_role_prior_cache=team_role_prior_cache,
                logs_by_player=logs_by_player,
                advanced_by_player_game=advanced_by_player_game,
                rotation_by_player_game=rotation_by_player_game,
                logs_by_team=logs_by_team,
                rotation_by_team_game_player=rotation_by_team_game_player,
            )
            if seed is None or len(seed.recent_logs) < min_history:
                continue

            feature = seed.build_opportunity_features()
            projection = project_pregame_opportunity(feature)
            if projection.breakdown.expected_minutes < min_expected_minutes:
                continue

            breakdown = projection.breakdown.to_dict()
            target_advanced = advanced_by_player_game.get((target.player_id, target.game_id))
            target_rotation = rotation_by_player_game.get((target.player_id, target.game_id))
            actual_minutes = float(target.minutes) if target.minutes is not None else None
            actual_usage_pct = float(target_advanced.usage_percentage) if target_advanced and target_advanced.usage_percentage is not None else None
            actual_est_usage_pct = float(target_advanced.estimated_usage_percentage) if target_advanced and target_advanced.estimated_usage_percentage is not None else None
            actual_touches = float(target_advanced.touches) if target_advanced and target_advanced.touches is not None else None
            actual_passes = float(target_advanced.passes) if target_advanced and target_advanced.passes is not None else None
            actual_stint_count = float(target_rotation.stint_count) if target_rotation and target_rotation.stint_count is not None else None
            actual_started = bool(target_rotation.started) if target_rotation and target_rotation.started is not None else None
            actual_closed = bool(target_rotation.closed_game) if target_rotation and target_rotation.closed_game is not None else None

            minutes_error, abs_minutes_error = _compute_error(float(breakdown["expected_minutes"]), actual_minutes)
            usage_error, abs_usage_error = _compute_error(float(breakdown["expected_usage_pct"]), actual_usage_pct)
            est_usage_error, abs_est_usage_error = _compute_error(float(breakdown["expected_est_usage_pct"]), actual_est_usage_pct)
            touches_error, abs_touches_error = _compute_error(float(breakdown["expected_touches"]), actual_touches)
            passes_error, abs_passes_error = _compute_error(float(breakdown["expected_passes"]), actual_passes)

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
                    pregame_context_attached=bool(feature.pregame_context_attached),
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
                pregame_context_attached_count=0,
                pregame_context_attached_pct=0.0,
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
    pregame_context_attached_count = sum(1 for row in rows if row.pregame_context_attached)
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
            "pregame_context_attached": row.pregame_context_attached,
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
        notes.append("No historical advanced logs were available for the target rows, so opportunity usage and touches could not be evaluated.")
    elif advanced_target_count / len(rows) < 0.9:
        notes.append("Historical advanced-log coverage is incomplete for some target rows, so usage and touches metrics reflect a partial sample.")
    if rotation_target_count == 0:
        notes.append("No target rotation rows were available, so starter and closer validation could not be evaluated.")
    elif rotation_target_count / len(rows) < 0.9:
        notes.append("Target rotation coverage is incomplete for some opportunity rows, so start and close accuracy reflects a partial sample.")
    if pregame_context_attached_count == 0:
        notes.append("No persisted pregame context snapshots attached to this opportunity window, so context-aware role validation is limited.")
    elif pregame_context_attached_count / len(rows) < 0.9:
        notes.append("Persisted pregame context only covers part of this opportunity backtest window, so context-aware opportunity metrics reflect a mixed sample.")
    if official_injury_team_context_count == 0:
        notes.append("No historical official injury context attached to the opportunity backtest rows, so injury-aware calibration could not be evaluated.")
    elif official_injury_team_context_count / len(rows) < 0.9:
        notes.append("Historical official injury coverage is partial for this backtest window, so injury-aware opportunity metrics reflect a mixed sample.")
    notes.append(f"Opportunity backtest excludes players whose projected pregame role stayed below {min_expected_minutes:.1f} expected minutes.")

    summary = PregameOpportunityBacktestSummary(
        sample_size=len(rows),
        advanced_target_count=advanced_target_count,
        advanced_target_pct=_round(advanced_target_count / len(rows)),
        rotation_target_count=rotation_target_count,
        rotation_target_pct=_round(rotation_target_count / len(rows)),
        pregame_context_attached_count=pregame_context_attached_count,
        pregame_context_attached_pct=_round(pregame_context_attached_count / len(rows)),
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
