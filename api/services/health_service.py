from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.health import (
    HealthAlert,
    IngestionHealthResponse,
    InjuryReportsHealth,
    LinesHealth,
    PregameContextHealth,
    RotationsHealth,
    SignalRunHealth,
)
from api.services import stats_signal_service
from database.models import (
    Game,
    OddsSnapshot,
    OfficialInjuryReport,
    OfficialInjuryReportEntry,
    PlayerPropSnapshot,
    PregameContextSnapshot,
    RotationSyncState,
)
from ingestion.rotation_sync import (
    ROTATION_SYNC_STATUS_PENDING,
    ROTATION_SYNC_STATUS_QUARANTINED,
    ROTATION_SYNC_STATUS_RETRY,
)

_STALE_CAPTURE_MINUTES = 60
_SIGNAL_AUDIT_LAG_WARNING_MINUTES = 20
_SIGNAL_AUDIT_LAG_CRITICAL_MINUTES = 60
_PREGAME_ODDS_PHASES = ("pregame", "early", "late", "tip", "accumulation")
_HEALTH_SLATE_TIMEZONE = ZoneInfo("America/New_York")


def _today_window() -> tuple[datetime, datetime]:
    today = date.today()
    start = datetime(today.year, today.month, today.day, 0, 0, 0)
    end = start + timedelta(days=1)
    return start, end


def _build_lines_health(db: Session, now: datetime, today_game_ids: list[str]) -> LinesHealth:
    """Summarise tonight's prop-line capture state."""
    coverage = get_odds_snapshot_coverage(db)
    if not today_game_ids:
        return LinesHealth(**coverage)

    # All pregame snapshots for tonight's games
    snapshots = (
        db.execute(
            select(
                PlayerPropSnapshot.game_id,
                PlayerPropSnapshot.player_id,
                PlayerPropSnapshot.stat_type,
                func.max(PlayerPropSnapshot.captured_at).label("latest_capture"),
            )
            .where(
                PlayerPropSnapshot.game_id.in_(today_game_ids),
                PlayerPropSnapshot.is_live == False,  # noqa: E712
            )
            .group_by(
                PlayerPropSnapshot.game_id,
                PlayerPropSnapshot.player_id,
                PlayerPropSnapshot.stat_type,
            )
        )
        .all()
    )

    stale_threshold = now - timedelta(minutes=_STALE_CAPTURE_MINUTES)
    stale_count = 0
    oldest_age_minutes: int | None = None

    for row in snapshots:
        capture_age_minutes = int((now - row.latest_capture).total_seconds() / 60)
        if oldest_age_minutes is None or capture_age_minutes > oldest_age_minutes:
            oldest_age_minutes = capture_age_minutes
        if row.latest_capture < stale_threshold:
            stale_count += 1

    return LinesHealth(
        tonight_game_count=len(today_game_ids),
        tonight_prop_count=len(snapshots),
        stale_captures=stale_count,
        oldest_capture_age_minutes=oldest_age_minutes,
        sportsbook="fanduel",
        **coverage,
    )


def get_odds_snapshot_coverage(db: Session) -> dict[str, object]:
    total_rows = int(db.execute(select(func.count(OddsSnapshot.id))).scalar() or 0)
    phase_rows = db.execute(
        select(OddsSnapshot.market_phase, func.count(OddsSnapshot.id))
        .group_by(OddsSnapshot.market_phase)
        .order_by(OddsSnapshot.market_phase.asc())
    ).all()
    date_range = db.execute(
        select(func.min(OddsSnapshot.captured_at), func.max(OddsSnapshot.captured_at))
    ).one()
    multi_snapshot_games = int(
        db.execute(
            select(func.count())
            .select_from(
                select(OddsSnapshot.game_id)
                .where(OddsSnapshot.market_phase.in_(_PREGAME_ODDS_PHASES))
                .group_by(OddsSnapshot.game_id)
                .having(func.count(OddsSnapshot.id) >= 2)
                .subquery()
            )
        ).scalar()
        or 0
    )
    distinct_games = int(db.execute(select(func.count(func.distinct(OddsSnapshot.game_id)))).scalar() or 0)

    return {
        "total_odds_snapshots": total_rows,
        "odds_snapshot_rows_by_phase": {str(phase or "unknown"): int(count) for phase, count in phase_rows},
        "odds_snapshot_start_date": date_range[0],
        "odds_snapshot_end_date": date_range[1],
        "games_with_multi_pregame_snapshots": multi_snapshot_games,
        "average_odds_snapshots_per_game": round(total_rows / distinct_games, 2) if distinct_games else 0.0,
    }


def _build_rotations_health(db: Session) -> RotationsHealth:
    """Summarise rotation sync queue state."""
    total_games = (
        int(db.execute(select(func.count(RotationSyncState.game_id))).scalar() or 0)
    )
    pending = int(
        db.execute(
            select(func.count(RotationSyncState.game_id)).where(
                RotationSyncState.status == ROTATION_SYNC_STATUS_PENDING
            )
        ).scalar()
        or 0
    )
    retry = int(
        db.execute(
            select(func.count(RotationSyncState.game_id)).where(
                RotationSyncState.status == ROTATION_SYNC_STATUS_RETRY
            )
        ).scalar()
        or 0
    )
    quarantined = int(
        db.execute(
            select(func.count(RotationSyncState.game_id)).where(
                RotationSyncState.status == ROTATION_SYNC_STATUS_QUARANTINED
            )
        ).scalar()
        or 0
    )
    done = total_games - pending - retry - quarantined
    coverage_pct = round((done / total_games) * 100, 2) if total_games else 0.0

    return RotationsHealth(
        coverage_pct=coverage_pct,
        pending=pending,
        retry=retry,
        quarantined=quarantined,
    )


def _build_injury_reports_health(db: Session) -> InjuryReportsHealth:
    """Summarise official injury report ingestion state."""
    latest_row = (
        db.execute(
            select(OfficialInjuryReport.report_date)
            .where(OfficialInjuryReport.report_date.is_not(None))
            .order_by(OfficialInjuryReport.report_date.desc())
            .limit(1)
        )
        .scalar()
    )
    reports_stored = int(
        db.execute(select(func.count(OfficialInjuryReport.id))).scalar() or 0
    )
    return InjuryReportsHealth(
        latest_report_date=str(latest_row) if latest_row else None,
        reports_stored=reports_stored,
        **get_injury_matching_coverage(db),
    )


def get_injury_matching_coverage(db: Session) -> dict[str, object]:
    entries_stored = int(db.execute(select(func.count(OfficialInjuryReportEntry.id))).scalar() or 0)
    entries_with_player_id = int(
        db.execute(
            select(func.count(OfficialInjuryReportEntry.id)).where(
                OfficialInjuryReportEntry.player_id.is_not(None)
            )
        ).scalar()
        or 0
    )
    named_entries_stored = int(
        db.execute(
            select(func.count(OfficialInjuryReportEntry.id)).where(
                OfficialInjuryReportEntry.player_name.is_not(None)
            )
        ).scalar()
        or 0
    )
    named_entries_with_player_id = int(
        db.execute(
            select(func.count(OfficialInjuryReportEntry.id)).where(
                OfficialInjuryReportEntry.player_name.is_not(None),
                OfficialInjuryReportEntry.player_id.is_not(None),
            )
        ).scalar()
        or 0
    )
    entries_without_player_id_by_team_rows = db.execute(
        select(
            OfficialInjuryReportEntry.team_abbreviation,
            func.count(OfficialInjuryReportEntry.id),
        )
        .where(OfficialInjuryReportEntry.player_id.is_(None))
        .group_by(OfficialInjuryReportEntry.team_abbreviation)
        .order_by(func.count(OfficialInjuryReportEntry.id).desc())
    ).all()
    named_entries_without_player_id_by_team_rows = db.execute(
        select(
            OfficialInjuryReportEntry.team_abbreviation,
            func.count(OfficialInjuryReportEntry.id),
        )
        .where(
            OfficialInjuryReportEntry.player_id.is_(None),
            OfficialInjuryReportEntry.player_name.is_not(None),
        )
        .group_by(OfficialInjuryReportEntry.team_abbreviation)
        .order_by(func.count(OfficialInjuryReportEntry.id).desc())
    ).all()
    most_recent_match_stats_report_date = db.execute(
        select(func.max(OfficialInjuryReportEntry.game_date))
    ).scalar()

    entries_without_player_id = entries_stored - entries_with_player_id
    named_entries_without_player_id = named_entries_stored - named_entries_with_player_id
    return {
        "entries_stored": entries_stored,
        "entries_with_player_id": entries_with_player_id,
        "entries_without_player_id": entries_without_player_id,
        "entry_match_pct": round(entries_with_player_id / entries_stored, 4) if entries_stored else 0.0,
        "named_entries_stored": named_entries_stored,
        "named_entries_with_player_id": named_entries_with_player_id,
        "named_entries_without_player_id": named_entries_without_player_id,
        "named_entry_match_pct": round(named_entries_with_player_id / named_entries_stored, 4) if named_entries_stored else 0.0,
        "entries_without_player_id_by_team": {
            str(team_abbreviation or "unknown"): int(count)
            for team_abbreviation, count in entries_without_player_id_by_team_rows
        },
        "named_entries_without_player_id_by_team": {
            str(team_abbreviation or "unknown"): int(count)
            for team_abbreviation, count in named_entries_without_player_id_by_team_rows
        },
        "most_recent_match_stats_report_date": (
            str(most_recent_match_stats_report_date)
            if most_recent_match_stats_report_date is not None
            else None
        ),
    }


def _build_pregame_context_health(
    db: Session, today_game_ids: list[str]
) -> PregameContextHealth:
    """Count today's in-scope games that have pregame context snapshots.

    During live slates, `sync_pregame_markets()` only refreshes context for games that
    still appear in the latest `snapshot_phase='current'` pregame prop capture. Earlier
    finalized games may have historical pregame context but are no longer part of the
    current refresh scope. Health should mirror that runtime scope when current-phase
    markets are available.
    """
    if not today_game_ids:
        return PregameContextHealth()

    current_phase_game_ids = set(
        db.execute(
            select(PlayerPropSnapshot.game_id)
            .where(
                PlayerPropSnapshot.game_id.in_(today_game_ids),
                PlayerPropSnapshot.is_live == False,  # noqa: E712
                PlayerPropSnapshot.snapshot_phase == "current",
            )
            .distinct()
        )
        .scalars()
        .all()
    )
    scope_game_ids = current_phase_game_ids or set(today_game_ids)

    games_with_context = set(
        db.execute(
            select(PregameContextSnapshot.game_id)
            .where(PregameContextSnapshot.game_id.in_(scope_game_ids))
            .distinct()
        )
        .scalars()
        .all()
    )
    with_context = len(games_with_context)
    missing_context = len(scope_game_ids) - with_context

    return PregameContextHealth(
        tonight_games_with_context=with_context,
        tonight_games_missing_context=missing_context,
    )


def _build_signal_run_health(
    db: Session, today_game_ids: list[str]
) -> SignalRunHealth:
    """Summarise tonight's stats-first signal card run."""
    return stats_signal_service.build_signal_run_health(db, today_game_ids)


def _current_slate_date_iso(now: datetime) -> str:
    localized_now = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return localized_now.astimezone(_HEALTH_SLATE_TIMEZONE).date().isoformat()


def _build_health_alerts(
    *,
    now: datetime,
    today_game_ids: list[str],
    lines: LinesHealth,
    injury_reports: InjuryReportsHealth,
    pregame_context: PregameContextHealth,
    signal_run: SignalRunHealth,
) -> list[HealthAlert]:
    alerts: list[HealthAlert] = []
    today_iso = _current_slate_date_iso(now)

    if today_game_ids and lines.tonight_prop_count == 0:
        alerts.append(
            HealthAlert(
                code="lines_missing",
                severity="critical",
                message="No pregame prop captures are available for today's slate.",
            )
        )
    elif lines.stale_captures > 0:
        severity = "critical" if lines.stale_captures == lines.tonight_prop_count else "warning"
        alerts.append(
            HealthAlert(
                code="lines_stale",
                severity=severity,
                message=(
                    f"{lines.stale_captures} pregame prop captures are older than "
                    f"{_STALE_CAPTURE_MINUTES} minutes."
                ),
            )
        )

    if today_game_ids and injury_reports.latest_report_date != today_iso:
        alerts.append(
            HealthAlert(
                code="injury_reports_stale",
                severity="critical",
                message="Official injury reports are not current for today's slate.",
            )
        )

    if pregame_context.tonight_games_missing_context > 0:
        severity = (
            "critical"
            if pregame_context.tonight_games_with_context == 0 and today_game_ids
            else "warning"
        )
        alerts.append(
            HealthAlert(
                code="pregame_context_missing",
                severity=severity,
                message=(
                    f"{pregame_context.tonight_games_missing_context} slate games are missing "
                    "persisted pregame context."
                ),
            )
        )

    if signal_run.signals_generated > 0:
        if signal_run.latest_persisted_at is None:
            alerts.append(
                HealthAlert(
                    code="signal_audit_missing",
                    severity="critical",
                    message="Current stats-first signals have not been persisted to the audit trail.",
                )
            )
        elif signal_run.audit_lag_minutes is not None and signal_run.audit_lag_minutes > 0:
            severity = (
                "critical"
                if signal_run.audit_lag_minutes >= _SIGNAL_AUDIT_LAG_CRITICAL_MINUTES
                else "warning"
            )
            if signal_run.audit_lag_minutes >= _SIGNAL_AUDIT_LAG_WARNING_MINUTES:
                alerts.append(
                    HealthAlert(
                        code="signal_audit_lag",
                        severity=severity,
                        message=(
                            "Signal audit snapshots are behind the latest prop captures by "
                            f"{signal_run.audit_lag_minutes} minutes."
                        ),
                    )
                )

        if signal_run.signals_blocked == signal_run.signals_generated:
            alerts.append(
                HealthAlert(
                    code="signals_all_blocked",
                    severity="critical",
                    message="Every current stats-first signal is blocked by readiness gates.",
                )
            )
        elif signal_run.signals_blocked > 0:
            alerts.append(
                HealthAlert(
                    code="signals_partially_blocked",
                    severity="warning",
                    message=(
                        f"{signal_run.signals_blocked} current stats-first signals are blocked "
                        "by readiness gates."
                    ),
                )
            )

        if signal_run.signals_using_fallback > 0:
            alerts.append(
                HealthAlert(
                    code="signals_using_fallback",
                    severity="warning",
                    message=(
                        f"{signal_run.signals_using_fallback} current stats-first signals are "
                        "leaning on fallback logic."
                    ),
                )
            )

    return alerts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_ingestion_health(db: Session) -> IngestionHealthResponse:
    """Build a full pipeline health snapshot for the dashboard header."""
    now = datetime.utcnow()
    start, end = _today_window()

    today_game_id_rows = db.execute(
        select(Game.game_id).where(
            Game.game_date >= start,
            Game.game_date < end,
        )
    ).all()
    today_game_ids = [row[0] for row in today_game_id_rows]

    lines = _build_lines_health(db, now, today_game_ids)
    rotations = _build_rotations_health(db)
    injury_reports = _build_injury_reports_health(db)
    pregame_context = _build_pregame_context_health(db, today_game_ids)
    signal_run = _build_signal_run_health(db, today_game_ids)

    return IngestionHealthResponse(
        health_captured_at=now,
        lines=lines,
        rotations=rotations,
        injury_reports=injury_reports,
        pregame_context=pregame_context,
        signal_run=signal_run,
        alerts=_build_health_alerts(
            now=now,
            today_game_ids=today_game_ids,
            lines=lines,
            injury_reports=injury_reports,
            pregame_context=pregame_context,
            signal_run=signal_run,
        ),
    )
