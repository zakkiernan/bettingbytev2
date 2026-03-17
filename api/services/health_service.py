from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.health import (
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

    return IngestionHealthResponse(
        health_captured_at=now,
        lines=_build_lines_health(db, now, today_game_ids),
        rotations=_build_rotations_health(db),
        injury_reports=_build_injury_reports_health(db),
        pregame_context=_build_pregame_context_health(db, today_game_ids),
        signal_run=_build_signal_run_health(db, today_game_ids),
    )
