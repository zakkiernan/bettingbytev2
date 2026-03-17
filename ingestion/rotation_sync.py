from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, func, or_

from database.db import session_scope
from database.models import HistoricalGameLog, IngestionRunItem, PlayerRotationGame, RotationSyncState
from ingestion.rotation_provider import ROTATION_EXPECTED_MINUTES_FLOOR

ROTATION_SYNC_STATUS_PENDING = "pending"
ROTATION_SYNC_STATUS_RETRY = "retry"
ROTATION_SYNC_STATUS_SUCCESS = "success"
ROTATION_SYNC_STATUS_QUARANTINED = "quarantined"

ROTATION_SYNC_BASE_COOLDOWN_MINUTES = int(os.getenv("ROTATION_SYNC_BASE_COOLDOWN_MINUTES", "30"))
ROTATION_SYNC_QUARANTINE_AFTER = int(os.getenv("ROTATION_SYNC_QUARANTINE_AFTER", "5"))
ROTATION_SYNC_MAX_RETRY_GAMES_PER_BATCH = int(os.getenv("ROTATION_SYNC_MAX_RETRY_GAMES_PER_BATCH", "2"))

_ROTATION_COOLDOWN_MULTIPLIERS = (1, 4, 16, 48, 144)


def _utcnow() -> datetime:
    return datetime.utcnow()


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


def rotation_cooldown_for_failure_count(consecutive_failures: int) -> timedelta:
    if consecutive_failures <= 0:
        return timedelta(0)
    index = min(consecutive_failures - 1, len(_ROTATION_COOLDOWN_MULTIPLIERS) - 1)
    return timedelta(minutes=ROTATION_SYNC_BASE_COOLDOWN_MINUTES * _ROTATION_COOLDOWN_MULTIPLIERS[index])


def infer_rotation_error_type(error_text: str | None) -> str | None:
    if not error_text:
        return None

    normalized = error_text.lower()
    if "timed out" in normalized or "timeout" in normalized:
        return "timeout"
    if "empty response" in normalized:
        return "empty_response"
    if "non-json" in normalized or "text/html" in normalized or "html" in normalized:
        return "non_json_response"
    if "http 429" in normalized or "http 5" in normalized:
        return "http_429_or_5xx"
    if "source missing game" in normalized or "page not found" in normalized:
        return "source_missing_game"
    if "unexpected schema" in normalized or "missing expected result sets" in normalized or "response root was not a json object" in normalized:
        return "unexpected_schema"
    if "jsondecodeerror" in normalized or "invalid json" in normalized or "malformed json" in normalized or "expecting value" in normalized:
        return "other_parse_error"
    return "other_parse_error"


def _historical_game_rows(session, season: str, specific_game_ids: set[str] | None = None) -> dict[str, dict[str, Any]]:
    expected_rotation_case = case(
        (
            or_(
                HistoricalGameLog.minutes.is_(None),
                HistoricalGameLog.minutes >= ROTATION_EXPECTED_MINUTES_FLOOR,
            ),
            1,
        ),
        else_=0,
    )
    rows = (
        session.query(
            HistoricalGameLog.game_id.label("game_id"),
            func.count(HistoricalGameLog.player_id).label("historical_players"),
            func.sum(expected_rotation_case).label("expected_rotation_players"),
            func.min(HistoricalGameLog.game_date).label("game_date"),
        )
        .group_by(HistoricalGameLog.game_id)
        .all()
    )

    historical_games: dict[str, dict[str, Any]] = {}
    for row in rows:
        game_id = str(row.game_id)
        if specific_game_ids is not None and game_id not in specific_game_ids:
            continue
        if not _matches_season(row.game_date, season):
            continue
        historical_games[game_id] = {
            "historical_players": int(row.historical_players),
            "expected_rotation_players": int(row.expected_rotation_players or 0),
            "game_date": row.game_date,
        }
    return historical_games


def _rotation_player_counts(session, game_ids: set[str]) -> dict[str, int]:
    if not game_ids:
        return {}
    rows = (
        session.query(
            PlayerRotationGame.game_id.label("game_id"),
            func.count(PlayerRotationGame.player_id).label("rotation_players"),
        )
        .filter(PlayerRotationGame.game_id.in_(game_ids))
        .group_by(PlayerRotationGame.game_id)
        .all()
    )
    return {str(row.game_id): int(row.rotation_players) for row in rows}


def _load_existing_states(session, game_ids: set[str]) -> dict[str, RotationSyncState]:
    if not game_ids:
        return {}
    return {
        state.game_id: state
        for state in session.query(RotationSyncState).filter(RotationSyncState.game_id.in_(game_ids)).all()
    }


def _parse_metrics_json(metrics_json: str | None) -> dict[str, Any]:
    if not metrics_json:
        return {}
    try:
        parsed = json.loads(metrics_json)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def load_rotation_success_coverage(session, game_ids: set[str]) -> dict[str, dict[str, int]]:
    if not game_ids:
        return {}

    rows = (
        session.query(IngestionRunItem)
        .filter(
            IngestionRunItem.stage == "game_rotation",
            IngestionRunItem.status == "success",
            IngestionRunItem.entity_key.in_(game_ids),
        )
        .order_by(IngestionRunItem.entity_key, IngestionRunItem.created_at.desc())
        .all()
    )

    coverage_by_game: dict[str, dict[str, int]] = {}
    for row in rows:
        game_id = str(row.entity_key)
        if game_id in coverage_by_game:
            continue
        metrics = _parse_metrics_json(row.metrics_json)
        if not metrics:
            continue

        coverage: dict[str, int] = {}
        for key in (
            "expected_player_count",
            "historical_player_count",
            "mapped_player_count",
            "covered_player_count",
            "zero_window_player_count",
        ):
            coerced = _coerce_int(metrics.get(key))
            if coerced is not None:
                coverage[key] = coerced

        if coverage:
            coverage_by_game[game_id] = coverage

    return coverage_by_game


def rotation_missing_player_count(
    historical_row: dict[str, Any],
    rotation_player_count: int,
    coverage_metrics: dict[str, int] | None = None,
) -> int:
    expected_players = _coerce_int(historical_row.get("expected_rotation_players"))
    if expected_players is None or expected_players <= 0:
        expected_players = max(_coerce_int(historical_row.get("historical_players")) or 0, 0)

    covered_players = max(int(rotation_player_count or 0), 0)
    if coverage_metrics:
        covered_players = max(
            covered_players,
            max(_coerce_int(coverage_metrics.get("mapped_player_count")) or 0, 0),
            max(_coerce_int(coverage_metrics.get("covered_player_count")) or 0, 0),
        )

    return max(expected_players - covered_players, 0)


def _load_rotation_run_history(session, game_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not game_ids:
        return {}

    rows = (
        session.query(IngestionRunItem)
        .filter(
            IngestionRunItem.stage == "game_rotation",
            IngestionRunItem.entity_key.in_(game_ids),
        )
        .order_by(IngestionRunItem.entity_key, IngestionRunItem.created_at.desc())
        .all()
    )

    grouped: dict[str, list[IngestionRunItem]] = {}
    for row in rows:
        grouped.setdefault(str(row.entity_key), []).append(row)

    history: dict[str, dict[str, Any]] = {}
    for game_id, items in grouped.items():
        latest_item = items[0]
        consecutive_failures = 0
        latest_failed_item: IngestionRunItem | None = None
        last_success_at: datetime | None = None

        for item in items:
            if item.status == "failed":
                consecutive_failures += 1
                if latest_failed_item is None:
                    latest_failed_item = item
                continue
            if item.status == "success":
                last_success_at = item.created_at
                break

        history[game_id] = {
            "last_attempted_at": latest_item.created_at,
            "last_run_id": latest_item.run_id,
            "last_success_at": last_success_at,
            "consecutive_failures": consecutive_failures,
            "last_error_text": latest_failed_item.error_text if latest_failed_item is not None else None,
            "last_error_type": infer_rotation_error_type(latest_failed_item.error_text if latest_failed_item is not None else None),
        }
    return history


def _apply_success_seed(state: RotationSyncState, season: str, history: dict[str, Any] | None) -> None:
    state.season = season
    state.status = ROTATION_SYNC_STATUS_SUCCESS
    state.consecutive_failures = 0
    state.next_retry_at = None
    state.last_error_type = None
    state.last_error_text = None
    if history is not None:
        state.attempt_count = max(int(state.attempt_count or 0), int(history.get("consecutive_failures") or 0))
        state.last_succeeded_at = history.get("last_success_at") or state.last_succeeded_at
        state.last_run_id = history.get("last_run_id") or state.last_run_id
        state.last_attempted_at = history.get("last_attempted_at") or state.last_attempted_at


def _apply_pending_seed(state: RotationSyncState, season: str) -> None:
    state.season = season
    if state.status != ROTATION_SYNC_STATUS_PENDING:
        state.status = ROTATION_SYNC_STATUS_PENDING
    if int(state.attempt_count or 0) == 0:
        state.consecutive_failures = 0
        state.last_attempted_at = None
        state.last_run_id = None
    state.next_retry_at = None
    state.last_error_type = None
    state.last_error_text = None


def _apply_failure_seed(state: RotationSyncState, season: str, history: dict[str, Any]) -> None:
    consecutive_failures = int(history.get("consecutive_failures") or 0)
    last_attempted_at = history.get("last_attempted_at")
    last_error_type = history.get("last_error_type")

    state.season = season
    state.attempt_count = max(int(state.attempt_count or 0), consecutive_failures)
    state.consecutive_failures = max(int(state.consecutive_failures or 0), consecutive_failures)
    state.last_attempted_at = last_attempted_at
    state.last_run_id = history.get("last_run_id")
    state.last_error_type = last_error_type
    state.last_error_text = history.get("last_error_text")
    if state.last_succeeded_at is None:
        state.last_succeeded_at = history.get("last_success_at")

    if last_error_type == "source_missing_game" or state.consecutive_failures >= ROTATION_SYNC_QUARANTINE_AFTER:
        state.status = ROTATION_SYNC_STATUS_QUARANTINED
        state.next_retry_at = None
    else:
        state.status = ROTATION_SYNC_STATUS_RETRY
        if last_attempted_at is not None:
            state.next_retry_at = last_attempted_at + rotation_cooldown_for_failure_count(state.consecutive_failures)
        else:
            state.next_retry_at = _utcnow() + rotation_cooldown_for_failure_count(state.consecutive_failures)


def seed_rotation_sync_states(season: str, specific_game_ids: list[str] | None = None) -> dict[str, int]:
    specific_game_id_set = {str(game_id) for game_id in specific_game_ids} if specific_game_ids is not None else None

    with session_scope() as session:
        historical_games = _historical_game_rows(session, season=season, specific_game_ids=specific_game_id_set)
        game_ids = set(historical_games.keys())
        if not game_ids:
            return {
                "seeded_games": 0,
                "created_states": 0,
                "success_states": 0,
                "pending_states": 0,
                "retry_states": 0,
                "quarantined_states": 0,
            }

        rotation_counts = _rotation_player_counts(session, game_ids)
        existing_states = _load_existing_states(session, game_ids)
        history = _load_rotation_run_history(session, game_ids)

        created_states = 0
        status_counts = {
            ROTATION_SYNC_STATUS_SUCCESS: 0,
            ROTATION_SYNC_STATUS_PENDING: 0,
            ROTATION_SYNC_STATUS_RETRY: 0,
            ROTATION_SYNC_STATUS_QUARANTINED: 0,
        }

        for game_id in sorted(game_ids):
            state = existing_states.get(game_id)
            if state is None:
                state = RotationSyncState(game_id=game_id, season=season)
                session.add(state)
                existing_states[game_id] = state
                created_states += 1

            latest_history = history.get(game_id)
            if rotation_counts.get(game_id, 0) > 0:
                _apply_success_seed(state, season, latest_history)
            elif latest_history is not None and int(latest_history.get("consecutive_failures") or 0) > 0:
                _apply_failure_seed(state, season, latest_history)
            elif state.status in {ROTATION_SYNC_STATUS_RETRY, ROTATION_SYNC_STATUS_QUARANTINED} and int(state.attempt_count or 0) > 0:
                state.season = season
            else:
                _apply_pending_seed(state, season)

            status_counts[state.status] = status_counts.get(state.status, 0) + 1

        return {
            "seeded_games": len(game_ids),
            "created_states": created_states,
            "success_states": status_counts[ROTATION_SYNC_STATUS_SUCCESS],
            "pending_states": status_counts[ROTATION_SYNC_STATUS_PENDING],
            "retry_states": status_counts[ROTATION_SYNC_STATUS_RETRY],
            "quarantined_states": status_counts[ROTATION_SYNC_STATUS_QUARANTINED],
        }


def enqueue_rotation_games(game_ids: list[str], season: str) -> int:
    deduped_game_ids = sorted({str(game_id) for game_id in game_ids if game_id})
    if not deduped_game_ids:
        return 0

    with session_scope() as session:
        existing_states = _load_existing_states(session, set(deduped_game_ids))
        queued_games = 0
        for game_id in deduped_game_ids:
            state = existing_states.get(game_id)
            if state is None:
                session.add(
                    RotationSyncState(
                        game_id=game_id,
                        season=season,
                        status=ROTATION_SYNC_STATUS_PENDING,
                        attempt_count=0,
                        consecutive_failures=0,
                    )
                )
                queued_games += 1
                continue

            state.season = season
            if state.status in {ROTATION_SYNC_STATUS_SUCCESS, ROTATION_SYNC_STATUS_RETRY, ROTATION_SYNC_STATUS_QUARANTINED}:
                continue
            if state.status != ROTATION_SYNC_STATUS_PENDING:
                state.status = ROTATION_SYNC_STATUS_PENDING
                queued_games += 1

    return queued_games


def select_rotation_sync_batch(
    season: str,
    batch_size: int,
    specific_game_ids: list[str] | None = None,
    force_retry: bool = False,
    include_partial_success: bool = False,
    exclude_game_ids: list[str] | None = None,
) -> dict[str, Any]:
    specific_game_id_set = {str(game_id) for game_id in specific_game_ids} if specific_game_ids is not None else None
    excluded_game_id_set = {str(game_id) for game_id in exclude_game_ids} if exclude_game_ids is not None else set()
    now = _utcnow()

    with session_scope() as session:
        historical_games = _historical_game_rows(session, season=season, specific_game_ids=specific_game_id_set)
        game_ids = set(historical_games.keys())
        if not game_ids:
            return {
                "selected_game_ids": [],
                "pending_games_selected": 0,
                "retry_games_selected": 0,
                "partial_success_games_selected": 0,
                "skipped_cooldown_games": 0,
                "quarantined_games": 0,
            }

        rotation_counts = _rotation_player_counts(session, game_ids)
        existing_states = _load_existing_states(session, game_ids)
        success_coverage = load_rotation_success_coverage(session, game_ids)

        retry_candidates: list[tuple[datetime, str]] = []
        pending_candidates: list[tuple[int, str]] = []
        partial_success_candidates: list[tuple[int, datetime, str]] = []
        skipped_cooldown_games = 0
        quarantined_games = 0

        for game_id, row in historical_games.items():
            if excluded_game_id_set and game_id in excluded_game_id_set:
                continue

            state = existing_states.get(game_id)
            if state is None:
                continue

            missing_players = rotation_missing_player_count(
                row,
                rotation_counts.get(game_id, 0),
                success_coverage.get(game_id),
            )
            if missing_players <= 0:
                continue

            if state.status == ROTATION_SYNC_STATUS_SUCCESS:
                if include_partial_success:
                    partial_success_candidates.append((-missing_players, state.last_succeeded_at or datetime.min, game_id))
                continue
            if state.status == ROTATION_SYNC_STATUS_QUARANTINED:
                if force_retry and specific_game_id_set is not None and game_id in specific_game_id_set:
                    retry_candidates.append((state.next_retry_at or datetime.min, game_id))
                else:
                    quarantined_games += 1
                continue
            if state.status == ROTATION_SYNC_STATUS_RETRY:
                if force_retry and specific_game_id_set is not None and game_id in specific_game_id_set:
                    retry_candidates.append((state.next_retry_at or datetime.min, game_id))
                    continue
                if state.next_retry_at is None or state.next_retry_at <= now:
                    retry_candidates.append((state.next_retry_at or datetime.min, game_id))
                else:
                    skipped_cooldown_games += 1
                continue
            if state.status == ROTATION_SYNC_STATUS_PENDING:
                pending_candidates.append((-missing_players, game_id))

        retry_candidates.sort(key=lambda item: (item[0], item[1]))
        pending_candidates.sort(key=lambda item: (item[0], item[1]))
        partial_success_candidates.sort(key=lambda item: (item[0], item[1], item[2]))

        retry_limit = batch_size if force_retry and specific_game_id_set is not None else min(batch_size, ROTATION_SYNC_MAX_RETRY_GAMES_PER_BATCH)
        selected_retry = [game_id for _, game_id in retry_candidates[:retry_limit]]
        remaining_slots = max(batch_size - len(selected_retry), 0)
        selected_pending = [game_id for _, game_id in pending_candidates[:remaining_slots]]
        remaining_slots = max(remaining_slots - len(selected_pending), 0)
        selected_partial_success = [
            game_id for _, _, game_id in partial_success_candidates[:remaining_slots]
        ]

        return {
            "selected_game_ids": selected_retry + selected_pending + selected_partial_success,
            "pending_games_selected": len(selected_pending),
            "retry_games_selected": len(selected_retry),
            "partial_success_games_selected": len(selected_partial_success),
            "skipped_cooldown_games": skipped_cooldown_games,
            "quarantined_games": quarantined_games,
        }


def record_rotation_sync_attempt(
    game_id: str,
    season: str,
    *,
    successful: bool,
    run_id: int | None = None,
    error_type: str | None = None,
    error_text: str | None = None,
) -> None:
    with session_scope() as session:
        state = session.get(RotationSyncState, game_id)
        if state is None:
            state = RotationSyncState(game_id=game_id, season=season)
            session.add(state)

        now = _utcnow()
        state.season = season
        state.attempt_count = int(state.attempt_count or 0) + 1
        state.last_attempted_at = now
        state.last_run_id = run_id

        if successful:
            state.status = ROTATION_SYNC_STATUS_SUCCESS
            state.consecutive_failures = 0
            state.last_succeeded_at = now
            state.next_retry_at = None
            state.last_error_type = None
            state.last_error_text = None
            return

        state.consecutive_failures = int(state.consecutive_failures or 0) + 1
        state.last_error_type = error_type
        state.last_error_text = error_text
        if error_type == "source_missing_game" or state.consecutive_failures >= ROTATION_SYNC_QUARANTINE_AFTER:
            state.status = ROTATION_SYNC_STATUS_QUARANTINED
            state.next_retry_at = None
        else:
            state.status = ROTATION_SYNC_STATUS_RETRY
            state.next_retry_at = now + rotation_cooldown_for_failure_count(state.consecutive_failures)

