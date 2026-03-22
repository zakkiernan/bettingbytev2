from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analytics.features_opportunity import PregameOpportunityFeatures
from analytics.nba.signals_profile import (
    POINTS_STAT_TYPE,
    STAT_FEATURE_BUILDERS,
    SUPPORTED_STAT_TYPES,
    MAX_RECENT_LOGS,
    _title_case_status,
    build_fallback_signal_profile,
    build_stats_signal_profile,
)
from analytics.nba.signals_readiness import build_signal_readiness
from analytics.nba.signals_types import SignalInjuryEntry, StatsSignalCard
from database.models import (
    Game,
    HistoricalGameLog,
    OddsSnapshot,
    OfficialInjuryReport,
    OfficialInjuryReportEntry,
    PlayerPropSnapshot,
    SignalAuditTrail,
    StatsSignalSnapshot,
)

CURRENT_SNAPSHOT_PHASE = "current"
_INJURY_STATUS_CODES = ("OUT", "DOUBTFUL", "QUESTIONABLE", "PROBABLE")


def today_window() -> tuple[datetime, datetime]:
    today = date.today()
    start = datetime(today.year, today.month, today.day, 0, 0, 0)
    end = start + timedelta(days=1)
    return start, end


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def load_recent_logs_by_player(db: Session, player_ids: list[str]) -> dict[str, list[HistoricalGameLog]]:
    unique_player_ids = sorted({player_id for player_id in player_ids if player_id})
    if not unique_player_ids:
        return {}

    rows = (
        db.execute(
            select(HistoricalGameLog)
            .where(HistoricalGameLog.player_id.in_(unique_player_ids))
            .order_by(HistoricalGameLog.player_id, HistoricalGameLog.game_date.desc())
        )
        .scalars()
        .all()
    )

    logs_by_player: dict[str, list[HistoricalGameLog]] = defaultdict(list)
    for row in rows:
        bucket = logs_by_player[str(row.player_id)]
        if len(bucket) < MAX_RECENT_LOGS:
            bucket.append(row)
    return dict(logs_by_player)


def load_features_by_snapshot(snapshots: list[PlayerPropSnapshot]) -> dict[tuple[datetime, str, str, str], PregameOpportunityFeatures]:
    features_by_snapshot: dict[tuple[datetime, str, str, str], PregameOpportunityFeatures] = {}
    stat_types = sorted({snapshot.stat_type for snapshot in snapshots if snapshot.stat_type in STAT_FEATURE_BUILDERS})
    for captured_at in sorted({snapshot.captured_at for snapshot in snapshots}):
        for stat_type in stat_types:
            for feature in STAT_FEATURE_BUILDERS[stat_type](captured_at=captured_at):
                features_by_snapshot[(captured_at, feature.game_id, feature.player_id, stat_type)] = feature
    return features_by_snapshot


def _injury_entries_for_team_date(rows: list[OfficialInjuryReportEntry]) -> list[SignalInjuryEntry]:
    latest_by_player: dict[str, OfficialInjuryReportEntry] = {}
    for row in rows:
        key = row.player_name or ""
        current = latest_by_player.get(key)
        current_time = current.report_datetime_utc if current is not None else None
        if current is None or (row.report_datetime_utc or datetime.min) >= (current_time or datetime.min):
            latest_by_player[key] = row

    entries: list[SignalInjuryEntry] = []
    for row in latest_by_player.values():
        label = _title_case_status(row.current_status)
        if label is None:
            continue
        entries.append(
            SignalInjuryEntry(
                player_name=row.player_name or "",
                team_abbreviation=row.team_abbreviation or "",
                current_status=label,
                reason=row.reason or "",
            )
        )
    entries.sort(key=lambda entry: (entry.current_status, entry.player_name))
    return entries


def load_injury_entries_by_team_date(
    db: Session,
    *,
    team_dates: set[tuple[str, date]],
) -> dict[tuple[str, date], list[SignalInjuryEntry]]:
    if not team_dates:
        return {}

    team_abbreviations = sorted({team for team, _ in team_dates})
    game_dates = sorted({game_date for _, game_date in team_dates})
    rows = (
        db.execute(
            select(OfficialInjuryReportEntry)
            .where(
                OfficialInjuryReportEntry.team_abbreviation.in_(team_abbreviations),
                OfficialInjuryReportEntry.game_date.in_(game_dates),
                OfficialInjuryReportEntry.current_status.in_(list(_INJURY_STATUS_CODES)),
            )
            .order_by(
                OfficialInjuryReportEntry.team_abbreviation,
                OfficialInjuryReportEntry.game_date,
                OfficialInjuryReportEntry.report_datetime_utc.desc(),
            )
        )
        .scalars()
        .all()
    )

    grouped_rows: dict[tuple[str, date], list[OfficialInjuryReportEntry]] = defaultdict(list)
    for row in rows:
        if row.team_abbreviation and row.game_date:
            grouped_rows[(row.team_abbreviation, row.game_date)].append(row)

    return {
        key: _injury_entries_for_team_date(group_rows)
        for key, group_rows in grouped_rows.items()
    }


def load_latest_injury_reports_by_date(
    db: Session,
    *,
    game_dates: set[date],
) -> dict[date, datetime]:
    if not game_dates:
        return {}

    rows = db.execute(
        select(
            OfficialInjuryReport.report_date,
            func.max(OfficialInjuryReport.report_datetime_utc).label("latest_report_at"),
        )
        .where(OfficialInjuryReport.report_date.in_(sorted(game_dates)))
        .group_by(OfficialInjuryReport.report_date)
    ).all()

    return {
        row.report_date: row.latest_report_at
        for row in rows
        if row.report_date is not None and row.latest_report_at is not None
    }


def load_latest_odds_snapshot_times(
    db: Session,
    *,
    snapshots: list[PlayerPropSnapshot],
) -> dict[tuple[str, str, str], datetime]:
    if not snapshots:
        return {}

    game_ids = sorted({snapshot.game_id for snapshot in snapshots})
    player_ids = sorted({snapshot.player_id for snapshot in snapshots})
    stat_types = sorted({snapshot.stat_type for snapshot in snapshots})
    rows = db.execute(
        select(
            OddsSnapshot.game_id,
            OddsSnapshot.player_id,
            OddsSnapshot.stat_type,
            func.max(OddsSnapshot.captured_at).label("latest_captured_at"),
        )
        .where(
            OddsSnapshot.game_id.in_(game_ids),
            OddsSnapshot.player_id.in_(player_ids),
            OddsSnapshot.stat_type.in_(stat_types),
            OddsSnapshot.market_phase != "live",
        )
        .group_by(
            OddsSnapshot.game_id,
            OddsSnapshot.player_id,
            OddsSnapshot.stat_type,
        )
    ).all()
    return {
        (row.game_id, row.player_id, row.stat_type): row.latest_captured_at
        for row in rows
        if row.latest_captured_at is not None
    }


def build_cards_from_snapshots(
    db: Session,
    snapshots: list[PlayerPropSnapshot],
    *,
    evaluation_time: datetime | None = None,
) -> list[StatsSignalCard]:
    if not snapshots:
        return []
    evaluation_time = evaluation_time or utcnow()

    games_by_id = {
        game.game_id: game
        for game in db.execute(
            select(Game).where(Game.game_id.in_([snapshot.game_id for snapshot in snapshots]))
        ).scalars().all()
    }
    features_by_snapshot = load_features_by_snapshot(snapshots)
    recent_logs_by_player = load_recent_logs_by_player(db, [snapshot.player_id for snapshot in snapshots])
    latest_odds_snapshot_at_by_key = load_latest_odds_snapshot_times(db, snapshots=snapshots)

    team_dates: set[tuple[str, date]] = set()
    for snapshot in snapshots:
        game = games_by_id.get(snapshot.game_id)
        game_date = game.game_date.date() if game and game.game_date else None
        if snapshot.team and game_date is not None:
            team_dates.add((snapshot.team, game_date))
    injury_entries_by_team_date = load_injury_entries_by_team_date(db, team_dates=team_dates)
    injury_reports_by_date = load_latest_injury_reports_by_date(
        db,
        game_dates={game_date for _, game_date in team_dates},
    )

    cards: list[StatsSignalCard] = []
    for snapshot in snapshots:
        game = games_by_id.get(snapshot.game_id)
        recent_logs = recent_logs_by_player.get(snapshot.player_id, [])
        game_date = game.game_date.date() if game and game.game_date else None
        injury_entries = injury_entries_by_team_date.get((snapshot.team or "", game_date), []) if snapshot.team and game_date else []

        feature = features_by_snapshot.get((snapshot.captured_at, snapshot.game_id, snapshot.player_id, snapshot.stat_type))
        if feature is None:
            profile = build_fallback_signal_profile(snapshot, game, recent_logs=recent_logs, injury_entries=injury_entries)
        else:
            profile = build_stats_signal_profile(
                feature,
                recent_logs=recent_logs,
                injury_entries=injury_entries,
                stat_type=snapshot.stat_type,
            )
        profile.readiness = build_signal_readiness(
            snapshot=snapshot,
            game=game,
            feature=feature,
            recent_logs=recent_logs,
            recent_games_count=profile.recent_games_count,
            opportunity_confidence=profile.opportunity.opportunity_confidence,
            latest_injury_report_at=injury_reports_by_date.get(game_date) if game_date is not None else None,
            latest_odds_snapshot_at=latest_odds_snapshot_at_by_key.get(
                (snapshot.game_id, snapshot.player_id, snapshot.stat_type)
            ),
            evaluation_time=evaluation_time,
        )
        if profile.readiness.blockers:
            profile.recommended_side = None

        cards.append(
            StatsSignalCard(
                snapshot=snapshot,
                game=game,
                profile=profile,
                recent_logs=recent_logs,
            )
        )

    return cards


def base_snapshot_query():
    return select(PlayerPropSnapshot).where(
        PlayerPropSnapshot.is_live == False,  # noqa: E712
        PlayerPropSnapshot.snapshot_phase == CURRENT_SNAPSHOT_PHASE,
        PlayerPropSnapshot.stat_type.in_(SUPPORTED_STAT_TYPES),
    )


def load_current_snapshots(
    db: Session,
    *,
    game_ids: list[str] | None = None,
    player_id: str | None = None,
) -> list[PlayerPropSnapshot]:
    query = base_snapshot_query()
    if game_ids is not None:
        if not game_ids:
            return []
        query = query.where(PlayerPropSnapshot.game_id.in_(game_ids))
    if player_id is not None:
        query = query.where(PlayerPropSnapshot.player_id == player_id)
    query = query.order_by(PlayerPropSnapshot.game_id, PlayerPropSnapshot.player_name)
    return db.execute(query).scalars().all()


def load_snapshots_for_today(db: Session, *, game_id: str | None = None) -> tuple[list[PlayerPropSnapshot], list[str]]:
    start, end = today_window()
    today_game_ids = [
        row[0]
        for row in db.execute(
            select(Game.game_id).where(
                Game.game_date >= start,
                Game.game_date < end,
            )
        ).all()
    ]
    scoped_game_ids = [game_id] if game_id is not None else today_game_ids
    return load_current_snapshots(db, game_ids=scoped_game_ids), scoped_game_ids


def load_latest_signal_audit_metrics(
    db: Session,
    *,
    game_ids: list[str],
) -> tuple[datetime | None, datetime | None]:
    if not game_ids:
        return None, None

    latest_persisted_at, latest_source_prop_captured_at = db.execute(
        select(
            func.max(StatsSignalSnapshot.created_at),
            func.max(StatsSignalSnapshot.source_prop_captured_at),
        ).where(
            StatsSignalSnapshot.game_id.in_(game_ids),
            StatsSignalSnapshot.snapshot_phase == CURRENT_SNAPSHOT_PHASE,
            StatsSignalSnapshot.stat_type.in_(SUPPORTED_STAT_TYPES),
        )
    ).one()
    return latest_persisted_at, latest_source_prop_captured_at


def load_signal_audit_archive_summary(db: Session) -> dict[str, object]:
    total_rows = int(db.execute(select(func.count(SignalAuditTrail.id))).scalar() or 0)
    phase_rows = db.execute(
        select(SignalAuditTrail.snapshot_phase, func.count(SignalAuditTrail.id))
        .group_by(SignalAuditTrail.snapshot_phase)
        .order_by(SignalAuditTrail.snapshot_phase.asc())
    ).all()
    games_with_full_coverage = int(
        db.execute(
            select(func.count())
            .select_from(
                select(SignalAuditTrail.game_id)
                .where(SignalAuditTrail.snapshot_phase.in_(("early", "late", "tip")))
                .group_by(SignalAuditTrail.game_id)
                .having(func.count(func.distinct(SignalAuditTrail.snapshot_phase)) >= 3)
                .subquery()
            )
        ).scalar()
        or 0
    )
    most_recent_capture_at = db.execute(
        select(func.max(SignalAuditTrail.captured_at))
    ).scalar()
    return {
        "total_audit_rows": total_rows,
        "audit_rows_by_snapshot_phase": {
            str(phase or "unknown"): int(count)
            for phase, count in phase_rows
        },
        "games_with_full_audit_coverage": games_with_full_coverage,
        "most_recent_audit_capture_at": most_recent_capture_at,
    }
