from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import func

from database.db import session_scope
from database.models import (
    Game,
    HistoricalAdvancedLog,
    HistoricalGameLog,
    IngestionRun,
    IngestionRunItem,
    LiveGameSnapshot,
    LivePlayerSnapshot,
    OddsSnapshot,
    Player,
    PlayerPropSnapshot,
    PlayerRotationGame,
    PlayerRotationStint,
    RotationSyncState,
    SourcePayload,
    SportsbookEventMap,
    Team,
    TeamRotationGame,
)
from ingestion.rotation_sync import (
    ROTATION_SYNC_STATUS_PENDING,
    ROTATION_SYNC_STATUS_QUARANTINED,
    ROTATION_SYNC_STATUS_RETRY,
)

FINAL_GAME_STATUS = 3
FINAL_STATUS_TEXT = "Final"


def _season_from_game_date(game_date: datetime | None) -> str | None:
    if game_date is None:
        return None
    if game_date.month >= 10:
        return f"{game_date.year}-{str(game_date.year + 1)[-2:]}"
    return f"{game_date.year - 1}-{str(game_date.year)[-2:]}"


def _matches_season(game_date: datetime | None, season: str | None) -> bool:
    if season is None:
        return True
    return _season_from_game_date(game_date) == season


def _historical_game_counts(session, season: str | None = None) -> dict[str, int]:
    rows = (
        session.query(
            HistoricalGameLog.game_id.label("game_id"),
            func.count(HistoricalGameLog.player_id).label("historical_players"),
            func.min(HistoricalGameLog.game_date).label("game_date"),
        )
        .group_by(HistoricalGameLog.game_id)
        .all()
    )
    return {
        row.game_id: int(row.historical_players)
        for row in rows
        if _matches_season(row.game_date, season)
    }


def get_postgame_enrichment_backlog(season: str | None = None) -> list[dict[str, int | str]]:
    with session_scope() as session:
        hist_counts = _historical_game_counts(session, season=season)
        adv_counts = {
            row.game_id: int(row.advanced_players)
            for row in session.query(
                HistoricalAdvancedLog.game_id.label("game_id"),
                func.count(HistoricalAdvancedLog.player_id).label("advanced_players"),
            )
            .filter(HistoricalAdvancedLog.game_id.in_(hist_counts.keys()))
            .group_by(HistoricalAdvancedLog.game_id)
            .all()
        }

    backlog: list[dict[str, int | str]] = []
    for game_id, historical_players in hist_counts.items():
        advanced_players = adv_counts.get(game_id, 0)
        if advanced_players < historical_players:
            backlog.append(
                {
                    "game_id": game_id,
                    "historical_players": historical_players,
                    "advanced_players": advanced_players,
                    "missing_players": historical_players - advanced_players,
                }
            )

    backlog.sort(key=lambda row: (-int(row["missing_players"]), str(row["game_id"])))
    return backlog


def get_rotation_backlog(season: str | None = None) -> list[dict[str, int | str]]:
    with session_scope() as session:
        hist_counts = _historical_game_counts(session, season=season)
        rotation_counts = {
            row.game_id: int(row.rotation_players)
            for row in session.query(
                PlayerRotationGame.game_id.label("game_id"),
                func.count(PlayerRotationGame.player_id).label("rotation_players"),
            )
            .filter(PlayerRotationGame.game_id.in_(hist_counts.keys()))
            .group_by(PlayerRotationGame.game_id)
            .all()
        }

    backlog: list[dict[str, int | str]] = []
    for game_id, historical_players in hist_counts.items():
        rotation_players = rotation_counts.get(game_id, 0)
        if rotation_players < historical_players:
            backlog.append(
                {
                    "game_id": game_id,
                    "historical_players": historical_players,
                    "rotation_players": rotation_players,
                    "missing_players": historical_players - rotation_players,
                }
            )

    backlog.sort(key=lambda row: (-int(row["missing_players"]), str(row["game_id"])))
    return backlog


def get_missing_canonical_games_from_history(season: str | None = None) -> list[dict[str, object]]:
    with session_scope() as session:
        existing_game_ids = {row[0] for row in session.query(Game.game_id).distinct().all()}
        historical_game_ids = {
            row.game_id
            for row in session.query(
                HistoricalGameLog.game_id.label("game_id"),
                func.min(HistoricalGameLog.game_date).label("game_date"),
            )
            .group_by(HistoricalGameLog.game_id)
            .all()
            if _matches_season(row.game_date, season)
        }
        missing_game_ids = sorted(historical_game_ids - existing_game_ids)
        if not missing_game_ids:
            return []

        team_id_by_abbreviation = {
            team.abbreviation: team.team_id
            for team in session.query(Team).all()
            if team.abbreviation
        }

        grouped_rows: dict[str, list[HistoricalGameLog]] = defaultdict(list)
        for row in (
            session.query(HistoricalGameLog)
            .filter(HistoricalGameLog.game_id.in_(missing_game_ids))
            .order_by(HistoricalGameLog.game_id, HistoricalGameLog.team, HistoricalGameLog.player_id)
            .all()
        ):
            grouped_rows[row.game_id].append(row)

    canonical_games: list[dict[str, object]] = []
    for game_id in missing_game_ids:
        rows = grouped_rows.get(game_id, [])
        if not rows:
            continue

        home_row = next((row for row in rows if row.is_home), None)
        away_row = next((row for row in rows if not row.is_home), None)
        if home_row is None or away_row is None:
            continue

        game_date = min((row.game_date for row in rows if row.game_date is not None), default=None)
        canonical_games.append(
            {
                "game_id": game_id,
                "season": season,
                "game_date": game_date,
                "home_team_id": team_id_by_abbreviation.get(home_row.team),
                "away_team_id": team_id_by_abbreviation.get(away_row.team),
                "home_team_abbreviation": home_row.team,
                "away_team_abbreviation": away_row.team,
                "game_status": FINAL_GAME_STATUS,
                "status_text": FINAL_STATUS_TEXT,
                "game_time_utc": game_date,
                "is_in_season_tournament": None,
            }
        )

    return canonical_games


def get_rotation_queue_diagnostics(
    season: str | None = None,
    statuses: list[str] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    with session_scope() as session:
        query = session.query(RotationSyncState)
        if season is not None:
            query = query.filter(RotationSyncState.season == season)
        if statuses:
            query = query.filter(RotationSyncState.status.in_(statuses))
        rows = query.all()

    rows = sorted(
        rows,
        key=lambda row: (
            row.next_retry_at or datetime.min,
            -int(row.consecutive_failures or 0),
            str(row.game_id),
        ),
    )[:limit]

    return [
        {
            "game_id": row.game_id,
            "season": row.season,
            "status": row.status,
            "attempt_count": int(row.attempt_count or 0),
            "consecutive_failures": int(row.consecutive_failures or 0),
            "last_attempted_at": row.last_attempted_at,
            "last_succeeded_at": row.last_succeeded_at,
            "next_retry_at": row.next_retry_at,
            "last_error_type": row.last_error_type,
            "last_error_text": row.last_error_text,
            "last_run_id": row.last_run_id,
        }
        for row in rows
    ]


def summarize_ingestion_health() -> dict[str, Any]:
    now = datetime.utcnow()
    with session_scope() as session:
        historical_game_ids = {row[0] for row in session.query(HistoricalGameLog.game_id).distinct().all()}
        enriched_game_ids = {row[0] for row in session.query(HistoricalAdvancedLog.game_id).distinct().all()}
        rotation_game_ids = {row[0] for row in session.query(PlayerRotationGame.game_id).distinct().all()}
        canonical_game_ids = {row[0] for row in session.query(Game.game_id).distinct().all()}

        historical_games = len(historical_game_ids)
        enriched_games = len(enriched_game_ids)
        rotation_games = len(rotation_game_ids)
        canonical_games = len(canonical_game_ids)
        canonical_historical_games = len(historical_game_ids & canonical_game_ids)
        extra_canonical_games = len(canonical_game_ids - historical_game_ids)

        mapped_events = int(
            session.query(func.count(SportsbookEventMap.id))
            .filter(SportsbookEventMap.nba_game_id.is_not(None))
            .scalar()
            or 0
        )
        total_events = int(session.query(func.count(SportsbookEventMap.id)).scalar() or 0)
        failed_runs = int(session.query(func.count(IngestionRun.id)).filter(IngestionRun.status == "failed").scalar() or 0)
        failed_run_items = int(
            session.query(func.count(IngestionRunItem.id)).filter(IngestionRunItem.status == "failed").scalar() or 0
        )

        rotation_queue_pending = int(
            session.query(func.count(RotationSyncState.game_id))
            .filter(RotationSyncState.status == ROTATION_SYNC_STATUS_PENDING)
            .scalar()
            or 0
        )
        rotation_queue_retry = int(
            session.query(func.count(RotationSyncState.game_id))
            .filter(RotationSyncState.status == ROTATION_SYNC_STATUS_RETRY)
            .scalar()
            or 0
        )
        rotation_queue_quarantined = int(
            session.query(func.count(RotationSyncState.game_id))
            .filter(RotationSyncState.status == ROTATION_SYNC_STATUS_QUARANTINED)
            .scalar()
            or 0
        )
        rotation_queue_due_now = int(
            session.query(func.count(RotationSyncState.game_id))
            .filter(
                RotationSyncState.status == ROTATION_SYNC_STATUS_RETRY,
                RotationSyncState.next_retry_at.is_not(None),
                RotationSyncState.next_retry_at <= now,
            )
            .scalar()
            or 0
        )
        failure_rows = (
            session.query(
                RotationSyncState.last_error_type,
                func.count(RotationSyncState.game_id).label("count"),
            )
            .filter(
                RotationSyncState.status.in_([ROTATION_SYNC_STATUS_RETRY, ROTATION_SYNC_STATUS_QUARANTINED]),
                RotationSyncState.last_error_type.is_not(None),
            )
            .group_by(RotationSyncState.last_error_type)
            .all()
        )
        rotation_recent_failure_counts = {
            str(row.last_error_type): int(row.count)
            for row in failure_rows
            if row.last_error_type
        }

    enrichment_coverage = round((enriched_games / historical_games) * 100, 2) if historical_games else 0.0
    rotation_coverage = round((rotation_games / historical_games) * 100, 2) if historical_games else 0.0
    canonical_coverage = round((canonical_historical_games / historical_games) * 100, 2) if historical_games else 0.0

    unresolved_enrichment_failures = {row["game_id"] for row in get_postgame_enrichment_backlog()}
    unresolved_rotation_failures = {row["game_id"] for row in get_rotation_backlog()}
    unresolved_canonical_failures = {row["game_id"] for row in get_missing_canonical_games_from_history()}

    with session_scope() as session:
        unresolved_failed_run_items = 0
        for row in session.query(IngestionRunItem).filter(IngestionRunItem.status == "failed").all():
            if row.stage == "postgame_enrichment" and row.entity_key in unresolved_enrichment_failures:
                unresolved_failed_run_items += 1
            elif row.stage == "game_rotation" and row.entity_key in unresolved_rotation_failures:
                unresolved_failed_run_items += 1
            elif row.stage == "canonical_game_reconciliation" and row.entity_key in unresolved_canonical_failures:
                unresolved_failed_run_items += 1

        return {
            "teams": int(session.query(func.count(Team.team_id)).scalar() or 0),
            "players": int(session.query(func.count(Player.player_id)).scalar() or 0),
            "games": canonical_games,
            "canonical_games": canonical_games,
            "canonical_historical_games": canonical_historical_games,
            "extra_canonical_games": extra_canonical_games,
            "canonical_game_coverage_pct": canonical_coverage,
            "source_payloads": int(session.query(func.count(SourcePayload.id)).scalar() or 0),
            "event_mappings": total_events,
            "mapped_events": mapped_events,
            "player_prop_snapshots": int(session.query(func.count(PlayerPropSnapshot.id)).scalar() or 0),
            "odds_snapshots": int(session.query(func.count(OddsSnapshot.id)).scalar() or 0),
            "historical_game_logs": int(session.query(func.count(HistoricalGameLog.id)).scalar() or 0),
            "historical_games": historical_games,
            "historical_advanced_logs": int(session.query(func.count(HistoricalAdvancedLog.id)).scalar() or 0),
            "enriched_games": enriched_games,
            "enrichment_coverage_pct": enrichment_coverage,
            "team_rotation_games": int(session.query(func.count(TeamRotationGame.id)).scalar() or 0),
            "player_rotation_games": int(session.query(func.count(PlayerRotationGame.id)).scalar() or 0),
            "player_rotation_stints": int(session.query(func.count(PlayerRotationStint.id)).scalar() or 0),
            "rotation_games": rotation_games,
            "rotation_coverage_pct": rotation_coverage,
            "rotation_queue_pending": rotation_queue_pending,
            "rotation_queue_retry": rotation_queue_retry,
            "rotation_queue_quarantined": rotation_queue_quarantined,
            "rotation_queue_due_now": rotation_queue_due_now,
            "rotation_recent_failure_counts": rotation_recent_failure_counts,
            "live_game_snapshots": int(session.query(func.count(LiveGameSnapshot.id)).scalar() or 0),
            "live_player_snapshots": int(session.query(func.count(LivePlayerSnapshot.id)).scalar() or 0),
            "failed_runs": failed_runs,
            "failed_run_items": failed_run_items,
            "unresolved_failed_run_items": unresolved_failed_run_items,
        }


def get_recent_run_item_failures(limit: int = 20) -> list[dict[str, str | int | None]]:
    with session_scope() as session:
        rows = (
            session.query(IngestionRunItem)
            .filter(IngestionRunItem.status == "failed")
            .order_by(IngestionRunItem.created_at.desc())
            .limit(limit)
            .all()
        )

    return [
        {
            "run_id": row.run_id,
            "entity_type": row.entity_type,
            "entity_key": row.entity_key,
            "stage": row.stage,
            "error_text": row.error_text,
        }
        for row in rows
    ]
