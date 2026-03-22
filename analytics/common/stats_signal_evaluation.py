from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from statistics import mean
from typing import Any

from analytics.evaluation import (
    PregamePointsErrorSlice,
    _build_historical_injury_report_indexes,
    _build_odds_index,
    _empty_points_error_slice,
    _grade_recommended_pick,
    _round,
    _select_historical_injury_index,
    _select_latest_pregame_odds_snapshot,
    _sort_logs_desc,
    _summarize_context_attachment,
    _summarize_points_errors,
    _target_context_time,
)
from analytics.features_opportunity import (
    PregameFeatureRequest,
    _build_absence_impact_index,
    _build_defense_context,
    build_pregame_feature_seed,
)
from analytics.features_pregame import build_pregame_points_features_from_seed
from analytics.nba.signals_profile import (
    build_fallback_signal_profile,
    build_stats_signal_profile,
)
from analytics.nba.signals_readiness import build_signal_readiness
from analytics.pregame_context_loader import (
    build_pregame_context_index,
    load_pregame_context_snapshot_rows,
)
from database.db import session_scope
from database.models import (
    AbsenceImpactSummary,
    Game,
    HistoricalAdvancedLog,
    HistoricalGameLog,
    OddsSnapshot,
    OfficialInjuryReportEntry,
    PlayerPropSnapshot,
    PlayerRotationGame,
    Team,
    TeamDefensiveStat,
)


@dataclass(slots=True)
class StatsSignalCalibrationBucket:
    label: str
    sample_size: int
    win_count: int
    loss_count: int
    push_count: int
    hit_rate: float
    implied_hit_rate: float
    calibration_gap: float
    avg_edge: float
    avg_confidence: float


@dataclass(slots=True)
class StatsSignalDecisionSummary:
    recommendation_count: int
    recommendation_rate: float
    win_count: int
    loss_count: int
    push_count: int
    graded_count: int
    hit_rate: float
    implied_hit_rate: float
    calibration_gap: float
    avg_edge: float
    avg_confidence: float
    over_recommendation_count: int
    under_recommendation_count: int
    confidence_buckets: list[StatsSignalCalibrationBucket]
    edge_buckets: list[StatsSignalCalibrationBucket]


@dataclass(slots=True)
class StatsSignalProfileBucket:
    label: str
    sample_size: int
    recommendation_count: int
    graded_count: int
    hit_rate: float
    mae: float
    avg_confidence: float


@dataclass(slots=True)
class StatsSignalBacktestRow:
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
    line: float
    line_available: bool
    over_probability: float
    under_probability: float
    recommended_probability: float | None
    edge_over: float
    edge_under: float
    confidence: float
    recommended_side: str | None
    line_delta: float
    recommended_outcome: str | None
    recent_hit_rate: float | None
    recent_games_count: int
    key_factor: str | None
    pregame_context_attached: bool
    official_injury_attached: bool
    context_source: str
    readiness_status: str
    readiness_blocker_count: int
    readiness_warning_count: int
    using_fallback: bool
    breakdown: dict[str, float]


@dataclass(slots=True)
class StatsSignalBacktestSummary:
    sample_size: int
    candidate_count: int
    line_available_count: int
    line_available_pct: float
    line_missing_count: int
    line_missing_pct: float
    pregame_context_attached_count: int
    pregame_context_attached_pct: float
    official_injury_attached_count: int
    official_injury_attached_pct: float
    injury_only_context_count: int
    injury_only_context_pct: float
    readiness_ready_count: int
    readiness_limited_count: int
    readiness_blocked_count: int
    using_fallback_count: int
    mae: float
    rmse: float
    bias: float
    median_abs_error: float
    within_two_points_pct: float
    within_four_points_pct: float
    projection_error: PregamePointsErrorSlice
    decision_summary: StatsSignalDecisionSummary
    player_profile_buckets: list[StatsSignalProfileBucket]
    largest_misses: list[dict[str, Any]]
    notes: list[str]


@dataclass(slots=True)
class StatsSignalBacktestResult:
    summary: StatsSignalBacktestSummary
    rows: list[StatsSignalBacktestRow]


def _empty_decision_summary() -> StatsSignalDecisionSummary:
    return StatsSignalDecisionSummary(
        recommendation_count=0,
        recommendation_rate=0.0,
        win_count=0,
        loss_count=0,
        push_count=0,
        graded_count=0,
        hit_rate=0.0,
        implied_hit_rate=0.0,
        calibration_gap=0.0,
        avg_edge=0.0,
        avg_confidence=0.0,
        over_recommendation_count=0,
        under_recommendation_count=0,
        confidence_buckets=[],
        edge_buckets=[],
    )


def _bucket_label(value: float, bins: tuple[float, ...], *, percent: bool = False) -> str:
    for idx in range(len(bins) - 1):
        lower = bins[idx]
        upper = bins[idx + 1]
        if lower <= value < upper:
            if percent:
                return f"{int(lower * 100)}-{int(upper * 100)}%"
            if upper >= 999:
                return f">={lower:.1f}"
            return f"{lower:.1f}-{upper:.1f}"
    return f">={bins[-2]:.1f}"


def _summarize_calibration_bucket(
    label: str,
    rows: list[StatsSignalBacktestRow],
) -> StatsSignalCalibrationBucket:
    wins = sum(1 for row in rows if row.recommended_outcome == "win")
    losses = sum(1 for row in rows if row.recommended_outcome == "loss")
    pushes = sum(1 for row in rows if row.recommended_outcome == "push")
    graded = wins + losses
    implied_rows = [row.recommended_probability for row in rows if row.recommended_probability is not None]
    hit_rate = _round(wins / graded) if graded else 0.0
    implied_hit_rate = _round(mean(implied_rows)) if implied_rows else 0.0
    return StatsSignalCalibrationBucket(
        label=label,
        sample_size=len(rows),
        win_count=wins,
        loss_count=losses,
        push_count=pushes,
        hit_rate=hit_rate,
        implied_hit_rate=implied_hit_rate,
        calibration_gap=_round(hit_rate - implied_hit_rate),
        avg_edge=_round(mean(abs(row.edge_over) for row in rows)) if rows else 0.0,
        avg_confidence=_round(mean(row.confidence for row in rows)) if rows else 0.0,
    )


def summarize_stats_signal_decisions(
    rows: list[StatsSignalBacktestRow],
) -> StatsSignalDecisionSummary:
    recommended_rows = [row for row in rows if row.recommended_side is not None]
    if not recommended_rows:
        return _empty_decision_summary()

    confidence_bins = (0.0, 0.50, 0.60, 0.70, 0.80, 1.01)
    edge_bins = (0.0, 1.0, 2.0, 3.0, 5.0, 999.0)

    confidence_groups: dict[str, list[StatsSignalBacktestRow]] = defaultdict(list)
    edge_groups: dict[str, list[StatsSignalBacktestRow]] = defaultdict(list)
    for row in recommended_rows:
        confidence_groups[_bucket_label(row.confidence, confidence_bins, percent=True)].append(row)
        edge_groups[_bucket_label(abs(row.edge_over), edge_bins)].append(row)

    wins = sum(1 for row in recommended_rows if row.recommended_outcome == "win")
    losses = sum(1 for row in recommended_rows if row.recommended_outcome == "loss")
    pushes = sum(1 for row in recommended_rows if row.recommended_outcome == "push")
    graded = wins + losses
    implied_rows = [row.recommended_probability for row in recommended_rows if row.recommended_probability is not None]
    hit_rate = _round(wins / graded) if graded else 0.0
    implied_hit_rate = _round(mean(implied_rows)) if implied_rows else 0.0

    return StatsSignalDecisionSummary(
        recommendation_count=len(recommended_rows),
        recommendation_rate=_round(len(recommended_rows) / len(rows)) if rows else 0.0,
        win_count=wins,
        loss_count=losses,
        push_count=pushes,
        graded_count=graded,
        hit_rate=hit_rate,
        implied_hit_rate=implied_hit_rate,
        calibration_gap=_round(hit_rate - implied_hit_rate),
        avg_edge=_round(mean(abs(row.edge_over) for row in recommended_rows)),
        avg_confidence=_round(mean(row.confidence for row in recommended_rows)),
        over_recommendation_count=sum(1 for row in recommended_rows if row.recommended_side == "OVER"),
        under_recommendation_count=sum(1 for row in recommended_rows if row.recommended_side == "UNDER"),
        confidence_buckets=[
            _summarize_calibration_bucket(label, bucket_rows)
            for label, bucket_rows in confidence_groups.items()
        ],
        edge_buckets=[
            _summarize_calibration_bucket(label, bucket_rows)
            for label, bucket_rows in edge_groups.items()
        ],
    )


def _profile_bucket_label(expected_minutes: float | None) -> str:
    if expected_minutes is None:
        return "unknown"
    if expected_minutes < 24.0:
        return "under_24m"
    if expected_minutes < 32.0:
        return "24_to_32m"
    return "32m_plus"


def summarize_stats_signal_profile_buckets(
    rows: list[StatsSignalBacktestRow],
) -> list[StatsSignalProfileBucket]:
    ordered_labels = ("under_24m", "24_to_32m", "32m_plus", "unknown")
    grouped: dict[str, list[StatsSignalBacktestRow]] = {label: [] for label in ordered_labels}
    for row in rows:
        grouped[_profile_bucket_label(row.expected_minutes)].append(row)

    summaries: list[StatsSignalProfileBucket] = []
    for label in ordered_labels:
        bucket_rows = grouped[label]
        recommended_rows = [row for row in bucket_rows if row.recommended_side is not None]
        wins = sum(1 for row in recommended_rows if row.recommended_outcome == "win")
        losses = sum(1 for row in recommended_rows if row.recommended_outcome == "loss")
        graded = wins + losses
        summaries.append(
            StatsSignalProfileBucket(
                label=label,
                sample_size=len(bucket_rows),
                recommendation_count=len(recommended_rows),
                graded_count=graded,
                hit_rate=_round(wins / graded) if graded else 0.0,
                mae=_round(mean(row.abs_error for row in bucket_rows)) if bucket_rows else 0.0,
                avg_confidence=_round(mean(row.confidence for row in bucket_rows)) if bucket_rows else 0.0,
            )
        )
    return summaries


def _select_historical_injury_report_time(
    *,
    game_date: date | None,
    captured_at: datetime,
    report_refs_by_game_date: dict[str, list[tuple[int, datetime]]],
) -> datetime | None:
    if game_date is None:
        return None

    selected_report_at: datetime | None = None
    for _, report_datetime in report_refs_by_game_date.get(game_date.isoformat(), []):
        if report_datetime <= captured_at:
            selected_report_at = report_datetime
        else:
            break
    return selected_report_at


def backtest_stats_signal_points(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_history: int = 0,
    limit: int | None = None,
    max_minutes_before_tip: int | None = None,
    min_minutes_before_tip: int | None = None,
) -> StatsSignalBacktestResult:
    with session_scope() as session:
        target_query = session.query(HistoricalGameLog).filter(HistoricalGameLog.points.is_not(None))
        if start_date is not None:
            target_query = target_query.filter(HistoricalGameLog.game_date >= start_date)
        if end_date is not None:
            target_query = target_query.filter(HistoricalGameLog.game_date <= end_date)
        target_logs = target_query.order_by(
            HistoricalGameLog.game_date,
            HistoricalGameLog.game_id,
            HistoricalGameLog.player_name,
        ).all()

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
        absence_impact_rows = session.query(AbsenceImpactSummary).all()
        odds_rows = (
            session.query(OddsSnapshot)
            .filter(OddsSnapshot.market_phase == "pregame", OddsSnapshot.stat_type == "points")
            .order_by(OddsSnapshot.captured_at)
            .all()
        )

        target_game_ids = sorted({log.game_id for log in target_logs})
        max_target_datetime = max(
            (_target_context_time(next((game for game in games if game.game_id == log.game_id), None), log) for log in target_logs),
            default=None,
        )
        pregame_context_rows = load_pregame_context_snapshot_rows(
            session,
            game_ids=target_game_ids,
            captured_at=max_target_datetime,
        )

        target_game_dates = sorted(
            {_target_context_time(next((game for game in games if game.game_id == log.game_id), None), log).date() for log in target_logs}
        )
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
    absence_impact_index = _build_absence_impact_index(absence_impact_rows)

    rows: list[StatsSignalBacktestRow] = []
    line_missing_count = 0
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
            if odds_row is None:
                line_missing_count += 1
                continue

            request_captured_at = odds_row.captured_at
            latest_injury_report_at = _select_historical_injury_report_time(
                game_date=target_context_time.date(),
                captured_at=request_captured_at,
                report_refs_by_game_date=injury_report_refs_by_game_date,
            )
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
                    line=float(odds_row.line),
                    over_odds=int(odds_row.over_odds),
                    under_odds=int(odds_row.under_odds),
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
                absence_impact_index=absence_impact_index,
                team_role_prior_cache=team_role_prior_cache,
                logs_by_player=logs_by_player,
                advanced_by_player_game=advanced_by_player_game,
                rotation_by_player_game=rotation_by_player_game,
                logs_by_team=logs_by_team,
                rotation_by_team_game_player=rotation_by_team_game_player,
            )

            player_history = logs_by_player.get(target.player_id, [])
            prior_logs = _sort_logs_desc(
                [
                    log
                    for log in player_history
                    if (log.game_date, log.game_id) < (target.game_date, target.game_id)
                ]
            )
            if len(prior_logs) < min_history:
                continue

            snapshot = PlayerPropSnapshot(
                game_id=target.game_id,
                player_id=target.player_id,
                player_name=target.player_name,
                team=target.team,
                opponent=target.opponent,
                stat_type="points",
                line=float(odds_row.line),
                over_odds=int(odds_row.over_odds),
                under_odds=int(odds_row.under_odds),
                is_live=False,
                snapshot_phase="current",
                captured_at=request_captured_at,
            )

            if seed is None:
                features = None
                recent_logs = prior_logs
                profile = build_fallback_signal_profile(
                    snapshot,
                    target_game,
                    recent_logs=recent_logs,
                    injury_entries=[],
                )
                pregame_context_attached = False
                official_injury_attached = False
                context_source = "none"
            else:
                features = build_pregame_points_features_from_seed(seed)
                recent_logs = seed.recent_logs
                profile = build_stats_signal_profile(
                    features,
                    recent_logs=recent_logs,
                    injury_entries=[],
                )
                pregame_context_attached = bool(features.pregame_context_attached)
                official_injury_attached = bool(features.official_injury_attached)
                context_source = features.context_source or "none"

            readiness = build_signal_readiness(
                snapshot=snapshot,
                game=target_game,
                feature=features,
                recent_games_count=profile.recent_games_count,
                latest_injury_report_at=latest_injury_report_at,
                evaluation_time=request_captured_at,
            )
            if readiness.blockers:
                profile.recommended_side = None

            actual_points = float(target.points or 0.0)
            line_value = float(odds_row.line)
            line_delta = actual_points - line_value
            recommended_probability = None
            if profile.recommended_side == "OVER":
                recommended_probability = profile.over_probability
            elif profile.recommended_side == "UNDER":
                recommended_probability = profile.under_probability

            row = StatsSignalBacktestRow(
                game_id=target.game_id,
                game_date=target.game_date,
                player_id=target.player_id,
                player_name=target.player_name,
                team_abbreviation=target.team,
                opponent_abbreviation=target.opponent,
                projected_points=profile.projected_value,
                actual_points=actual_points,
                actual_minutes=float(target.minutes) if target.minutes is not None else None,
                expected_minutes=float(profile.breakdown.expected_minutes),
                error=_round(profile.projected_value - actual_points),
                abs_error=_round(abs(profile.projected_value - actual_points)),
                line=line_value,
                line_available=True,
                over_probability=profile.over_probability,
                under_probability=profile.under_probability,
                recommended_probability=recommended_probability,
                edge_over=profile.edge_over,
                edge_under=profile.edge_under,
                confidence=profile.confidence,
                recommended_side=profile.recommended_side,
                line_delta=_round(line_delta),
                recommended_outcome=None,
                recent_hit_rate=profile.recent_hit_rate,
                recent_games_count=profile.recent_games_count,
                key_factor=profile.key_factor,
                pregame_context_attached=pregame_context_attached,
                official_injury_attached=official_injury_attached,
                context_source=context_source,
                readiness_status=readiness.status,
                readiness_blocker_count=len(readiness.blockers),
                readiness_warning_count=len(readiness.warnings),
                using_fallback=readiness.using_fallback,
                breakdown=profile.breakdown.model_dump(),
            )
            row.recommended_outcome = _grade_recommended_pick(row)
            rows.append(row)
            if limit is not None and len(rows) >= limit:
                break

    candidate_count = len(rows) + line_missing_count
    if not rows:
        notes = ["No historical pregame points lines produced eligible stats-first signal rows for the requested window."]
        return StatsSignalBacktestResult(
            summary=StatsSignalBacktestSummary(
                sample_size=0,
                candidate_count=candidate_count,
                line_available_count=0,
                line_available_pct=0.0,
                line_missing_count=line_missing_count,
                line_missing_pct=_round(line_missing_count / candidate_count) if candidate_count else 0.0,
                pregame_context_attached_count=0,
                pregame_context_attached_pct=0.0,
                official_injury_attached_count=0,
                official_injury_attached_pct=0.0,
                injury_only_context_count=0,
                injury_only_context_pct=0.0,
                readiness_ready_count=0,
                readiness_limited_count=0,
                readiness_blocked_count=0,
                using_fallback_count=0,
                mae=0.0,
                rmse=0.0,
                bias=0.0,
                median_abs_error=0.0,
                within_two_points_pct=0.0,
                within_four_points_pct=0.0,
                projection_error=_empty_points_error_slice(),
                decision_summary=_empty_decision_summary(),
                player_profile_buckets=[],
                largest_misses=[],
                notes=notes,
            ),
            rows=[],
        )

    projection_error = _summarize_points_errors(rows)
    decision_summary = summarize_stats_signal_decisions(rows)
    profile_buckets = summarize_stats_signal_profile_buckets(rows)
    context_coverage = _summarize_context_attachment(rows)
    pregame_context_attached_count = context_coverage.pregame_context_attached_count
    official_injury_attached_count = context_coverage.official_injury_attached_count
    injury_only_context_count = context_coverage.injury_only_context_count
    readiness_ready_count = sum(1 for row in rows if row.readiness_status == "ready")
    readiness_limited_count = sum(1 for row in rows if row.readiness_status == "limited")
    readiness_blocked_count = sum(1 for row in rows if row.readiness_status == "blocked")
    using_fallback_count = sum(1 for row in rows if row.using_fallback)

    largest_misses = [
        {
            "game_id": row.game_id,
            "game_date": row.game_date.isoformat(),
            "player_name": row.player_name,
            "team_abbreviation": row.team_abbreviation,
            "opponent_abbreviation": row.opponent_abbreviation,
            "projected_points": row.projected_points,
            "actual_points": row.actual_points,
            "line": row.line,
            "readiness_status": row.readiness_status,
            "using_fallback": row.using_fallback,
            "context_source": row.context_source,
            "error": row.error,
            "abs_error": row.abs_error,
        }
        for row in sorted(rows, key=lambda item: item.abs_error, reverse=True)[:10]
    ]

    notes: list[str] = []
    line_missing_pct = (line_missing_count / candidate_count) if candidate_count else 0.0
    pregame_context_attached_pct = pregame_context_attached_count / len(rows)
    official_injury_attached_pct = official_injury_attached_count / len(rows)
    injury_only_context_pct = injury_only_context_count / len(rows)
    if line_missing_count > 0:
        notes.append(
            f"{line_missing_count} historical candidates were skipped because no pregame line was available in the local odds history."
        )
    if pregame_context_attached_count == 0:
        notes.append("No persisted pregame context snapshots attached to the stats-first backtest window.")
    elif pregame_context_attached_pct < 0.9:
        notes.append("Persisted pregame context only covers part of the stats-first backtest window.")
    if official_injury_attached_count == 0:
        notes.append("No historical official injury context attached to the evaluated stats-first signal rows.")
    elif official_injury_attached_pct < 0.9:
        notes.append("Historical official injury coverage is partial for the evaluated stats-first signal rows.")
    if readiness_blocked_count > 0:
        notes.append("Blocked rows are included for readiness tracking, but their recommendations were suppressed before grading.")
    if using_fallback_count > 0:
        notes.append("Some evaluated rows relied on fallback logic because a full pregame feature build was unavailable.")
    if decision_summary.recommendation_count == 0:
        notes.append("Current stats-first thresholds did not produce any graded recommendations for this window.")
    elif abs(decision_summary.calibration_gap) >= 0.08:
        notes.append("Confidence calibration gap is still material, so recommendation thresholds should be tuned before live expansion.")
    if line_missing_pct >= 0.5:
        notes.append("Historical line coverage is still thin for this window, so calibration conclusions should be treated as early.")

    summary = StatsSignalBacktestSummary(
        sample_size=len(rows),
        candidate_count=candidate_count,
        line_available_count=len(rows),
        line_available_pct=_round(len(rows) / candidate_count) if candidate_count else 0.0,
        line_missing_count=line_missing_count,
        line_missing_pct=_round(line_missing_pct) if candidate_count else 0.0,
        pregame_context_attached_count=pregame_context_attached_count,
        pregame_context_attached_pct=_round(pregame_context_attached_pct),
        official_injury_attached_count=official_injury_attached_count,
        official_injury_attached_pct=_round(official_injury_attached_pct),
        injury_only_context_count=injury_only_context_count,
        injury_only_context_pct=_round(injury_only_context_pct),
        readiness_ready_count=readiness_ready_count,
        readiness_limited_count=readiness_limited_count,
        readiness_blocked_count=readiness_blocked_count,
        using_fallback_count=using_fallback_count,
        mae=projection_error.mae,
        rmse=projection_error.rmse,
        bias=projection_error.bias,
        median_abs_error=projection_error.median_abs_error,
        within_two_points_pct=projection_error.within_two_points_pct,
        within_four_points_pct=projection_error.within_four_points_pct,
        projection_error=projection_error,
        decision_summary=decision_summary,
        player_profile_buckets=profile_buckets,
        largest_misses=largest_misses,
        notes=notes,
    )
    return StatsSignalBacktestResult(summary=summary, rows=rows)
