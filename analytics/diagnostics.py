from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from analytics.evaluation import PregamePointsBacktestResult, PregamePointsBacktestRow


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


def analyze_pregame_points_misses(result: PregamePointsBacktestResult, *, top_n: int = 250) -> PregamePointsMissAnalysis:
    rows = sorted(result.rows, key=lambda item: item.abs_error, reverse=True)[:top_n]
    counts = Counter(_classify_row(row) for row in rows)
    buckets = [
        PregamePointsMissBucket(label=label, count=count, pct=round(count / len(rows), 4) if rows else 0.0)
        for label, count in counts.most_common()
    ]
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
                "category": _classify_row(row),
            }
        )
    return PregamePointsMissAnalysis(top_miss_count=len(rows), buckets=buckets, examples=examples)
