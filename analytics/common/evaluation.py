from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace as dataclass_replace
from datetime import date, datetime, timedelta
from math import sqrt
from statistics import mean, median
from typing import Any, Callable

from analytics.features_opportunity import PregameFeatureRequest, _build_absence_impact_index, _build_defense_context, build_pregame_feature_seed
from analytics.features_assists import build_pregame_assists_features_from_seed
from analytics.features_pregame import build_pregame_points_features_from_seed
from analytics.features_rebounds import build_pregame_rebounds_features_from_seed
from analytics.features_threes import build_pregame_threes_features_from_seed
from analytics.injury_report_loader import build_official_injury_report_index
from analytics.assists_model import project_pregame_assists
from analytics.opportunity_model import PregameOpportunityModelConfig, project_pregame_opportunity
from analytics.pregame_context_loader import build_pregame_context_index, load_pregame_context_snapshot_rows
from analytics.pregame_model import project_pregame_points
from analytics.rebounds_model import project_pregame_rebounds
from analytics.threes_model import project_pregame_threes
from database.db import session_scope
from database.models import (
    AbsenceImpactSummary,
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
    over_probability: float
    under_probability: float
    edge_over: float
    edge_under: float
    confidence: float
    recommended_side: str | None
    line_delta: float | None
    recommended_outcome: str | None
    pregame_context_attached: bool
    official_injury_attached: bool
    context_source: str
    absence_impact_sample_confidence: float | None
    absence_impact_source_count: float | None
    absence_impact_minutes_bonus: float
    absence_impact_usage_bonus: float
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
class PregamePointsDecisionBucket:
    label: str
    sample_size: int
    win_count: int
    loss_count: int
    push_count: int
    hit_rate: float
    avg_edge: float
    avg_confidence: float


@dataclass(slots=True)
class PregamePointsDecisionSummary:
    recommendation_count: int
    recommendation_rate: float
    win_count: int
    loss_count: int
    push_count: int
    graded_count: int
    hit_rate: float
    avg_edge: float
    avg_confidence: float
    over_recommendation_count: int
    under_recommendation_count: int
    confidence_buckets: list[PregamePointsDecisionBucket]
    edge_buckets: list[PregamePointsDecisionBucket]


@dataclass(slots=True)
class PregamePointsBacktestSummary:
    sample_size: int
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
    mae: float
    rmse: float
    bias: float
    median_abs_error: float
    within_two_points_pct: float
    within_four_points_pct: float
    projection_error: PregamePointsErrorSlice
    line_available_error: PregamePointsErrorSlice
    line_missing_error: PregamePointsErrorSlice
    decision_summary: PregamePointsDecisionSummary
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
    official_injury_attached: bool
    context_source: str
    absence_impact_sample_confidence: float | None
    absence_impact_source_count: float | None
    absence_impact_minutes_bonus: float
    absence_impact_usage_bonus: float
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
    official_injury_attached_count: int
    official_injury_attached_pct: float
    injury_only_context_count: int
    injury_only_context_pct: float
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


@dataclass(slots=True)
class PregameStatBacktestRow:
    game_id: str
    game_date: datetime
    player_id: str
    player_name: str
    team_abbreviation: str
    opponent_abbreviation: str
    stat_type: str
    projected_value: float
    actual_value: float
    actual_minutes: float | None
    expected_minutes: float | None
    error: float
    abs_error: float
    line: float | None
    line_available: bool
    over_probability: float
    under_probability: float
    edge_over: float
    edge_under: float
    confidence: float
    recommended_side: str | None
    line_delta: float | None
    recommended_outcome: str | None
    pregame_context_attached: bool
    official_injury_attached: bool
    context_source: str
    absence_impact_sample_confidence: float | None
    absence_impact_source_count: float | None
    absence_impact_minutes_bonus: float
    absence_impact_usage_bonus: float
    breakdown: dict[str, float]


@dataclass(slots=True)
class PregameStatBacktestSummary:
    stat_type: str
    sample_size: int
    line_available_count: int
    line_available_pct: float
    line_missing_count: int
    line_missing_pct: float
    pregame_context_attached_count: int
    pregame_context_attached_pct: float
    official_injury_attached_count: int
    official_injury_attached_pct: float
    mae: float
    rmse: float
    bias: float
    median_abs_error: float
    recommendation_count: int
    hit_rate: float
    largest_misses: list[dict[str, Any]]
    notes: list[str]


@dataclass(slots=True)
class PregameStatBacktestResult:
    summary: PregameStatBacktestSummary
    rows: list[PregameStatBacktestRow]


PregameReboundsBacktestRow = PregameStatBacktestRow
PregameAssistsBacktestRow = PregameStatBacktestRow
PregameThreesBacktestRow = PregameStatBacktestRow
PregameReboundsBacktestSummary = PregameStatBacktestSummary
PregameAssistsBacktestSummary = PregameStatBacktestSummary
PregameThreesBacktestSummary = PregameStatBacktestSummary
PregameReboundsBacktestResult = PregameStatBacktestResult
PregameAssistsBacktestResult = PregameStatBacktestResult
PregameThreesBacktestResult = PregameStatBacktestResult


@dataclass(slots=True)
class ContextAttachmentCoverage:
    pregame_context_attached_count: int
    official_injury_attached_count: int
    injury_only_context_count: int


@dataclass(slots=True)
class AbsenceImpactConfidenceBucketSummary:
    label: str
    sample_size: int
    mae: float
    avg_minutes_bonus: float
    avg_usage_bonus: float



def _season_from_game_date(game_date: datetime) -> str:
    if game_date.month >= 10:
        return f"{game_date.year}-{str(game_date.year + 1)[-2:]}"
    return f"{game_date.year - 1}-{str(game_date.year)[-2:]}"



def _round(value: float) -> float:
    return round(float(value), 4)



def _summarize_context_attachment(rows: list[Any]) -> ContextAttachmentCoverage:
    pregame_context_attached_count = 0
    official_injury_attached_count = 0
    injury_only_context_count = 0
    for row in rows:
        has_pregame_context = bool(getattr(row, "pregame_context_attached", False))
        has_official_injury = bool(getattr(row, "official_injury_attached", False))
        if has_pregame_context:
            pregame_context_attached_count += 1
        if has_official_injury:
            official_injury_attached_count += 1
        if has_official_injury and not has_pregame_context:
            injury_only_context_count += 1
    return ContextAttachmentCoverage(
        pregame_context_attached_count=pregame_context_attached_count,
        official_injury_attached_count=official_injury_attached_count,
        injury_only_context_count=injury_only_context_count,
    )



def _absence_impact_confidence_label(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value < 0.5:
        return "0.35-0.49"
    if value < 0.65:
        return "0.50-0.64"
    return "0.65+"



def _summarize_absence_impact_confidence_buckets(rows: list[Any], *, error_attr: str) -> list[AbsenceImpactConfidenceBucketSummary]:
    ordered_labels = ("0.35-0.49", "0.50-0.64", "0.65+", "unknown")
    bucket_rows: dict[str, list[Any]] = {label: [] for label in ordered_labels}
    for row in rows:
        bucket_rows[_absence_impact_confidence_label(getattr(row, "absence_impact_sample_confidence", None))].append(row)

    summaries: list[AbsenceImpactConfidenceBucketSummary] = []
    for label in ordered_labels:
        candidates = bucket_rows[label]
        error_values = [float(getattr(row, error_attr)) for row in candidates if getattr(row, error_attr) is not None]
        summaries.append(
            AbsenceImpactConfidenceBucketSummary(
                label=label,
                sample_size=len(candidates),
                mae=_round(mean(abs(value) for value in error_values)) if error_values else 0.0,
                avg_minutes_bonus=_round(mean(float(row.absence_impact_minutes_bonus) for row in candidates)) if candidates else 0.0,
                avg_usage_bonus=_round(mean(float(row.absence_impact_usage_bonus) for row in candidates)) if candidates else 0.0,
            )
        )
    return summaries



def _has_absence_impact_bonus(row: Any) -> bool:
    return abs(float(getattr(row, "absence_impact_minutes_bonus", 0.0) or 0.0)) > 0.0001 or abs(
        float(getattr(row, "absence_impact_usage_bonus", 0.0) or 0.0)
    ) > 0.0001



def summarize_points_absence_impact(rows: list[PregamePointsBacktestRow]) -> dict[str, Any]:
    affected_rows = [row for row in rows if _has_absence_impact_bonus(row)]
    minutes_affected_rows = [row for row in affected_rows if abs(float(row.absence_impact_minutes_bonus or 0.0)) > 0.0001]
    usage_only_rows = [
        row
        for row in affected_rows
        if abs(float(row.absence_impact_minutes_bonus or 0.0)) <= 0.0001 and abs(float(row.absence_impact_usage_bonus or 0.0)) > 0.0001
    ]
    unaffected_rows = [row for row in rows if not _has_absence_impact_bonus(row)]

    return {
        "affected_count": len(affected_rows),
        "affected_pct": _round(len(affected_rows) / len(rows)) if rows else 0.0,
        "minutes_affected_count": len(minutes_affected_rows),
        "minutes_affected_pct": _round(len(minutes_affected_rows) / len(rows)) if rows else 0.0,
        "usage_only_count": len(usage_only_rows),
        "usage_only_pct": _round(len(usage_only_rows) / len(rows)) if rows else 0.0,
        "affected_mae": _round(mean(row.abs_error for row in affected_rows)) if affected_rows else 0.0,
        "minutes_affected_mae": _round(mean(row.abs_error for row in minutes_affected_rows)) if minutes_affected_rows else 0.0,
        "usage_only_mae": _round(mean(row.abs_error for row in usage_only_rows)) if usage_only_rows else 0.0,
        "unaffected_mae": _round(mean(row.abs_error for row in unaffected_rows)) if unaffected_rows else 0.0,
        "confidence_buckets": _summarize_absence_impact_confidence_buckets(affected_rows, error_attr="error"),
        "largest_affected_misses": [
            {
                "game_id": row.game_id,
                "game_date": row.game_date.isoformat(),
                "player_name": row.player_name,
                "team_abbreviation": row.team_abbreviation,
                "opponent_abbreviation": row.opponent_abbreviation,
                "projected_points": row.projected_points,
                "actual_points": row.actual_points,
                "error": row.error,
                "abs_error": row.abs_error,
                "absence_impact_sample_confidence": row.absence_impact_sample_confidence,
                "absence_impact_source_count": row.absence_impact_source_count,
                "absence_impact_minutes_bonus": row.absence_impact_minutes_bonus,
                "absence_impact_usage_bonus": row.absence_impact_usage_bonus,
            }
            for row in sorted(affected_rows, key=lambda item: item.abs_error, reverse=True)[:10]
        ],
    }



def summarize_opportunity_absence_impact(rows: list[PregameOpportunityBacktestRow]) -> dict[str, Any]:
    affected_rows = [row for row in rows if _has_absence_impact_bonus(row)]
    minutes_affected_rows = [row for row in affected_rows if abs(float(row.absence_impact_minutes_bonus or 0.0)) > 0.0001]
    usage_only_rows = [
        row
        for row in affected_rows
        if abs(float(row.absence_impact_minutes_bonus or 0.0)) <= 0.0001 and abs(float(row.absence_impact_usage_bonus or 0.0)) > 0.0001
    ]
    unaffected_rows = [row for row in rows if not _has_absence_impact_bonus(row)]

    def _minutes_mae(candidates: list[PregameOpportunityBacktestRow]) -> float:
        values = [float(row.abs_minutes_error) for row in candidates if row.abs_minutes_error is not None]
        return _round(mean(values)) if values else 0.0

    return {
        "affected_count": len(affected_rows),
        "affected_pct": _round(len(affected_rows) / len(rows)) if rows else 0.0,
        "minutes_affected_count": len(minutes_affected_rows),
        "minutes_affected_pct": _round(len(minutes_affected_rows) / len(rows)) if rows else 0.0,
        "usage_only_count": len(usage_only_rows),
        "usage_only_pct": _round(len(usage_only_rows) / len(rows)) if rows else 0.0,
        "affected_minutes_mae": _minutes_mae(affected_rows),
        "minutes_affected_minutes_mae": _minutes_mae(minutes_affected_rows),
        "usage_only_minutes_mae": _minutes_mae(usage_only_rows),
        "unaffected_minutes_mae": _minutes_mae(unaffected_rows),
        "confidence_buckets": _summarize_absence_impact_confidence_buckets(affected_rows, error_attr="minutes_error"),
        "largest_affected_minutes_misses": [
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
                "context_source": row.context_source,
                "absence_impact_sample_confidence": row.absence_impact_sample_confidence,
                "absence_impact_source_count": row.absence_impact_source_count,
                "absence_impact_minutes_bonus": row.absence_impact_minutes_bonus,
                "absence_impact_usage_bonus": row.absence_impact_usage_bonus,
            }
            for row in sorted(affected_rows, key=lambda item: float(item.abs_minutes_error or 0.0), reverse=True)[:10]
        ],
    }



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



def _empty_points_decision_summary() -> PregamePointsDecisionSummary:
    return PregamePointsDecisionSummary(
        recommendation_count=0,
        recommendation_rate=0.0,
        win_count=0,
        loss_count=0,
        push_count=0,
        graded_count=0,
        hit_rate=0.0,
        avg_edge=0.0,
        avg_confidence=0.0,
        over_recommendation_count=0,
        under_recommendation_count=0,
        confidence_buckets=[],
        edge_buckets=[],
    )



def _grade_recommended_pick(row: PregamePointsBacktestRow) -> str | None:
    if not row.line_available or row.recommended_side is None or row.line is None:
        return None
    if row.actual_points > row.line:
        actual_side = "OVER"
    elif row.actual_points < row.line:
        actual_side = "UNDER"
    else:
        return "push"
    return "win" if row.recommended_side == actual_side else "loss"



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



def _summarize_decision_bucket(label: str, rows: list[PregamePointsBacktestRow]) -> PregamePointsDecisionBucket:
    wins = sum(1 for row in rows if row.recommended_outcome == "win")
    losses = sum(1 for row in rows if row.recommended_outcome == "loss")
    pushes = sum(1 for row in rows if row.recommended_outcome == "push")
    graded = wins + losses
    return PregamePointsDecisionBucket(
        label=label,
        sample_size=len(rows),
        win_count=wins,
        loss_count=losses,
        push_count=pushes,
        hit_rate=_round(wins / graded) if graded else 0.0,
        avg_edge=_round(mean(abs(row.edge_over) for row in rows)) if rows else 0.0,
        avg_confidence=_round(mean(row.confidence for row in rows)) if rows else 0.0,
    )



def _summarize_points_decisions(rows: list[PregamePointsBacktestRow]) -> PregamePointsDecisionSummary:
    recommended_rows = [row for row in rows if row.recommended_side is not None and row.line_available]
    if not recommended_rows:
        return _empty_points_decision_summary()

    confidence_bins = (0.0, 0.50, 0.60, 0.70, 0.80, 1.01)
    edge_bins = (0.0, 1.0, 2.0, 3.0, 5.0, 999.0)

    confidence_groups: dict[str, list[PregamePointsBacktestRow]] = defaultdict(list)
    edge_groups: dict[str, list[PregamePointsBacktestRow]] = defaultdict(list)
    for row in recommended_rows:
        confidence_groups[_bucket_label(row.confidence, confidence_bins, percent=True)].append(row)
        edge_groups[_bucket_label(abs(row.edge_over), edge_bins)].append(row)

    wins = sum(1 for row in recommended_rows if row.recommended_outcome == "win")
    losses = sum(1 for row in recommended_rows if row.recommended_outcome == "loss")
    pushes = sum(1 for row in recommended_rows if row.recommended_outcome == "push")
    graded = wins + losses

    return PregamePointsDecisionSummary(
        recommendation_count=len(recommended_rows),
        recommendation_rate=_round(len(recommended_rows) / len(rows)) if rows else 0.0,
        win_count=wins,
        loss_count=losses,
        push_count=pushes,
        graded_count=graded,
        hit_rate=_round(wins / graded) if graded else 0.0,
        avg_edge=_round(mean(abs(row.edge_over) for row in recommended_rows)),
        avg_confidence=_round(mean(row.confidence for row in recommended_rows)),
        over_recommendation_count=sum(1 for row in recommended_rows if row.recommended_side == "OVER"),
        under_recommendation_count=sum(1 for row in recommended_rows if row.recommended_side == "UNDER"),
        confidence_buckets=[
            _summarize_decision_bucket(label, bucket_rows)
            for label, bucket_rows in confidence_groups.items()
        ],
        edge_buckets=[
            _summarize_decision_bucket(label, bucket_rows)
            for label, bucket_rows in edge_groups.items()
        ],
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
    opportunity_config: PregameOpportunityModelConfig | None = None,
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
        absence_impact_rows = session.query(AbsenceImpactSummary).all()
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
    absence_impact_index = _build_absence_impact_index(absence_impact_rows)

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
                absence_impact_index=absence_impact_index,
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
            opportunity_projection = project_pregame_opportunity(features, config=opportunity_config) if opportunity_config is not None else project_pregame_opportunity(features)
            projection = project_pregame_points(features, opportunity_config=opportunity_config, opportunity_projection=opportunity_projection)
            if projection.breakdown.expected_minutes < min_expected_minutes:
                continue

            actual_points = float(target.points or 0.0)
            error = projection.projected_value - actual_points
            breakdown = projection.breakdown.to_dict()
            opportunity_breakdown = opportunity_projection.breakdown
            line_value = float(odds_row.line) if odds_row is not None else None
            line_delta = actual_points - line_value if line_value is not None else None
            row = PregamePointsBacktestRow(
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
                line=line_value,
                line_available=odds_row is not None,
                over_probability=float(projection.over_probability),
                under_probability=float(projection.under_probability),
                edge_over=float(projection.edge_over),
                edge_under=float(projection.edge_under),
                confidence=float(projection.confidence),
                recommended_side=projection.recommended_side,
                line_delta=_round(line_delta) if line_delta is not None else None,
                recommended_outcome=None,
                pregame_context_attached=bool(features.pregame_context_attached),
                official_injury_attached=bool(features.official_injury_attached),
                context_source=features.context_source or "none",
                absence_impact_sample_confidence=features.absence_impact_sample_confidence,
                absence_impact_source_count=features.absence_impact_source_count,
                absence_impact_minutes_bonus=float(opportunity_breakdown.absence_impact_minutes_bonus),
                absence_impact_usage_bonus=float(opportunity_breakdown.absence_impact_usage_bonus),
                recent_form_adjustment=float(breakdown.get("recent_form_adjustment", 0.0)),
                minutes_adjustment=float(breakdown.get("minutes_adjustment", 0.0)),
                usage_adjustment=float(breakdown.get("usage_adjustment", 0.0)),
                efficiency_adjustment=float(breakdown.get("efficiency_adjustment", 0.0)),
                opponent_adjustment=float(breakdown.get("opponent_adjustment", 0.0)),
                pace_adjustment=float(breakdown.get("pace_adjustment", 0.0)),
                context_adjustment=float(breakdown.get("context_adjustment", 0.0)),
                breakdown=breakdown,
            )
            row.recommended_outcome = _grade_recommended_pick(row)
            rows.append(row)
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
                official_injury_attached_count=0,
                official_injury_attached_pct=0.0,
                injury_only_context_count=0,
                injury_only_context_pct=0.0,
                mae=0.0,
                rmse=0.0,
                bias=0.0,
                median_abs_error=0.0,
                within_two_points_pct=0.0,
                within_four_points_pct=0.0,
                projection_error=_empty_points_error_slice(),
                line_available_error=_empty_points_error_slice(),
                line_missing_error=_empty_points_error_slice(),
                decision_summary=_empty_points_decision_summary(),
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
    decision_summary = _summarize_points_decisions(rows)
    line_available_count = len(line_available_rows)
    line_missing_count = len(line_missing_rows)
    context_coverage = _summarize_context_attachment(rows)
    pregame_context_attached_count = context_coverage.pregame_context_attached_count
    official_injury_attached_count = context_coverage.official_injury_attached_count
    injury_only_context_count = context_coverage.injury_only_context_count

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
            "official_injury_attached": row.official_injury_attached,
            "context_source": row.context_source,
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
    official_injury_attached_pct = official_injury_attached_count / len(rows)
    injury_only_context_pct = injury_only_context_count / len(rows)
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
    if injury_only_context_count > 0:
        notes.append("Some rows relied on official injury fallback without persisted pregame context, so lineup-aware validation still reflects a mixed context sample.")
    notes.append(f"Backtest excludes players whose projected pregame role stayed below {min_expected_minutes:.1f} expected minutes.")

    summary = PregamePointsBacktestSummary(
        sample_size=len(rows),
        line_available_count=line_available_count,
        line_available_pct=_round(line_available_pct),
        line_missing_count=line_missing_count,
        line_missing_pct=_round(line_missing_pct),
        pregame_context_attached_count=pregame_context_attached_count,
        pregame_context_attached_pct=_round(pregame_context_attached_pct),
        official_injury_attached_count=official_injury_attached_count,
        official_injury_attached_pct=_round(official_injury_attached_pct),
        injury_only_context_count=injury_only_context_count,
        injury_only_context_pct=_round(injury_only_context_pct),
        mae=projection_error.mae,
        rmse=projection_error.rmse,
        bias=projection_error.bias,
        median_abs_error=projection_error.median_abs_error,
        within_two_points_pct=projection_error.within_two_points_pct,
        within_four_points_pct=projection_error.within_four_points_pct,
        projection_error=projection_error,
        line_available_error=line_available_error,
        line_missing_error=line_missing_error,
        decision_summary=decision_summary,
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
    opportunity_config: PregameOpportunityModelConfig | None = None,
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
        absence_impact_rows = session.query(AbsenceImpactSummary).all()
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
    absence_impact_index = _build_absence_impact_index(absence_impact_rows)

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
                absence_impact_index=absence_impact_index,
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
            projection = project_pregame_opportunity(feature, config=opportunity_config) if opportunity_config is not None else project_pregame_opportunity(feature)
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
                    official_injury_attached=bool(feature.official_injury_attached),
                    context_source=feature.context_source or "none",
                    absence_impact_sample_confidence=feature.absence_impact_sample_confidence,
                    absence_impact_source_count=feature.absence_impact_source_count,
                    absence_impact_minutes_bonus=float(projection.breakdown.absence_impact_minutes_bonus),
                    absence_impact_usage_bonus=float(projection.breakdown.absence_impact_usage_bonus),
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
                official_injury_attached_count=0,
                official_injury_attached_pct=0.0,
                injury_only_context_count=0,
                injury_only_context_pct=0.0,
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
    context_coverage = _summarize_context_attachment(rows)
    pregame_context_attached_count = context_coverage.pregame_context_attached_count
    official_injury_attached_count = context_coverage.official_injury_attached_count
    injury_only_context_count = context_coverage.injury_only_context_count
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
            "official_injury_attached": row.official_injury_attached,
            "context_source": row.context_source,
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
    if injury_only_context_count > 0:
        notes.append("Some opportunity rows relied on official injury fallback without persisted pregame context, so lineup-aware role validation still reflects a mixed context sample.")
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
        official_injury_attached_count=official_injury_attached_count,
        official_injury_attached_pct=_round(official_injury_attached_count / len(rows)),
        injury_only_context_count=injury_only_context_count,
        injury_only_context_pct=_round(injury_only_context_count / len(rows)),
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


def _grade_recommended_stat_pick(row: PregameStatBacktestRow) -> str | None:
    if not row.line_available or row.recommended_side is None or row.line is None:
        return None
    if row.actual_value > row.line:
        return "win" if row.recommended_side == "OVER" else "loss"
    if row.actual_value < row.line:
        return "win" if row.recommended_side == "UNDER" else "loss"
    return "push"


def _backtest_pregame_stat(
    *,
    stat_type: str,
    actual_attr: str,
    feature_builder: Callable[[Any], Any],
    projector: Callable[[Any], Any],
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_history: int = 8,
    min_expected_minutes: float = 12.0,
    limit: int | None = None,
    max_minutes_before_tip: int | None = None,
    min_minutes_before_tip: int | None = None,
) -> PregameStatBacktestResult:
    start_date = start_date or datetime.min
    end_date = end_date or datetime.max

    target_column = getattr(HistoricalGameLog, actual_attr)
    with session_scope() as session:
        target_logs = (
            session.query(HistoricalGameLog)
            .filter(
                HistoricalGameLog.game_date >= start_date,
                HistoricalGameLog.game_date <= end_date,
                target_column.is_not(None),
            )
            .order_by(HistoricalGameLog.game_date.asc(), HistoricalGameLog.game_id.asc(), HistoricalGameLog.player_id.asc())
            .all()
        )
        all_logs = (
            session.query(HistoricalGameLog)
            .filter(target_column.is_not(None))
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
            .filter(OddsSnapshot.market_phase == "pregame", OddsSnapshot.stat_type == stat_type)
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
    absence_impact_index = _build_absence_impact_index(absence_impact_rows)

    rows: list[PregameStatBacktestRow] = []
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
                    stat_type=stat_type,
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
                absence_impact_index=absence_impact_index,
                team_role_prior_cache=team_role_prior_cache,
                logs_by_player=logs_by_player,
                advanced_by_player_game=advanced_by_player_game,
                rotation_by_player_game=rotation_by_player_game,
                logs_by_team=logs_by_team,
                rotation_by_team_game_player=rotation_by_team_game_player,
            )
            if seed is None or len(seed.recent_logs) < min_history:
                continue

            features = feature_builder(seed)
            projection = projector(features)
            if float(projection.breakdown.to_dict().get("expected_minutes", 0.0)) < min_expected_minutes:
                continue

            actual_value = float(getattr(target, actual_attr) or 0.0)
            error = projection.projected_value - actual_value
            breakdown = projection.breakdown.to_dict()
            line_value = float(odds_row.line) if odds_row is not None else None
            line_delta = actual_value - line_value if line_value is not None else None
            row = PregameStatBacktestRow(
                game_id=target.game_id,
                game_date=target.game_date,
                player_id=target.player_id,
                player_name=target.player_name,
                team_abbreviation=target.team,
                opponent_abbreviation=target.opponent,
                stat_type=stat_type,
                projected_value=projection.projected_value,
                actual_value=actual_value,
                actual_minutes=float(target.minutes) if target.minutes is not None else None,
                expected_minutes=float(breakdown.get("expected_minutes", 0.0)) if breakdown.get("expected_minutes") is not None else None,
                error=_round(error),
                abs_error=_round(abs(error)),
                line=line_value,
                line_available=odds_row is not None,
                over_probability=float(projection.over_probability),
                under_probability=float(projection.under_probability),
                edge_over=float(projection.edge_over),
                edge_under=float(projection.edge_under),
                confidence=float(projection.confidence),
                recommended_side=projection.recommended_side,
                line_delta=_round(line_delta) if line_delta is not None else None,
                recommended_outcome=None,
                pregame_context_attached=bool(features.pregame_context_attached),
                official_injury_attached=bool(features.official_injury_attached),
                context_source=features.context_source or "none",
                absence_impact_sample_confidence=features.absence_impact_sample_confidence,
                absence_impact_source_count=features.absence_impact_source_count,
                absence_impact_minutes_bonus=0.0,
                absence_impact_usage_bonus=0.0,
                breakdown=breakdown,
            )
            row.recommended_outcome = _grade_recommended_stat_pick(row)
            rows.append(row)
            if limit is not None and len(rows) >= limit:
                break

    if not rows:
        return PregameStatBacktestResult(
            summary=PregameStatBacktestSummary(
                stat_type=stat_type,
                sample_size=0,
                line_available_count=0,
                line_available_pct=0.0,
                line_missing_count=0,
                line_missing_pct=0.0,
                pregame_context_attached_count=0,
                pregame_context_attached_pct=0.0,
                official_injury_attached_count=0,
                official_injury_attached_pct=0.0,
                mae=0.0,
                rmse=0.0,
                bias=0.0,
                median_abs_error=0.0,
                recommendation_count=0,
                hit_rate=0.0,
                largest_misses=[],
                notes=[f"No eligible historical {stat_type} rows were found for the requested backtest window."],
            ),
            rows=[],
        )

    signed_errors = [row.error for row in rows]
    absolute_errors = [row.abs_error for row in rows]
    line_available_count = sum(1 for row in rows if row.line_available)
    pregame_context_attached_count = sum(1 for row in rows if row.pregame_context_attached)
    official_injury_attached_count = sum(1 for row in rows if row.official_injury_attached)
    graded_rows = [row for row in rows if row.recommended_outcome in {"win", "loss"}]
    recommendation_count = sum(1 for row in rows if row.recommended_side is not None)

    largest_misses = [
        {
            "game_id": row.game_id,
            "game_date": row.game_date.isoformat(),
            "player_name": row.player_name,
            "team_abbreviation": row.team_abbreviation,
            "opponent_abbreviation": row.opponent_abbreviation,
            "projected_value": row.projected_value,
            "actual_value": row.actual_value,
            "line": row.line,
            "error": row.error,
            "abs_error": row.abs_error,
            "confidence": row.confidence,
            "context_source": row.context_source,
        }
        for row in sorted(rows, key=lambda item: item.abs_error, reverse=True)[:10]
    ]
    notes = [f"{stat_type.title()} backtest excludes players whose projected pregame role stayed below {min_expected_minutes:.1f} expected minutes."]

    return PregameStatBacktestResult(
        summary=PregameStatBacktestSummary(
            stat_type=stat_type,
            sample_size=len(rows),
            line_available_count=line_available_count,
            line_available_pct=_round(line_available_count / len(rows)),
            line_missing_count=len(rows) - line_available_count,
            line_missing_pct=_round((len(rows) - line_available_count) / len(rows)),
            pregame_context_attached_count=pregame_context_attached_count,
            pregame_context_attached_pct=_round(pregame_context_attached_count / len(rows)),
            official_injury_attached_count=official_injury_attached_count,
            official_injury_attached_pct=_round(official_injury_attached_count / len(rows)),
            mae=_round(mean(absolute_errors)),
            rmse=_round(sqrt(mean(error ** 2 for error in signed_errors))),
            bias=_round(mean(signed_errors)),
            median_abs_error=_round(median(absolute_errors)),
            recommendation_count=recommendation_count,
            hit_rate=_round(sum(1 for row in graded_rows if row.recommended_outcome == "win") / len(graded_rows)) if graded_rows else 0.0,
            largest_misses=largest_misses,
            notes=notes,
        ),
        rows=rows,
    )


def backtest_pregame_rebounds(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_history: int = 8,
    min_expected_minutes: float = 12.0,
    limit: int | None = None,
    max_minutes_before_tip: int | None = None,
    min_minutes_before_tip: int | None = None,
) -> PregameReboundsBacktestResult:
    return _backtest_pregame_stat(
        stat_type="rebounds",
        actual_attr="rebounds",
        feature_builder=build_pregame_rebounds_features_from_seed,
        projector=project_pregame_rebounds,
        start_date=start_date,
        end_date=end_date,
        min_history=min_history,
        min_expected_minutes=min_expected_minutes,
        limit=limit,
        max_minutes_before_tip=max_minutes_before_tip,
        min_minutes_before_tip=min_minutes_before_tip,
    )


def backtest_pregame_assists(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_history: int = 8,
    min_expected_minutes: float = 12.0,
    limit: int | None = None,
    max_minutes_before_tip: int | None = None,
    min_minutes_before_tip: int | None = None,
) -> PregameAssistsBacktestResult:
    return _backtest_pregame_stat(
        stat_type="assists",
        actual_attr="assists",
        feature_builder=build_pregame_assists_features_from_seed,
        projector=project_pregame_assists,
        start_date=start_date,
        end_date=end_date,
        min_history=min_history,
        min_expected_minutes=min_expected_minutes,
        limit=limit,
        max_minutes_before_tip=max_minutes_before_tip,
        min_minutes_before_tip=min_minutes_before_tip,
    )


def backtest_pregame_threes(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_history: int = 8,
    min_expected_minutes: float = 12.0,
    limit: int | None = None,
    max_minutes_before_tip: int | None = None,
    min_minutes_before_tip: int | None = None,
) -> PregameThreesBacktestResult:
    return _backtest_pregame_stat(
        stat_type="threes",
        actual_attr="threes_made",
        feature_builder=build_pregame_threes_features_from_seed,
        projector=project_pregame_threes,
        start_date=start_date,
        end_date=end_date,
        min_history=min_history,
        min_expected_minutes=min_expected_minutes,
        limit=limit,
        max_minutes_before_tip=max_minutes_before_tip,
        min_minutes_before_tip=min_minutes_before_tip,
    )


def _row_projected_value(row: PregamePointsBacktestRow | PregameStatBacktestRow) -> float:
    return float(getattr(row, "projected_value", getattr(row, "projected_points", 0.0)))


def _row_actual_value(row: PregamePointsBacktestRow | PregameStatBacktestRow) -> float:
    return float(getattr(row, "actual_value", getattr(row, "actual_points", 0.0)))


def _row_line_value(row: PregamePointsBacktestRow | PregameStatBacktestRow) -> float | None:
    line = getattr(row, "line", None)
    return float(line) if line is not None else None


def compute_calibration_curve(
    rows: list[PregamePointsBacktestRow] | list[PregameStatBacktestRow],
    n_bins: int = 10,
) -> list[dict[str, float | int | None]]:
    if n_bins <= 0:
        raise ValueError("n_bins must be positive")

    buckets: list[list[PregamePointsBacktestRow | PregameStatBacktestRow]] = [[] for _ in range(n_bins)]
    for row in rows:
        confidence = max(0.0, min(float(getattr(row, "confidence", 0.0) or 0.0), 0.999999))
        bucket_index = min(int(confidence * n_bins), n_bins - 1)
        buckets[bucket_index].append(row)

    curve: list[dict[str, float | int | None]] = []
    for index, bucket in enumerate(buckets):
        lower = index / n_bins
        upper = (index + 1) / n_bins
        line_rows = [row for row in bucket if getattr(row, "line_available", False) and _row_line_value(row) is not None]
        closer_count = 0
        for row in line_rows:
            projected_error = abs(_row_projected_value(row) - _row_actual_value(row))
            line_error = abs(float(_row_line_value(row) or 0.0) - _row_actual_value(row))
            if projected_error < line_error:
                closer_count += 1

        graded_recommendations = [
            row
            for row in bucket
            if getattr(row, "recommended_side", None) is not None
            and getattr(row, "recommended_outcome", None) in {"win", "loss"}
        ]
        recommendation_hit_rate = (
            _round(
                sum(
                    1
                    for row in graded_recommendations
                    if getattr(row, "recommended_outcome", None) == "win"
                ) / len(graded_recommendations)
            )
            if graded_recommendations
            else None
        )

        curve.append(
            {
                "bin_label": f"{lower:.1f}-{upper:.1f}",
                "sample_count": len(bucket),
                "line_sample_count": len(line_rows),
                "mean_confidence": _round(mean(float(getattr(row, "confidence", 0.0) or 0.0) for row in bucket)) if bucket else 0.0,
                "actual_hit_rate": _round(closer_count / len(line_rows)) if line_rows else None,
                "recommendation_hit_rate": recommendation_hit_rate,
                "recommendation_count": len(graded_recommendations),
            }
        )
    return curve


def analyze_recommendation_thresholds(
    rows: list[PregamePointsBacktestRow] | list[PregameStatBacktestRow],
    edge_thresholds: list[float] = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
    confidence_thresholds: list[float] = [0.50, 0.55, 0.60, 0.65, 0.70],
) -> list[dict[str, float | int | None | str]]:
    analyses: list[dict[str, float | int | None | str]] = []
    line_rows = [row for row in rows if getattr(row, "line_available", False) and _row_line_value(row) is not None]
    for edge_threshold in edge_thresholds:
        for confidence_threshold in confidence_thresholds:
            qualified_rows: list[tuple[PregamePointsBacktestRow | PregameStatBacktestRow, str, float]] = []
            for row in line_rows:
                confidence = float(getattr(row, "confidence", 0.0) or 0.0)
                if confidence < confidence_threshold:
                    continue
                line = float(_row_line_value(row) or 0.0)
                projected_value = _row_projected_value(row)
                signed_edge = projected_value - line
                if abs(signed_edge) < edge_threshold:
                    continue
                side = "OVER" if signed_edge >= 0 else "UNDER"
                qualified_rows.append((row, side, abs(signed_edge)))

            graded_rows = []
            for row, side, edge in qualified_rows:
                actual_value = _row_actual_value(row)
                line = float(_row_line_value(row) or 0.0)
                if actual_value == line:
                    continue
                hit = actual_value > line if side == "OVER" else actual_value < line
                graded_rows.append((row, edge, hit))

            analyses.append(
                {
                    "edge_threshold": edge_threshold,
                    "confidence_threshold": confidence_threshold,
                    "qualified_count": len(qualified_rows),
                    "graded_count": len(graded_rows),
                    "hit_rate": _round(sum(1 for _, _, hit in graded_rows if hit) / len(graded_rows)) if graded_rows else None,
                    "average_edge": _round(mean(edge for _, edge, _ in graded_rows)) if graded_rows else 0.0,
                    "average_actual_error": _round(
                        mean(abs(_row_projected_value(row) - _row_actual_value(row)) for row, _, _ in graded_rows)
                    ) if graded_rows else 0.0,
                }
            )
    return analyses


def _zeroed_absence_impact_config() -> PregameOpportunityModelConfig:
    return dataclass_replace(
        PregameOpportunityModelConfig(),
        absence_impact_minutes_factor=0.0,
        absence_impact_usage_factor=0.0,
        absence_impact_touches_factor=0.0,
        absence_impact_passes_factor=0.0,
    )


@dataclass(slots=True)
class AbsenceImpactABRow:
    game_id: str
    game_date: datetime
    player_id: str
    player_name: str
    team_abbreviation: str
    opponent_abbreviation: str
    actual_points: float
    projected_with: float
    projected_without: float
    error_with: float
    error_without: float
    abs_error_with: float
    abs_error_without: float
    delta_abs_error: float
    absence_impact_minutes_bonus: float
    absence_impact_usage_bonus: float
    absence_impact_sample_confidence: float | None
    absence_impact_source_count: float | None


@dataclass(slots=True)
class AbsenceImpactABSummary:
    total_rows: int
    affected_rows: int
    affected_pct: float
    with_mae: float
    without_mae: float
    mae_delta: float
    with_bias: float
    without_bias: float
    bias_delta: float
    with_rmse: float
    without_rmse: float
    rmse_delta: float
    improved_count: int
    worsened_count: int
    unchanged_count: int
    improved_pct: float
    worsened_pct: float
    avg_improvement: float
    avg_worsening: float
    confidence_buckets: list[dict[str, Any]]
    top_improvements: list[dict[str, Any]]
    top_worsenings: list[dict[str, Any]]


def compare_absence_impact_ab(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_history: int = 8,
    limit: int | None = None,
) -> AbsenceImpactABSummary:
    result_with = backtest_pregame_points(
        start_date=start_date,
        end_date=end_date,
        min_history=min_history,
        limit=limit,
    )
    zeroed_config = _zeroed_absence_impact_config()
    result_without = backtest_pregame_points(
        start_date=start_date,
        end_date=end_date,
        min_history=min_history,
        limit=limit,
        opportunity_config=zeroed_config,
    )

    with_by_key = {(r.game_id, r.player_id): r for r in result_with.rows}
    without_by_key = {(r.game_id, r.player_id): r for r in result_without.rows}

    ab_rows: list[AbsenceImpactABRow] = []
    for key, row_with in with_by_key.items():
        if not _has_absence_impact_bonus(row_with):
            continue
        row_without = without_by_key.get(key)
        if row_without is None:
            continue
        delta = abs(row_with.error) - abs(row_without.error)
        ab_rows.append(
            AbsenceImpactABRow(
                game_id=row_with.game_id,
                game_date=row_with.game_date,
                player_id=row_with.player_id,
                player_name=row_with.player_name,
                team_abbreviation=row_with.team_abbreviation,
                opponent_abbreviation=row_with.opponent_abbreviation,
                actual_points=row_with.actual_points,
                projected_with=row_with.projected_points,
                projected_without=row_without.projected_points,
                error_with=row_with.error,
                error_without=row_without.error,
                abs_error_with=row_with.abs_error,
                abs_error_without=row_without.abs_error,
                delta_abs_error=_round(delta),
                absence_impact_minutes_bonus=row_with.absence_impact_minutes_bonus,
                absence_impact_usage_bonus=row_with.absence_impact_usage_bonus,
                absence_impact_sample_confidence=row_with.absence_impact_sample_confidence,
                absence_impact_source_count=row_with.absence_impact_source_count,
            )
        )

    if not ab_rows:
        return AbsenceImpactABSummary(
            total_rows=len(result_with.rows),
            affected_rows=0,
            affected_pct=0.0,
            with_mae=0.0, without_mae=0.0, mae_delta=0.0,
            with_bias=0.0, without_bias=0.0, bias_delta=0.0,
            with_rmse=0.0, without_rmse=0.0, rmse_delta=0.0,
            improved_count=0, worsened_count=0, unchanged_count=0,
            improved_pct=0.0, worsened_pct=0.0,
            avg_improvement=0.0, avg_worsening=0.0,
            confidence_buckets=[], top_improvements=[], top_worsenings=[],
        )

    with_mae = _round(mean(r.abs_error_with for r in ab_rows))
    without_mae = _round(mean(r.abs_error_without for r in ab_rows))
    with_bias = _round(mean(r.error_with for r in ab_rows))
    without_bias = _round(mean(r.error_without for r in ab_rows))
    with_rmse = _round(sqrt(mean(r.error_with ** 2 for r in ab_rows)))
    without_rmse = _round(sqrt(mean(r.error_without ** 2 for r in ab_rows)))

    improved = [r for r in ab_rows if r.delta_abs_error < -0.01]
    worsened = [r for r in ab_rows if r.delta_abs_error > 0.01]
    unchanged = [r for r in ab_rows if abs(r.delta_abs_error) <= 0.01]

    confidence_labels = ("0.35-0.49", "0.50-0.64", "0.65+", "unknown")
    buckets: list[dict[str, Any]] = []
    for label in confidence_labels:
        bucket = [r for r in ab_rows if _absence_impact_confidence_label(r.absence_impact_sample_confidence) == label]
        if not bucket:
            buckets.append({"label": label, "count": 0, "with_mae": 0.0, "without_mae": 0.0, "mae_delta": 0.0})
            continue
        b_with_mae = _round(mean(r.abs_error_with for r in bucket))
        b_without_mae = _round(mean(r.abs_error_without for r in bucket))
        buckets.append({
            "label": label,
            "count": len(bucket),
            "with_mae": b_with_mae,
            "without_mae": b_without_mae,
            "mae_delta": _round(b_with_mae - b_without_mae),
        })

    def _row_dict(r: AbsenceImpactABRow) -> dict[str, Any]:
        return {
            "game_id": r.game_id,
            "game_date": r.game_date.isoformat(),
            "player_name": r.player_name,
            "team_abbreviation": r.team_abbreviation,
            "actual_points": r.actual_points,
            "projected_with": r.projected_with,
            "projected_without": r.projected_without,
            "abs_error_with": r.abs_error_with,
            "abs_error_without": r.abs_error_without,
            "delta_abs_error": r.delta_abs_error,
            "absence_impact_minutes_bonus": r.absence_impact_minutes_bonus,
            "absence_impact_usage_bonus": r.absence_impact_usage_bonus,
            "absence_impact_sample_confidence": r.absence_impact_sample_confidence,
        }

    top_improvements = sorted(ab_rows, key=lambda r: r.delta_abs_error)[:10]
    top_worsenings = sorted(ab_rows, key=lambda r: r.delta_abs_error, reverse=True)[:10]

    return AbsenceImpactABSummary(
        total_rows=len(result_with.rows),
        affected_rows=len(ab_rows),
        affected_pct=_round(len(ab_rows) / len(result_with.rows)) if result_with.rows else 0.0,
        with_mae=with_mae,
        without_mae=without_mae,
        mae_delta=_round(with_mae - without_mae),
        with_bias=with_bias,
        without_bias=without_bias,
        bias_delta=_round(with_bias - without_bias),
        with_rmse=with_rmse,
        without_rmse=without_rmse,
        rmse_delta=_round(with_rmse - without_rmse),
        improved_count=len(improved),
        worsened_count=len(worsened),
        unchanged_count=len(unchanged),
        improved_pct=_round(len(improved) / len(ab_rows)),
        worsened_pct=_round(len(worsened) / len(ab_rows)),
        avg_improvement=_round(mean(r.delta_abs_error for r in improved)) if improved else 0.0,
        avg_worsening=_round(mean(r.delta_abs_error for r in worsened)) if worsened else 0.0,
        confidence_buckets=buckets,
        top_improvements=[_row_dict(r) for r in top_improvements],
        top_worsenings=[_row_dict(r) for r in top_worsenings],
    )

