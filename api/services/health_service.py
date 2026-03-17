from __future__ import annotations

from datetime import date, datetime, timedelta

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
    OfficialInjuryReport,
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


def _today_window() -> tuple[datetime, datetime]:
    today = date.today()
    start = datetime(today.year, today.month, today.day, 0, 0, 0)
    end = start + timedelta(days=1)
    return start, end


def _build_lines_health(db: Session, now: datetime, today_game_ids: list[str]) -> LinesHealth:
    """Summarise tonight's prop-line capture state."""
    if not today_game_ids:
        return LinesHealth()

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
    )


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
    from database.models import OfficialInjuryReportEntry
    entries_stored = int(
        db.execute(select(func.count(OfficialInjuryReportEntry.id))).scalar() or 0
    )

    return InjuryReportsHealth(
        latest_report_date=str(latest_row) if latest_row else None,
        reports_stored=reports_stored,
        entries_stored=entries_stored,
    )


def _build_pregame_context_health(
    db: Session, today_game_ids: list[str]
) -> PregameContextHealth:
    """Count tonight's games that have pregame context snapshots."""
    if not today_game_ids:
        return PregameContextHealth()

    games_with_context = (
        db.execute(
            select(PregameContextSnapshot.game_id)
            .where(PregameContextSnapshot.game_id.in_(today_game_ids))
            .distinct()
        )
        .scalars()
        .all()
    )
    with_context = len(set(games_with_context))
    missing_context = len(today_game_ids) - with_context

    return PregameContextHealth(
        tonight_games_with_context=with_context,
        tonight_games_missing_context=missing_context,
    )


def _build_signal_run_health(
    db: Session, today_game_ids: list[str]
) -> SignalRunHealth:
    """Summarise tonight's stats-first signal card run."""
    return stats_signal_service.build_signal_run_health(db, today_game_ids)


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
    today_iso = now.date().isoformat()

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
