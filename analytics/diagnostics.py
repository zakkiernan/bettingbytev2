from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from analytics.evaluation import (
    PregameOpportunityBacktestResult,
    PregameOpportunityBacktestRow,
    PregamePointsBacktestResult,
    PregamePointsBacktestRow,
)


@dataclass(slots=True)
class PregamePointsMissBucket:
    label: str
    count: int
    pct: float


@dataclass(slots=True)
class PregamePointsMissAnalysis:
    top_miss_count: int
    buckets: list[PregamePointsMissBucket]
    examples: list[dict[str, object]]
    pregame_context_attached_count: int = 0
    pregame_context_missing_count: int = 0
    line_available_count: int = 0
    line_missing_count: int = 0
    with_pregame_context_buckets: list[PregamePointsMissBucket] | None = None
    without_pregame_context_buckets: list[PregamePointsMissBucket] | None = None
    with_line_buckets: list[PregamePointsMissBucket] | None = None
    without_line_buckets: list[PregamePointsMissBucket] | None = None


@dataclass(slots=True)
class PregameOpportunityMissBucket:
    label: str
    count: int
    pct: float


@dataclass(slots=True)
class PregameOpportunityMissAnalysis:
    top_miss_count: int
    buckets: list[PregameOpportunityMissBucket]
    examples: list[dict[str, object]]
    pregame_context_attached_count: int = 0
    pregame_context_missing_count: int = 0
    with_pregame_context_buckets: list[PregameOpportunityMissBucket] | None = None
    without_pregame_context_buckets: list[PregameOpportunityMissBucket] | None = None


def _classify_row(row: PregamePointsBacktestRow) -> str:
    if row.actual_minutes is not None and row.actual_minutes <= 5:
        return "availability_or_dnp"
    if row.expected_minutes is not None and row.actual_minutes is not None:
        if row.actual_minutes <= max(8.0, row.expected_minutes * 0.45):
            return "minutes_shortfall"
        if row.actual_minutes >= row.expected_minutes + 8.0:
            return "minutes_spike"
    if row.projected_points < row.actual_points and row.actual_points >= row.projected_points + 12.0:
        if row.actual_minutes is not None and row.expected_minutes is not None and row.actual_minutes >= row.expected_minutes - 2.0:
            return "scoring_outlier_upside"
    if row.projected_points > row.actual_points and row.actual_points <= row.projected_points - 12.0:
        if row.actual_minutes is not None and row.expected_minutes is not None and row.actual_minutes >= max(10.0, row.expected_minutes - 4.0):
            return "scoring_outlier_downside"
    if abs(row.opponent_adjustment) >= 1.0:
        return "opponent_adjustment_heavy"
    if abs(row.recent_form_adjustment) >= 1.5:
        return "recent_form_heavy"
    return "mixed"


def _classify_opportunity_row(row: PregameOpportunityBacktestRow) -> str:
    if row.actual_minutes is not None and row.actual_minutes <= 5.0:
        return "availability_or_dnp"
    if row.actual_minutes is not None:
        if row.actual_minutes <= max(8.0, row.expected_minutes * 0.45):
            return "minutes_shortfall"
        if row.actual_minutes >= row.expected_minutes + 8.0:
            return "minutes_spike"
    if row.actual_started is not None and (row.expected_start_rate >= 0.65) != row.actual_started:
        return "start_role_miss"
    if row.actual_closed is not None and (row.expected_close_rate >= 0.60) != row.actual_closed:
        return "close_role_miss"
    if row.actual_usage_pct is not None and row.abs_usage_error is not None and row.abs_usage_error >= 0.06:
        return "usage_miss"
    if row.actual_touches is not None and row.abs_touches_error is not None and row.abs_touches_error >= 12.0:
        return "touch_miss"
    if row.actual_passes is not None and row.abs_passes_error is not None and row.abs_passes_error >= 10.0:
        return "pass_miss"
    return "mixed"


def analyze_pregame_points_misses(result: PregamePointsBacktestResult, *, top_n: int = 250) -> PregamePointsMissAnalysis:
    rows = sorted(result.rows, key=lambda item: item.abs_error, reverse=True)[:top_n]
    counts = Counter(_classify_row(row) for row in rows)
    buckets = [
        PregamePointsMissBucket(label=label, count=count, pct=round(count / len(rows), 4) if rows else 0.0)
        for label, count in counts.most_common()
    ]
    with_context_rows = [row for row in rows if getattr(row, "pregame_context_attached", False)]
    without_context_rows = [row for row in rows if not getattr(row, "pregame_context_attached", False)]
    with_line_rows = [row for row in rows if getattr(row, "line_available", False)]
    without_line_rows = [row for row in rows if not getattr(row, "line_available", False)]
    with_context_counts = Counter(_classify_row(row) for row in with_context_rows)
    without_context_counts = Counter(_classify_row(row) for row in without_context_rows)
    with_line_counts = Counter(_classify_row(row) for row in with_line_rows)
    without_line_counts = Counter(_classify_row(row) for row in without_line_rows)
    examples = []
    for row in rows[:25]:
        examples.append(
            {
                "player_name": row.player_name,
                "game_id": row.game_id,
                "game_date": row.game_date.isoformat(),
                "projected_points": row.projected_points,
                "actual_points": row.actual_points,
                "actual_minutes": row.actual_minutes,
                "expected_minutes": row.expected_minutes,
                "error": row.error,
                "pregame_context_attached": bool(getattr(row, "pregame_context_attached", False)),
                "line_available": bool(getattr(row, "line_available", False)),
                "category": _classify_row(row),
            }
        )
    return PregamePointsMissAnalysis(
        top_miss_count=len(rows),
        buckets=buckets,
        examples=examples,
        pregame_context_attached_count=len(with_context_rows),
        pregame_context_missing_count=len(without_context_rows),
        line_available_count=len(with_line_rows),
        line_missing_count=len(without_line_rows),
        with_pregame_context_buckets=[
            PregamePointsMissBucket(label=label, count=count, pct=round(count / len(with_context_rows), 4) if with_context_rows else 0.0)
            for label, count in with_context_counts.most_common()
        ],
        without_pregame_context_buckets=[
            PregamePointsMissBucket(label=label, count=count, pct=round(count / len(without_context_rows), 4) if without_context_rows else 0.0)
            for label, count in without_context_counts.most_common()
        ],
        with_line_buckets=[
            PregamePointsMissBucket(label=label, count=count, pct=round(count / len(with_line_rows), 4) if with_line_rows else 0.0)
            for label, count in with_line_counts.most_common()
        ],
        without_line_buckets=[
            PregamePointsMissBucket(label=label, count=count, pct=round(count / len(without_line_rows), 4) if without_line_rows else 0.0)
            for label, count in without_line_counts.most_common()
        ],
    )


def analyze_pregame_opportunity_misses(
    result: PregameOpportunityBacktestResult,
    *,
    top_n: int = 250,
) -> PregameOpportunityMissAnalysis:
    rows = sorted(
        result.rows,
        key=lambda item: float(item.abs_minutes_error) if item.abs_minutes_error is not None else -1.0,
        reverse=True,
    )[:top_n]
    counts = Counter(_classify_opportunity_row(row) for row in rows)
    buckets = [
        PregameOpportunityMissBucket(label=label, count=count, pct=round(count / len(rows), 4) if rows else 0.0)
        for label, count in counts.most_common()
    ]
    with_context_rows = [row for row in rows if getattr(row, "pregame_context_attached", False)]
    without_context_rows = [row for row in rows if not getattr(row, "pregame_context_attached", False)]
    with_context_counts = Counter(_classify_opportunity_row(row) for row in with_context_rows)
    without_context_counts = Counter(_classify_opportunity_row(row) for row in without_context_rows)
    examples = []
    for row in rows[:25]:
        examples.append(
            {
                "player_name": row.player_name,
                "game_id": row.game_id,
                "game_date": row.game_date.isoformat(),
                "expected_minutes": row.expected_minutes,
                "actual_minutes": row.actual_minutes,
                "expected_usage_pct": row.expected_usage_pct,
                "actual_usage_pct": row.actual_usage_pct,
                "expected_start_rate": row.expected_start_rate,
                "actual_started": row.actual_started,
                "expected_close_rate": row.expected_close_rate,
                "actual_closed": row.actual_closed,
                "opportunity_score": row.opportunity_score,
                "confidence": row.confidence,
                "official_injury_status": getattr(row, "official_injury_status", None),
                "official_teammate_out_count": getattr(row, "official_teammate_out_count", None),
                "late_scratch_risk": getattr(row, "late_scratch_risk", None),
                "pregame_context_attached": bool(getattr(row, "pregame_context_attached", False)),
                "category": _classify_opportunity_row(row),
            }
        )
    return PregameOpportunityMissAnalysis(
        top_miss_count=len(rows),
        buckets=buckets,
        examples=examples,
        pregame_context_attached_count=len(with_context_rows),
        pregame_context_missing_count=len(without_context_rows),
        with_pregame_context_buckets=[
            PregameOpportunityMissBucket(label=label, count=count, pct=round(count / len(with_context_rows), 4) if with_context_rows else 0.0)
            for label, count in with_context_counts.most_common()
        ],
        without_pregame_context_buckets=[
            PregameOpportunityMissBucket(label=label, count=count, pct=round(count / len(without_context_rows), 4) if without_context_rows else 0.0)
            for label, count in without_context_counts.most_common()
        ],
    )
