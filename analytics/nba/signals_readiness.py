from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from analytics.features_opportunity import PregameOpportunityFeatures
from analytics.nba.signals_profile import POINTS_STAT_TYPE, SUPPORTED_STAT_TYPES, _value_or_zero
from analytics.nba.signals_types import SignalReadinessResult
from database.models import HistoricalGameLog, PlayerPropSnapshot

MIN_RECENT_GAMES_FOR_RECOMMENDATION = 5
MAX_SIGNAL_CAPTURE_AGE_MINUTES = 90
INJURY_REPORT_REQUIRED_WINDOW_MINUTES = 240
LOW_CONTEXT_CONFIDENCE_THRESHOLD = 0.45
LOW_OPPORTUNITY_CONFIDENCE_THRESHOLD = 0.35
STALE_ODDS_ARCHIVE_WARNING_MINUTES = 120
MIN_NON_ZERO_STAT_GAMES = 5

_STAT_LOG_ATTRS = {
    "points": "points",
    "rebounds": "rebounds",
    "assists": "assists",
    "threes": "threes_made",
}
_STAT_REQUIRED_FEATURE_FIELDS: dict[str, tuple[tuple[str, str], ...]] = {
    "points": (
        ("season_points_avg", "season scoring average"),
        ("last10_points_avg", "last-10 scoring average"),
    ),
    "rebounds": (
        ("season_rebounds_avg", "season rebounds average"),
        ("season_reb_pct", "season rebound rate"),
    ),
    "assists": (
        ("season_assists_avg", "season assists average"),
        ("season_ast_pct", "season assist rate"),
    ),
    "threes": (
        ("season_threes_avg", "season threes average"),
        ("season_3pa_rate", "season three-point attempt rate"),
    ),
}


def _age_minutes(later: datetime, earlier: datetime | None) -> int | None:
    if earlier is None:
        return None
    delta_seconds = (later - earlier).total_seconds()
    return max(int(delta_seconds // 60), 0)


def _minutes_to_tip(game: Any, *, evaluation_time: datetime) -> int | None:
    game_time_utc = getattr(game, "game_time_utc", None)
    if game_time_utc is None:
        return None
    return int((game_time_utc - evaluation_time).total_seconds() // 60)


def _count_non_zero_recent_games(recent_logs: list[HistoricalGameLog], *, stat_type: str) -> int:
    stat_attr = _STAT_LOG_ATTRS.get(stat_type)
    if stat_attr is None:
        return 0
    return sum(
        1
        for row in recent_logs
        if _value_or_zero(getattr(row, stat_attr, None)) > 0.0
    )


def _missing_stat_feature_labels(
    feature: PregameOpportunityFeatures,
    *,
    stat_type: str,
) -> list[str]:
    missing_labels: list[str] = []
    for attr, label in _STAT_REQUIRED_FEATURE_FIELDS.get(stat_type, ()):
        if getattr(feature, attr, None) is None:
            missing_labels.append(label)
    return missing_labels


def _build_signal_readiness(
    *,
    snapshot: PlayerPropSnapshot,
    game: Any,
    feature: PregameOpportunityFeatures | None,
    recent_logs: list[HistoricalGameLog],
    recent_games_count: int,
    opportunity_confidence: float | None,
    latest_injury_report_at: datetime | None,
    latest_odds_snapshot_at: datetime | None,
    evaluation_time: datetime,
) -> SignalReadinessResult:
    blockers: list[str] = []
    warnings: list[str] = []

    line_age_minutes = _age_minutes(evaluation_time, snapshot.captured_at)
    minutes_to_tip = _minutes_to_tip(game, evaluation_time=evaluation_time)
    using_fallback = feature is None

    if using_fallback:
        blockers.append("Pregame feature build is unavailable for this snapshot")

    if recent_games_count < MIN_RECENT_GAMES_FOR_RECOMMENDATION:
        blockers.append(f"Only {recent_games_count} recent games are available")

    if (
        line_age_minutes is not None
        and line_age_minutes > MAX_SIGNAL_CAPTURE_AGE_MINUTES
        and (minutes_to_tip is None or minutes_to_tip > 0)
    ):
        blockers.append(f"Pregame line snapshot is {line_age_minutes} minutes old")

    odds_archive_age_minutes = _age_minutes(evaluation_time, latest_odds_snapshot_at)
    if (
        minutes_to_tip is not None
        and 0 < minutes_to_tip <= INJURY_REPORT_REQUIRED_WINDOW_MINUTES
        and odds_archive_age_minutes is not None
        and odds_archive_age_minutes > STALE_ODDS_ARCHIVE_WARNING_MINUTES
    ):
        warnings.append(
            "Line snapshot may be stale"
            f" - last captured {odds_archive_age_minutes} minutes ago."
        )

    if (
        minutes_to_tip is not None
        and 0 < minutes_to_tip <= INJURY_REPORT_REQUIRED_WINDOW_MINUTES
        and latest_injury_report_at is None
    ):
        blockers.append("Official injury report is missing inside the pregame window")

    if feature is not None:
        stat_type = snapshot.stat_type if snapshot.stat_type in SUPPORTED_STAT_TYPES else POINTS_STAT_TYPE
        missing_labels = _missing_stat_feature_labels(feature, stat_type=stat_type)
        if missing_labels:
            blockers.append(
                f"Missing {stat_type} feature data: {', '.join(missing_labels)}"
            )

        if stat_type != POINTS_STAT_TYPE:
            non_zero_sample = _count_non_zero_recent_games(recent_logs, stat_type=stat_type)
            if non_zero_sample < MIN_NON_ZERO_STAT_GAMES:
                blockers.append(
                    f"Only {non_zero_sample} recent non-zero {stat_type} games are available"
                )

        context_confidence = _value_or_zero(feature.pregame_context_confidence)
        context_source = (feature.context_source or "none").strip().lower()
        if context_source == "none":
            warnings.append("Signal is missing enriched pregame context")
        elif context_source != "pregame_context":
            warnings.append(f"Signal is leaning on {context_source.replace('_', ' ')} context")

        if feature.pregame_context_confidence is not None and context_confidence < LOW_CONTEXT_CONFIDENCE_THRESHOLD:
            warnings.append(f"Pregame context confidence is only {context_confidence:.2f}")

    if opportunity_confidence is not None and opportunity_confidence < LOW_OPPORTUNITY_CONFIDENCE_THRESHOLD:
        blockers.append(
            f"Opportunity confidence is only {float(opportunity_confidence):.2f}"
        )

    status: Literal["ready", "limited", "blocked"] = "ready"
    if blockers:
        status = "blocked"
    elif warnings:
        status = "limited"

    return SignalReadinessResult(
        is_ready=not blockers,
        status=status,
        blockers=blockers,
        warnings=warnings,
        line_age_minutes=line_age_minutes,
        minutes_to_tip=minutes_to_tip,
        using_fallback=using_fallback,
    )


def build_signal_readiness(
    *,
    snapshot: PlayerPropSnapshot,
    game: Any,
    feature: PregameOpportunityFeatures | None,
    recent_logs: list[HistoricalGameLog],
    recent_games_count: int,
    opportunity_confidence: float | None,
    latest_injury_report_at: datetime | None,
    latest_odds_snapshot_at: datetime | None,
    evaluation_time: datetime,
) -> SignalReadinessResult:
    return _build_signal_readiness(
        snapshot=snapshot,
        game=game,
        feature=feature,
        recent_logs=recent_logs,
        recent_games_count=recent_games_count,
        opportunity_confidence=opportunity_confidence,
        latest_injury_report_at=latest_injury_report_at,
        latest_odds_snapshot_at=latest_odds_snapshot_at,
        evaluation_time=evaluation_time,
    )
