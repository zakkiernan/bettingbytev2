from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analytics.features_assists import build_pregame_assists_features
from analytics.features_pregame import build_pregame_points_features
from analytics.features_rebounds import build_pregame_rebounds_features
from analytics.features_threes import build_pregame_threes_features
from analytics.nba.signals_common import SUPPORTED_STAT_TYPES
from analytics.nba.signals_profile import (
    build_fallback_signal_profile_data,
    build_stats_signal_profile_data,
)
from analytics.nba.signals_readiness import build_signal_readiness_data
from analytics.nba.signals_types import InjuryEntryData, StatsSignalProfileData
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
_INJURY_STATUS_LABELS = {
    "OUT": "Out",
    "DOUBTFUL": "Doubtful",
    "QUESTIONABLE": "Questionable",
    "PROBABLE": "Probable",
}
_STAT_FEATURE_BUILDERS = {
    "points": build_pregame_points_features,
    "rebounds": build_pregame_rebounds_features,
    "assists": build_pregame_assists_features,
    "threes": build_pregame_threes_features,
}


@dataclass(slots=True)
class StatsSignalCardData:
    snapshot: PlayerPropSnapshot
    game: Game | None
    profile: StatsSignalProfileData
    recent_logs: list[HistoricalGameLog]


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def today_window() -> tuple[datetime, datetime]:
    today = date.today()
    start = datetime(today.year, today.month, today.day, 0, 0, 0)
    end = start + timedelta(days=1)
    return start, end


def load_recent_logs_by_player(db: Session, player_ids: list[str]) -> dict[str, list[HistoricalGameLog]]:
    unique_player_ids = sorted({player_id for player_id in player_ids if player_id})
    if not unique_player_ids:
        return {}
    rows = (
        db.execute(
            select(HistoricalGameLog)
            .where(HistoricalGameLog.player_id.in_(unique_player_ids))
            .order_by(HistoricalGameLog.game_date.desc(), HistoricalGameLog.game_id.desc())
        )
        .scalars()
        .all()
    )
    recent_logs_by_player: dict[str, list[HistoricalGameLog]] = {}
    for row in rows:
        recent_logs_by_player.setdefault(row.player_id, []).append(row)
    return recent_logs_by_player


def load_features_by_snapshot(snapshots: list[PlayerPropSnapshot]) -> dict[tuple[datetime, str, str, str], object]:
    features_by_snapshot: dict[tuple[datetime, str, str, str], object] = {}
    for stat_type, build_features in _STAT_FEATURE_BUILDERS.items():
        feature_rows = build_features(limit=None)
        for feature in feature_rows:
            features_by_snapshot[(feature.captured_at, feature.game_id, feature.player_id, stat_type)] = feature
    return {
        key: value
        for key, value in features_by_snapshot.items()
        if key in {(snapshot.captured_at, snapshot.game_id, snapshot.player_id, snapshot.stat_type) for snapshot in snapshots}
    }


def injury_entries_for_team_date(rows: list[OfficialInjuryReportEntry]) -> list[InjuryEntryData]:
    entries: list[InjuryEntryData] = []
    for row in rows:
        label = _INJURY_STATUS_LABELS.get(row.current_status or "")
        if label is None:
            continue
        entries.append(
            InjuryEntryData(
                player_name=row.player_name or "Unknown",
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
) -> dict[tuple[str, date], list[InjuryEntryData]]:
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
                OfficialInjuryReportEntry.current_status.in_(list(_INJURY_STATUS_LABELS.keys())),
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

    grouped_rows: dict[tuple[str, date], list[OfficialInjuryReportEntry]] = {}
    for row in rows:
        if row.team_abbreviation is None or row.game_date is None:
            continue
        grouped_rows.setdefault((row.team_abbreviation, row.game_date), []).append(row)

    return {
        key: injury_entries_for_team_date(value)
        for key, value in grouped_rows.items()
    }


def load_latest_injury_reports_by_date(
    db: Session,
    *,
    game_dates: set[date],
) -> dict[date, datetime]:
    if not game_dates:
        return {}
    rows = (
        db.execute(
            select(
                OfficialInjuryReport.report_date,
                func.max(OfficialInjuryReport.report_datetime_utc).label("latest_report_at"),
            )
            .where(OfficialInjuryReport.report_date.in_(sorted(game_dates)))
            .group_by(OfficialInjuryReport.report_date)
        )
        .all()
    )
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
    keys = {
        (snapshot.game_id, snapshot.player_id, snapshot.stat_type)
        for snapshot in snapshots
    }
    if not keys:
        return {}

    rows = (
        db.execute(
            select(
                OddsSnapshot.game_id,
                OddsSnapshot.player_id,
                OddsSnapshot.stat_type,
                func.max(OddsSnapshot.captured_at).label("latest_captured_at"),
            )
            .where(
                OddsSnapshot.market_phase == "pregame",
                OddsSnapshot.is_live == False,  # noqa: E712
                OddsSnapshot.game_id.in_([key[0] for key in keys]),
                OddsSnapshot.player_id.in_([key[1] for key in keys]),
                OddsSnapshot.stat_type.in_([key[2] for key in keys]),
            )
            .group_by(OddsSnapshot.game_id, OddsSnapshot.player_id, OddsSnapshot.stat_type)
        )
        .all()
    )
    return {
        (row.game_id, row.player_id, row.stat_type): row.latest_captured_at
        for row in rows
        if row.latest_captured_at is not None
    }


def build_signal_cards_from_snapshots(
    db: Session,
    snapshots: list[PlayerPropSnapshot],
    *,
    evaluation_time: datetime | None = None,
) -> list[StatsSignalCardData]:
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

    cards: list[StatsSignalCardData] = []
    for snapshot in snapshots:
        game = games_by_id.get(snapshot.game_id)
        recent_logs = recent_logs_by_player.get(snapshot.player_id, [])
        game_date = game.game_date.date() if game and game.game_date else None
        injury_entries = injury_entries_by_team_date.get((snapshot.team or "", game_date), []) if snapshot.team and game_date else []

        feature = features_by_snapshot.get((snapshot.captured_at, snapshot.game_id, snapshot.player_id, snapshot.stat_type))
        if feature is None:
            profile = build_fallback_signal_profile_data(snapshot, game, recent_logs=recent_logs, injury_entries=injury_entries)
        else:
            profile = build_stats_signal_profile_data(
                feature,
                recent_logs=recent_logs,
                injury_entries=injury_entries,
                stat_type=snapshot.stat_type,
            )
        profile.readiness = build_signal_readiness_data(
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
            StatsSignalCardData(
                snapshot=snapshot,
                game=game,
                profile=profile,
                recent_logs=recent_logs,
            )
        )

    return cards


def base_snapshot_query() -> select:
    return select(PlayerPropSnapshot).where(
        PlayerPropSnapshot.is_live == False,  # noqa: E712
        PlayerPropSnapshot.snapshot_phase == CURRENT_SNAPSHOT_PHASE,
        PlayerPropSnapshot.stat_type.in_(SUPPORTED_STAT_TYPES),
    )


def load_current_snapshots(db: Session, *, game_ids: list[str] | None = None) -> list[PlayerPropSnapshot]:
    query = base_snapshot_query()
    if game_ids:
        query = query.where(PlayerPropSnapshot.game_id.in_(game_ids))
    return db.execute(
        query.order_by(
            PlayerPropSnapshot.game_id.asc(),
            PlayerPropSnapshot.player_name.asc(),
            PlayerPropSnapshot.stat_type.asc(),
        )
    ).scalars().all()


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
    return db.execute(
        select(
            func.max(StatsSignalSnapshot.created_at),
            func.max(StatsSignalSnapshot.source_prop_captured_at),
        )
        .where(
            StatsSignalSnapshot.game_id.in_(game_ids),
            StatsSignalSnapshot.snapshot_phase == CURRENT_SNAPSHOT_PHASE,
            StatsSignalSnapshot.stat_type.in_(SUPPORTED_STAT_TYPES),
        )
    ).one()


def load_signal_audit_archive_summary(db: Session) -> dict[str, int | str | datetime | None]:
    total_rows = int(db.execute(select(func.count(SignalAuditTrail.id))).scalar() or 0)
    rows_by_snapshot_phase = {
        str(snapshot_phase): int(count)
        for snapshot_phase, count in db.execute(
            select(SignalAuditTrail.snapshot_phase, func.count(SignalAuditTrail.id))
            .group_by(SignalAuditTrail.snapshot_phase)
            .order_by(SignalAuditTrail.snapshot_phase.asc())
        ).all()
    }
    games_with_full_coverage = int(
        db.execute(
            select(SignalAuditTrail.game_id)
            .where(SignalAuditTrail.snapshot_phase.in_(("early", "late", "tip")))
            .group_by(SignalAuditTrail.game_id)
            .having(func.count(func.distinct(SignalAuditTrail.snapshot_phase)) >= 3)
        ).rowcount
        or 0
    )
    most_recent_capture_at = db.execute(
        select(func.max(SignalAuditTrail.captured_at))
    ).scalar()
    return {
        "last_run_at": None,
        "signals_generated": 0,
        "signals_with_recommendation": 0,
        "signals_ready": 0,
        "signals_limited": 0,
        "signals_blocked": 0,
        "signals_using_fallback": 0,
        "signals_by_stat_type": {},
        "blocked_by_stat_type": {},
        "blocked_reasons": {},
        "latest_persisted_at": None,
        "latest_audit_source_prop_captured_at": None,
        "audit_lag_minutes": None,
        "signals_missing_source_game": 0,
        "total_audit_rows": total_rows,
        "audit_rows_by_snapshot_phase": rows_by_snapshot_phase,
        "games_with_full_audit_coverage": games_with_full_coverage,
        "most_recent_audit_capture_at": most_recent_capture_at,
    }
