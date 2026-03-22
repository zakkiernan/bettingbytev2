from __future__ import annotations

import traceback
from datetime import date, datetime, time, timedelta
from typing import Any, Callable

import requests

from database.db import init_db
from ingestion.fanduel_client import fetch_current_prop_board
from ingestion.injury_reports import (
    backfill_injury_entry_player_ids as backfill_injury_entry_player_ids_impl,
    backfill_official_injury_reports as backfill_official_injury_reports_impl,
    build_injury_report_url,
    sync_official_injury_report as sync_official_injury_report_impl,
)
from ingestion.pregame_context import build_pregame_context_source_payloads, sync_pregame_context as sync_current_pregame_context
from ingestion.nba_client import (
    DEFAULT_SEASON,
    get_advanced_boxscore_bundle,
    get_boxscore_summary_bundle,
    get_historical_player_game_logs_bundle,
    get_hustle_boxscore_bundle,
    get_lineup_stats_bundle,
    get_live_boxscore_bundle,
    get_live_scoreboard_bundle,
    get_matchup_boxscore_bundle,
    get_player_clutch_stats_bundle,
    get_player_defensive_tracking_bundle,
    get_player_hustle_stats_bundle,
    get_player_on_off_stats_bundle,
    get_player_play_types_bundle,
    get_player_tracking_bundle,
    get_player_tracking_stats_bundle,
    get_player_shot_locations_bundle,
    get_shot_chart_bundle,
    get_static_players,
    get_static_teams,
    get_team_defensive_stats_bundle,
    get_todays_games_bundle,
    get_win_probability_bundle,
    normalize_game_summary,
)
from ingestion.nba.signal_jobs import (
    persist_current_signal_snapshots,
    repair_current_signal_snapshots as repair_current_signal_snapshots_impl,
)
from ingestion.rotation_provider import get_rotation_bundle
from ingestion.rotation_sync import (
    enqueue_rotation_games,
    record_rotation_sync_attempt,
    seed_rotation_sync_states,
    select_rotation_sync_batch,
)
from ingestion.validation import (
    get_missing_canonical_games_from_history,
    get_postgame_enrichment_backlog,
    get_rotation_backlog,
    summarize_ingestion_health,
)
from ingestion.writer import (
    create_ingestion_run,
    create_ingestion_run_item,
    finalize_ingestion_run,
    write_advanced_logs,
    write_games,
    write_historical_game_logs,
    write_hustle_stats_boxscores,
    write_lineup_stats,
    write_live_game_snapshots,
    write_live_player_snapshots,
    write_odds_snapshot,
    write_player_clutch_stats,
    write_player_defensive_tracking,
    write_player_hustle_stats,
    write_player_on_off_stats,
    write_player_play_types,
    write_player_rotation_games,
    write_player_rotation_stints,
    write_player_shot_location_stats,
    write_player_tracking_stats,
    write_players,
    write_prop_snapshot,
    write_matchup_boxscores,
    write_shot_chart_details,
    write_source_payloads,
    write_sportsbook_event_mappings,
    write_team_defensive_stats,
    write_team_rotation_games,
    write_teams,
    write_win_probability_entries,
)

STATUS_SCHEDULED = 1
STATUS_LIVE = 2
STATUS_FINISHED = 3
PREGAME_PROP_SNAPSHOT_PHASES = ("early", "late", "tip")

def _normalize_metrics(result: dict[str, Any] | int | None) -> dict[str, Any]:
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    return {"count": result}


def _run_logged_job(job_name: str, fn: Callable[..., dict[str, Any] | int | None], *args: Any, **kwargs: Any) -> dict[str, Any] | int | None:
    run_id = create_ingestion_run(job_name, metrics={"args": list(args), "kwargs": kwargs})
    try:
        result = fn(*args, run_id=run_id, **kwargs)
        metrics = _normalize_metrics(result)
        metrics["run_id"] = run_id
        finalize_ingestion_run(run_id, status="success", metrics=metrics)
        if isinstance(result, dict):
            result = {**result, "run_id": run_id}
        return result
    except Exception as exc:
        finalize_ingestion_run(
            run_id,
            status="failed",
            metrics={"run_id": run_id},
            error_text="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        )
        raise


def _merge_advanced_and_tracking(
    advanced_logs: list[dict[str, Any]],
    tracking_logs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}

    for row in advanced_logs + tracking_logs:
        key = (row["game_id"], row["player_id"])
        existing = merged.setdefault(key, {"game_id": row["game_id"], "player_id": row["player_id"]})
        for field, value in row.items():
            if value is not None:
                existing[field] = value

    return list(merged.values())


def _players_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        player_id = row.get("player_id")
        player_name = row.get("player_name")
        if not player_id or not player_name:
            continue
        first_name, _, last_name = player_name.partition(" ")
        deduped[player_id] = {
            "player_id": str(player_id),
            "full_name": player_name,
            "first_name": first_name,
            "last_name": last_name or None,
            "is_active": True,
        }
    return list(deduped.values())


def _extract_upstream_failures(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for payload in payloads:
        payload_body = payload.get("payload")
        if not isinstance(payload_body, dict) or payload_body.get("status") != "error":
            continue
        failures.append(
            {
                "payload_type": str(payload.get("payload_type") or payload_body.get("endpoint") or "unknown"),
                "endpoint": str(payload_body.get("endpoint") or payload.get("payload_type") or "unknown"),
                "identifier": payload_body.get("identifier") or payload.get("external_id"),
                "error_type": payload_body.get("error_type"),
                "error_message": str(payload_body.get("error_message") or "Unknown upstream failure"),
            }
        )
    return failures


def _record_upstream_failures(
    payloads: list[dict[str, Any]],
    *,
    run_id: int | None,
    stage: str,
    entity_type: str,
    default_entity_key: str,
    extra_metrics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    failures = _extract_upstream_failures(payloads)
    if run_id is None:
        return failures

    for failure in failures:
        metrics = dict(extra_metrics or {})
        metrics["payload_type"] = failure["payload_type"]
        metrics["endpoint"] = failure["endpoint"]
        if failure["identifier"] is not None:
            metrics["identifier"] = failure["identifier"]
        if failure["error_type"] is not None:
            metrics["error_type"] = failure["error_type"]
        create_ingestion_run_item(
            run_id=run_id,
            entity_type=entity_type,
            entity_key=str(failure["identifier"] or default_entity_key),
            stage=stage,
            status="failed",
            metrics=metrics,
            error_text=failure["error_message"],
        )

    return failures


def _write_payloads_with_failure_audit(
    payloads: list[dict[str, Any]],
    *,
    run_id: int | None,
    stage: str,
    entity_type: str,
    default_entity_key: str,
    extra_metrics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    write_source_payloads(payloads)
    return _record_upstream_failures(
        payloads,
        run_id=run_id,
        stage=stage,
        entity_type=entity_type,
        default_entity_key=default_entity_key,
        extra_metrics=extra_metrics,
    )


def _sync_reference_entities_impl(run_id: int | None = None) -> dict[str, int]:
    teams = get_static_teams()
    players = get_static_players()
    write_teams(teams)
    write_players(players)
    return {"teams": len(teams), "players": len(players)}


def _reconcile_canonical_games_from_history_impl(
    season: str | None = DEFAULT_SEASON,
    run_id: int | None = None,
    specific_game_ids: set[str] | None = None,
) -> dict[str, int]:
    inferred_games = get_missing_canonical_games_from_history(season=season)
    if specific_game_ids is not None:
        inferred_games = [game for game in inferred_games if game["game_id"] in specific_game_ids]

    if not inferred_games:
        return {"reconciled_games": 0}

    write_games(inferred_games)
    if run_id is not None:
        for game in inferred_games:
            create_ingestion_run_item(
                run_id=run_id,
                entity_type="game",
                entity_key=str(game["game_id"]),
                stage="canonical_game_reconciliation",
                status="success",
            )

    return {"reconciled_games": len(inferred_games)}


def sync_reference_entities() -> dict[str, int]:
    return _run_logged_job("sync_reference_entities", _sync_reference_entities_impl)


def reconcile_canonical_games_from_history(season: str | None = DEFAULT_SEASON) -> dict[str, int]:
    return _run_logged_job("reconcile_canonical_games_from_history", _reconcile_canonical_games_from_history_impl, season)


def bootstrap_backend() -> None:
    init_db()


def _sync_prop_snapshot_phase_impl(snapshot_phase: str, run_id: int | None = None) -> dict[str, Any]:
    _sync_reference_entities_impl(run_id=run_id)

    board = fetch_current_prop_board()
    props = board["props"]
    event_mappings = board["event_mappings"]
    payloads = board.get("payloads", [])
    unmapped_events = sum(1 for mapping in event_mappings if not mapping.get("nba_game_id"))

    schedule_games_today, schedule_payloads_today = get_todays_games_bundle()

    upstream_failures = _write_payloads_with_failure_audit(
        payloads + schedule_payloads_today,
        run_id=run_id,
        stage="scoreboard_schedule",
        entity_type="schedule",
        default_entity_key=f"snapshot_phase:{snapshot_phase}",
        extra_metrics={"snapshot_phase": snapshot_phase},
    )
    write_games(schedule_games_today)
    write_players(_players_from_rows(props))
    write_sportsbook_event_mappings(event_mappings)
    write_prop_snapshot(props, is_live=False, snapshot_phase=snapshot_phase)
    write_odds_snapshot(props, market_phase=snapshot_phase)

    return {
        "snapshot_phase": snapshot_phase,
        "props": len(props),
        "event_mappings": len(event_mappings),
        "unmapped_events": unmapped_events,
        "raw_payloads": len(payloads) + len(schedule_payloads_today),
        "schedule_games": len(schedule_games_today),
        "upstream_failures": len(upstream_failures),
    }


def sync_prop_snapshot_phase(snapshot_phase: str) -> dict[str, Any]:
    if snapshot_phase not in PREGAME_PROP_SNAPSHOT_PHASES and snapshot_phase != "current":
        raise ValueError(f"Unsupported prop snapshot phase: {snapshot_phase}")
    return _run_logged_job(f"sync_prop_snapshot_{snapshot_phase}", _sync_prop_snapshot_phase_impl, snapshot_phase)


def _sync_odds_accumulation_impl(run_id: int | None = None) -> dict[str, Any]:
    _sync_reference_entities_impl(run_id=run_id)

    board = fetch_current_prop_board()
    props = board["props"]
    event_mappings = board["event_mappings"]
    payloads = board.get("payloads", [])
    unmapped_events = sum(1 for mapping in event_mappings if not mapping.get("nba_game_id"))

    schedule_games_today, schedule_payloads_today = get_todays_games_bundle()
    schedule_games_tomorrow, schedule_payloads_tomorrow = get_todays_games_bundle(date.today() + timedelta(days=1))

    upstream_failures = _write_payloads_with_failure_audit(
        payloads + schedule_payloads_today + schedule_payloads_tomorrow,
        run_id=run_id,
        stage="scoreboard_schedule",
        entity_type="schedule",
        default_entity_key="odds_accumulation",
        extra_metrics={"market_phase": "accumulation"},
    )
    write_games(schedule_games_today + schedule_games_tomorrow)
    write_players(_players_from_rows(props))
    write_sportsbook_event_mappings(event_mappings)
    write_odds_snapshot(props, market_phase="accumulation")

    return {
        "props": len(props),
        "event_mappings": len(event_mappings),
        "unmapped_events": unmapped_events,
        "raw_payloads": len(payloads) + len(schedule_payloads_today) + len(schedule_payloads_tomorrow),
        "schedule_games": len(schedule_games_today) + len(schedule_games_tomorrow),
        "market_phase": "accumulation",
        "upstream_failures": len(upstream_failures),
    }


def sync_odds_accumulation() -> dict[str, Any]:
    return _run_logged_job("sync_odds_accumulation", _sync_odds_accumulation_impl)

def _sync_pregame_markets_impl(run_id: int | None = None) -> dict[str, int]:
    _sync_reference_entities_impl(run_id=run_id)

    board = fetch_current_prop_board()
    props = board["props"]
    event_mappings = board["event_mappings"]
    payloads = board.get("payloads", [])
    unmapped_events = sum(1 for mapping in event_mappings if not mapping.get("nba_game_id"))

    schedule_games_today, schedule_payloads_today = get_todays_games_bundle()
    schedule_games_tomorrow, schedule_payloads_tomorrow = get_todays_games_bundle(date.today() + timedelta(days=1))

    upstream_failures = _write_payloads_with_failure_audit(
        payloads + schedule_payloads_today + schedule_payloads_tomorrow,
        run_id=run_id,
        stage="scoreboard_schedule",
        entity_type="schedule",
        default_entity_key="pregame_markets",
    )
    write_games(schedule_games_today + schedule_games_tomorrow)
    write_players(_players_from_rows(props))
    write_sportsbook_event_mappings(event_mappings)
    write_prop_snapshot(props, is_live=False)
    write_odds_snapshot(props, market_phase="pregame")

    pregame_context_result = sync_current_pregame_context(captured_at=board.get("captured_at"), stat_type="points")
    pregame_context_payloads = build_pregame_context_source_payloads(pregame_context_result)
    _write_payloads_with_failure_audit(
        pregame_context_payloads,
        run_id=run_id,
        stage="pregame_context_payload",
        entity_type="pregame_context",
        default_entity_key="current",
    )
    signal_snapshot_metrics = persist_current_signal_snapshots()
    if run_id is not None:
        create_ingestion_run_item(
            run_id=run_id,
            entity_type="signal_phase",
            entity_key="current",
            stage="stats_signal_snapshot",
            status="success",
            metrics=signal_snapshot_metrics,
        )

    return {
        "props": len(props),
        "event_mappings": len(event_mappings),
        "unmapped_events": unmapped_events,
        "raw_payloads": len(payloads) + len(schedule_payloads_today) + len(schedule_payloads_tomorrow) + len(pregame_context_payloads),
        "pregame_context_games": len(pregame_context_result.payload.get("games", [])),
        "pregame_context_rows": len(pregame_context_result.feature_rows),
        "pregame_context_attached_count": int(pregame_context_result.attachment_metrics.get("attached_count", 0)),
        "pregame_context_attached_pct": float(pregame_context_result.attachment_metrics.get("attached_pct", 0.0)),
        "pregame_context_overlap_game_count": int(pregame_context_result.attachment_metrics.get("overlap_game_count", 0)),
        "pregame_context_missing_game_count": len(pregame_context_result.attachment_metrics.get("missing_context_game_ids", [])),
        "pregame_context_projected_unavailable_count": int(pregame_context_result.attachment_metrics.get("projected_unavailable_count", 0)),
        "pregame_context_high_late_scratch_risk_count": int(pregame_context_result.attachment_metrics.get("high_late_scratch_risk_count", 0)),
        "upstream_failures": len(upstream_failures),
        **signal_snapshot_metrics,
    }


def sync_pregame_markets() -> dict[str, int]:
    return _run_logged_job("sync_pregame_markets", _sync_pregame_markets_impl)


def _repair_current_signal_snapshots_impl(force: bool = False, run_id: int | None = None) -> dict[str, Any]:
    return repair_current_signal_snapshots_impl(force=force)


def repair_current_signal_snapshots(force: bool = False) -> dict[str, Any]:
    return _run_logged_job(
        "repair_current_signal_snapshots",
        _repair_current_signal_snapshots_impl,
        force,
    )


def _sync_live_state_and_markets_impl(run_id: int | None = None) -> dict[str, Any]:
    _sync_reference_entities_impl(run_id=run_id)

    board = fetch_current_prop_board()
    props = board["props"]
    event_mappings = board["event_mappings"]
    payloads = board.get("payloads", [])
    unmapped_events = sum(1 for mapping in event_mappings if not mapping.get("nba_game_id"))

    write_source_payloads(payloads)
    write_players(_players_from_rows(props))
    write_sportsbook_event_mappings(event_mappings)
    write_prop_snapshot(props, is_live=True)
    write_odds_snapshot(props, market_phase="live")

    live_games, live_payloads = get_live_scoreboard_bundle()
    live_scoreboard_failures = _write_payloads_with_failure_audit(
        live_payloads,
        run_id=run_id,
        stage="live_scoreboard",
        entity_type="feed",
        default_entity_key="live_scoreboard",
    )
    write_games(live_games)
    write_live_game_snapshots(live_games)

    live_player_snapshots: list[dict[str, Any]] = []
    live_boxscore_failures: list[str] = []
    box_payload_count = 0
    active_games = [game for game in live_games if game.get("game_status") == STATUS_LIVE]
    for game in active_games:
        snapshots, box_payloads = get_live_boxscore_bundle(game["game_id"])
        box_failures = _write_payloads_with_failure_audit(
            box_payloads,
            run_id=run_id,
            stage="live_boxscore",
            entity_type="game",
            default_entity_key=game["game_id"],
            extra_metrics={"game_id": game["game_id"]},
        )
        box_payload_count += len(box_payloads)
        if box_failures:
            live_boxscore_failures.append(game["game_id"])
            continue
        if not snapshots:
            live_boxscore_failures.append(game["game_id"])
            create_ingestion_run_item(
                run_id=run_id,
                entity_type="game",
                entity_key=game["game_id"],
                stage="live_boxscore",
                status="failed",
                error_text="Live boxscore returned no player snapshots.",
            )
            continue

        live_player_snapshots.extend(snapshots)
        create_ingestion_run_item(
            run_id=run_id,
            entity_type="game",
            entity_key=game["game_id"],
            stage="live_boxscore",
            status="success",
            metrics={"player_snapshots": len(snapshots)},
        )

    write_players(_players_from_rows(live_player_snapshots))
    write_live_player_snapshots(live_player_snapshots)

    return {
        "props": len(props),
        "event_mappings": len(event_mappings),
        "unmapped_events": unmapped_events,
        "live_games": len(live_games),
        "active_games": len(active_games),
        "live_player_snapshots": len(live_player_snapshots),
        "live_boxscore_failures": len(live_boxscore_failures),
        "live_scoreboard_failures": len(live_scoreboard_failures),
        "raw_payloads": len(payloads) + len(live_payloads) + box_payload_count,
    }


def sync_live_state_and_markets() -> dict[str, Any]:
    return _run_logged_job("sync_live_state_and_markets", _sync_live_state_and_markets_impl)


def _sync_rotation_for_game(game_id: str, run_id: int | None = None) -> dict[str, Any]:
    result = get_rotation_bundle(game_id)
    write_source_payloads(result.payloads)

    if not result.player_rotation_games:
        error_text = result.error_text or "Rotation scraper returned no player rotation summaries."
        failure_metrics: dict[str, Any] = {"raw_payloads": len(result.payloads)}
        if result.error_type is not None:
            failure_metrics["error_type"] = result.error_type
        failure_metrics.update(result.error_details)
        if run_id is not None:
            create_ingestion_run_item(
                run_id=run_id,
                entity_type="game",
                entity_key=game_id,
                stage="game_rotation",
                status="failed",
                metrics=failure_metrics,
                error_text=error_text,
            )
        return {
            "rotation_stints": 0,
            "team_rotation_games": 0,
            "player_rotation_games": 0,
            "raw_payloads": len(result.payloads),
            "error_type": result.error_type,
            "error_text": error_text,
            "error_details": dict(result.error_details),
            "complete": False,
        }

    write_players(_players_from_rows(result.player_rotation_games))
    write_team_rotation_games(result.team_rotation_games)
    write_player_rotation_games(result.player_rotation_games)
    write_player_rotation_stints(result.rotations)

    success_metrics = {
        "rotation_stints": len(result.rotations),
        "team_rotation_games": len(result.team_rotation_games),
        "player_rotation_games": len(result.player_rotation_games),
        "raw_payloads": len(result.payloads),
        **dict(result.coverage_metrics),
    }

    if run_id is not None:
        create_ingestion_run_item(
            run_id=run_id,
            entity_type="game",
            entity_key=game_id,
            stage="game_rotation",
            status="success",
            metrics=success_metrics,
        )

    return {
        "rotation_stints": len(result.rotations),
        "team_rotation_games": len(result.team_rotation_games),
        "player_rotation_games": len(result.player_rotation_games),
        "raw_payloads": len(result.payloads),
        "coverage_metrics": dict(result.coverage_metrics),
        "error_type": None,
        "error_text": None,
        "error_details": {},
        "complete": True,
    }


def _process_rotation_sync_queue_impl(
    season: str = DEFAULT_SEASON,
    batch_size: int = 5,
    max_batches: int | None = None,
    specific_game_ids: list[str] | None = None,
    force_retry: bool = False,
    include_partial_success: bool = False,
    run_id: int | None = None,
) -> dict[str, Any]:
    seed_metrics = seed_rotation_sync_states(season=season, specific_game_ids=specific_game_ids)
    total_candidates = int(seed_metrics.get("seeded_games", 0))
    if total_candidates == 0:
        return {
            "season": season,
            "games_seen": 0,
            "games_processed": 0,
            "successful_games": 0,
            "failed_games": 0,
            "rotation_stints": 0,
            "player_rotation_games": 0,
            "team_rotation_games": 0,
            "raw_payloads": 0,
            "batches": 0,
            "remaining_backlog": 0,
            "pending_games_selected": 0,
            "retry_games_selected": 0,
            "partial_success_games_selected": 0,
            "skipped_cooldown_games": 0,
            "quarantined_games": 0,
            "force_retry": force_retry,
            "include_partial_success": include_partial_success,
            **seed_metrics,
        }

    processed_games = 0
    successful_games = 0
    failed_games = 0
    rotation_stints_written = 0
    player_rotation_games_written = 0
    team_rotation_games_written = 0
    payload_count = 0
    pending_games_selected = 0
    retry_games_selected = 0
    partial_success_games_selected = 0
    skipped_cooldown_games = 0
    quarantined_games = 0
    batch_counter = 0
    remaining_specific_game_ids = [str(game_id) for game_id in specific_game_ids] if specific_game_ids is not None else None
    processed_game_ids: set[str] = set()

    while True:
        if max_batches is not None and batch_counter >= max_batches:
            break

        selection = select_rotation_sync_batch(
            season=season,
            batch_size=batch_size,
            specific_game_ids=remaining_specific_game_ids,
            force_retry=force_retry,
            include_partial_success=include_partial_success,
            exclude_game_ids=sorted(processed_game_ids) if processed_game_ids else None,
        )
        selected_game_ids = selection["selected_game_ids"]
        if not selected_game_ids:
            skipped_cooldown_games += int(selection.get("skipped_cooldown_games", 0))
            quarantined_games += int(selection.get("quarantined_games", 0))
            break

        batch_counter += 1
        pending_games_selected += int(selection.get("pending_games_selected", 0))
        retry_games_selected += int(selection.get("retry_games_selected", 0))
        partial_success_games_selected += int(selection.get("partial_success_games_selected", 0))
        skipped_cooldown_games += int(selection.get("skipped_cooldown_games", 0))
        quarantined_games += int(selection.get("quarantined_games", 0))

        for game_id in selected_game_ids:
            processed_game_ids.add(str(game_id))
            metrics = _sync_rotation_for_game(game_id, run_id=run_id)
            processed_games += 1
            payload_count += int(metrics.get("raw_payloads", 0))
            successful = bool(metrics.get("complete"))
            record_rotation_sync_attempt(
                game_id,
                season,
                successful=successful,
                run_id=run_id,
                error_type=metrics.get("error_type"),
                error_text=metrics.get("error_text"),
            )
            if not successful:
                failed_games += 1
                continue
            successful_games += 1
            rotation_stints_written += int(metrics.get("rotation_stints", 0))
            player_rotation_games_written += int(metrics.get("player_rotation_games", 0))
            team_rotation_games_written += int(metrics.get("team_rotation_games", 0))

        if remaining_specific_game_ids is not None:
            processed_specific_game_ids = {str(game_id) for game_id in selected_game_ids}
            remaining_specific_game_ids = [
                game_id for game_id in remaining_specific_game_ids if game_id not in processed_specific_game_ids
            ]

    remaining_backlog_rows = get_rotation_backlog(season=season)
    if specific_game_ids is not None:
        allowed = {str(game_id) for game_id in specific_game_ids}
        remaining_backlog_rows = [row for row in remaining_backlog_rows if str(row["game_id"]) in allowed]

    return {
        "season": season,
        "games_seen": total_candidates,
        "games_processed": processed_games,
        "successful_games": successful_games,
        "failed_games": failed_games,
        "rotation_stints": rotation_stints_written,
        "player_rotation_games": player_rotation_games_written,
        "team_rotation_games": team_rotation_games_written,
        "raw_payloads": payload_count,
        "batches": batch_counter,
        "remaining_backlog": len(remaining_backlog_rows),
        "pending_games_selected": pending_games_selected,
        "retry_games_selected": retry_games_selected,
        "partial_success_games_selected": partial_success_games_selected,
        "skipped_cooldown_games": skipped_cooldown_games,
        "quarantined_games": quarantined_games,
        "force_retry": force_retry,
        "include_partial_success": include_partial_success,
        **seed_metrics,
    }



def process_rotation_sync_queue(
    season: str = DEFAULT_SEASON,
    batch_size: int = 5,
    max_batches: int | None = None,
    specific_game_ids: list[str] | None = None,
    force_retry: bool = False,
) -> dict[str, Any]:
    return _run_logged_job(
        "process_rotation_sync_queue",
        _process_rotation_sync_queue_impl,
        season,
        batch_size,
        max_batches,
        specific_game_ids,
        force_retry,
    )



def backfill_historical_rotations(
    season: str = DEFAULT_SEASON,
    batch_size: int = 25,
    max_batches: int | None = None,
    specific_game_ids: list[str] | None = None,
) -> dict[str, Any]:
    return _run_logged_job(
        "backfill_historical_rotations",
        _process_rotation_sync_queue_impl,
        season,
        batch_size,
        max_batches,
        specific_game_ids,
        False,
        True,
    )


def _sync_postgame_enrichment_impl(run_id: int | None = None) -> dict[str, Any]:
    live_games, live_payloads = get_live_scoreboard_bundle()
    _write_payloads_with_failure_audit(
        live_payloads,
        run_id=run_id,
        stage="live_scoreboard",
        entity_type="feed",
        default_entity_key="postgame_live_scoreboard",
    )
    finished_game_ids = [game["game_id"] for game in live_games if game.get("game_status") == STATUS_FINISHED]
    return _backfill_postgame_enrichment_impl(
        season=DEFAULT_SEASON,
        run_id=run_id,
        specific_game_ids=finished_game_ids,
        batch_size=max(len(finished_game_ids), 1),
    )


def sync_postgame_enrichment() -> dict[str, Any]:
    return _run_logged_job("sync_postgame_enrichment", _sync_postgame_enrichment_impl)


def _sync_daily_team_defense_impl(season: str = DEFAULT_SEASON, run_id: int | None = None) -> dict[str, Any]:
    defensive_stats, payloads = get_team_defensive_stats_bundle(season=season)
    upstream_failures = _write_payloads_with_failure_audit(
        payloads,
        run_id=run_id,
        stage="team_defense_fetch",
        entity_type="season",
        default_entity_key=season,
        extra_metrics={"season": season},
    )
    write_team_defensive_stats(defensive_stats)
    return {"season": season, "team_defense_rows": len(defensive_stats), "raw_payloads": len(payloads), "upstream_failures": len(upstream_failures)}


def sync_daily_team_defense(season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return _run_logged_job("sync_daily_team_defense", _sync_daily_team_defense_impl, season)


def _sync_player_clutch_stats_impl(season: str = DEFAULT_SEASON, run_id: int | None = None) -> dict[str, Any]:
    rows, payloads = get_player_clutch_stats_bundle(season=season)
    upstream_failures = _write_payloads_with_failure_audit(
        payloads,
        run_id=run_id,
        stage="player_clutch_fetch",
        entity_type="season",
        default_entity_key=season,
        extra_metrics={"season": season},
    )
    write_players(_players_from_rows(rows))
    write_player_clutch_stats(rows)
    return {"season": season, "player_clutch_stats_rows": len(rows), "raw_payloads": len(payloads), "upstream_failures": len(upstream_failures)}


def sync_player_clutch_stats(season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return _run_logged_job("sync_player_clutch_stats", _sync_player_clutch_stats_impl, season)


def _sync_player_hustle_stats_impl(season: str = DEFAULT_SEASON, run_id: int | None = None) -> dict[str, Any]:
    rows, payloads = get_player_hustle_stats_bundle(season=season)
    upstream_failures = _write_payloads_with_failure_audit(
        payloads,
        run_id=run_id,
        stage="player_hustle_fetch",
        entity_type="season",
        default_entity_key=season,
        extra_metrics={"season": season},
    )
    write_players(_players_from_rows(rows))
    write_player_hustle_stats(rows)
    return {"season": season, "player_hustle_stats_rows": len(rows), "raw_payloads": len(payloads), "upstream_failures": len(upstream_failures)}


def sync_player_hustle_stats(season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return _run_logged_job("sync_player_hustle_stats", _sync_player_hustle_stats_impl, season)


def _sync_player_play_types_impl(season: str = DEFAULT_SEASON, run_id: int | None = None) -> dict[str, Any]:
    rows, payloads = get_player_play_types_bundle(season=season)
    upstream_failures = _write_payloads_with_failure_audit(
        payloads,
        run_id=run_id,
        stage="player_play_types_fetch",
        entity_type="season",
        default_entity_key=season,
        extra_metrics={"season": season},
    )
    write_players(_players_from_rows(rows))
    write_player_play_types(rows)
    return {"season": season, "player_play_type_rows": len(rows), "raw_payloads": len(payloads), "upstream_failures": len(upstream_failures)}


def sync_player_play_types(season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return _run_logged_job("sync_player_play_types", _sync_player_play_types_impl, season)


def _sync_player_tracking_stats_impl(season: str = DEFAULT_SEASON, run_id: int | None = None) -> dict[str, Any]:
    rows, payloads = get_player_tracking_stats_bundle(season=season)
    upstream_failures = _write_payloads_with_failure_audit(
        payloads,
        run_id=run_id,
        stage="player_tracking_stats_fetch",
        entity_type="season",
        default_entity_key=season,
        extra_metrics={"season": season},
    )
    write_players(_players_from_rows(rows))
    write_player_tracking_stats(rows)
    return {"season": season, "player_tracking_stats_rows": len(rows), "raw_payloads": len(payloads), "upstream_failures": len(upstream_failures)}


def sync_player_tracking_stats(season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return _run_logged_job("sync_player_tracking_stats", _sync_player_tracking_stats_impl, season)


def _sync_player_on_off_stats_impl(season: str = DEFAULT_SEASON, run_id: int | None = None) -> dict[str, Any]:
    rows, payloads = get_player_on_off_stats_bundle(season=season)
    upstream_failures = _write_payloads_with_failure_audit(
        payloads,
        run_id=run_id,
        stage="player_on_off_fetch",
        entity_type="season",
        default_entity_key=season,
        extra_metrics={"season": season},
    )
    write_players(_players_from_rows(rows))
    write_player_on_off_stats(rows)
    return {"season": season, "player_on_off_stats_rows": len(rows), "raw_payloads": len(payloads), "upstream_failures": len(upstream_failures)}


def sync_player_on_off_stats(season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return _run_logged_job("sync_player_on_off_stats", _sync_player_on_off_stats_impl, season)


def _sync_player_defensive_tracking_impl(season: str = DEFAULT_SEASON, run_id: int | None = None) -> dict[str, Any]:
    rows, payloads = get_player_defensive_tracking_bundle(season=season)
    upstream_failures = _write_payloads_with_failure_audit(
        payloads,
        run_id=run_id,
        stage="player_defensive_tracking_fetch",
        entity_type="season",
        default_entity_key=season,
        extra_metrics={"season": season},
    )
    write_players(_players_from_rows(rows))
    write_player_defensive_tracking(rows)
    return {"season": season, "player_defensive_tracking_rows": len(rows), "raw_payloads": len(payloads), "upstream_failures": len(upstream_failures)}


def sync_player_defensive_tracking(season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return _run_logged_job("sync_player_defensive_tracking", _sync_player_defensive_tracking_impl, season)


def _sync_player_shot_locations_impl(season: str = DEFAULT_SEASON, run_id: int | None = None) -> dict[str, Any]:
    rows, payloads = get_player_shot_locations_bundle(season=season)
    upstream_failures = _write_payloads_with_failure_audit(
        payloads,
        run_id=run_id,
        stage="player_shot_locations_fetch",
        entity_type="season",
        default_entity_key=season,
        extra_metrics={"season": season},
    )
    write_players(_players_from_rows(rows))
    write_player_shot_location_stats(rows)
    return {"season": season, "player_shot_location_rows": len(rows), "raw_payloads": len(payloads), "upstream_failures": len(upstream_failures)}


def sync_player_shot_locations(season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return _run_logged_job("sync_player_shot_locations", _sync_player_shot_locations_impl, season)


def _sync_lineup_stats_impl(season: str = DEFAULT_SEASON, run_id: int | None = None) -> dict[str, Any]:
    rows, payloads = get_lineup_stats_bundle(season=season)
    upstream_failures = _write_payloads_with_failure_audit(
        payloads,
        run_id=run_id,
        stage="lineup_stats_fetch",
        entity_type="season",
        default_entity_key=season,
        extra_metrics={"season": season},
    )
    write_lineup_stats(rows)
    return {"season": season, "lineup_stats_rows": len(rows), "raw_payloads": len(payloads), "upstream_failures": len(upstream_failures)}


def sync_lineup_stats(season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return _run_logged_job("sync_lineup_stats", _sync_lineup_stats_impl, season)


def _backfill_historical_game_logs_impl(
    season: str = DEFAULT_SEASON,
    season_type_all_star: str = "Regular Season",
    date_from_nullable: str = "",
    date_to_nullable: str = "",
    run_id: int | None = None,
) -> dict[str, Any]:
    _sync_reference_entities_impl(run_id=run_id)

    game_logs, payloads = get_historical_player_game_logs_bundle(
        season=season,
        season_type_all_star=season_type_all_star,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
    )
    upstream_failures = _write_payloads_with_failure_audit(
        payloads,
        run_id=run_id,
        stage="historical_game_logs_fetch",
        entity_type="season",
        default_entity_key=season,
        extra_metrics={"season": season, "season_type": season_type_all_star},
    )
    write_players(_players_from_rows(game_logs))
    write_historical_game_logs(game_logs)
    unique_game_ids = {row["game_id"] for row in game_logs}
    reconciliation = _reconcile_canonical_games_from_history_impl(
        season=season,
        run_id=run_id,
        specific_game_ids=unique_game_ids,
    )
    return {
        "season": season,
        "season_type": season_type_all_star,
        "historical_game_logs": len(game_logs),
        "unique_games": len(unique_game_ids),
        "raw_payloads": len(payloads),
        "upstream_failures": len(upstream_failures),
        **reconciliation,
    }


def backfill_historical_game_logs(
    season: str = DEFAULT_SEASON,
    season_type_all_star: str = "Regular Season",
    date_from_nullable: str = "",
    date_to_nullable: str = "",
) -> dict[str, Any]:
    return _run_logged_job(
        "backfill_historical_game_logs",
        _backfill_historical_game_logs_impl,
        season,
        season_type_all_star,
        date_from_nullable,
        date_to_nullable,
    )


def _backfill_postgame_enrichment_impl(
    season: str = DEFAULT_SEASON,
    batch_size: int = 25,
    max_batches: int | None = None,
    specific_game_ids: list[str] | None = None,
    run_id: int | None = None,
) -> dict[str, Any]:
    backlog_rows = get_postgame_enrichment_backlog(season=season)
    if specific_game_ids is not None:
        allowed = set(specific_game_ids)
        backlog_rows = [row for row in backlog_rows if row["game_id"] in allowed]

    total_candidates = len(backlog_rows)
    if total_candidates == 0:
        reconciliation = _reconcile_canonical_games_from_history_impl(season=season, run_id=run_id)
        return {
            "season": season,
            "games_seen": 0,
            "games_processed": 0,
            "advanced_logs": 0,
            "shot_chart_rows": 0,
            "hustle_boxscore_rows": 0,
            "matchup_boxscore_rows": 0,
            "win_probability_rows": 0,
            "rotation_stints": 0,
            "player_rotation_games": 0,
            "team_rotation_games": 0,
            "rotation_queue_games_enqueued": 0,
            "failed_games": 0,
            "batches": 0,
            **reconciliation,
        }

    processed_games = 0
    successful_games = 0
    failed_games = 0
    written_rows = 0
    shot_chart_rows_written = 0
    hustle_boxscore_rows_written = 0
    matchup_boxscore_rows_written = 0
    win_probability_rows_written = 0
    rotation_queue_games_enqueued = 0
    upstream_failures = 0
    batch_counter = 0

    for offset in range(0, total_candidates, batch_size):
        if max_batches is not None and batch_counter >= max_batches:
            break

        batch_counter += 1
        batch = backlog_rows[offset : offset + batch_size]
        for row in batch:
            game_id = str(row["game_id"])
            summary_data, summary_payloads = get_boxscore_summary_bundle(game_id)
            advanced_logs, advanced_payloads = get_advanced_boxscore_bundle(game_id)
            tracking_logs, tracking_payloads = get_player_tracking_bundle(game_id)
            shot_chart_rows, shot_chart_payloads = get_shot_chart_bundle(game_id)
            hustle_boxscore_rows, hustle_boxscore_payloads = get_hustle_boxscore_bundle(game_id)
            matchup_boxscore_rows, matchup_boxscore_payloads = get_matchup_boxscore_bundle(game_id)
            win_probability_rows, win_probability_payloads = get_win_probability_bundle(game_id)

            source_payloads = (
                summary_payloads
                + advanced_payloads
                + tracking_payloads
                + shot_chart_payloads
                + hustle_boxscore_payloads
                + matchup_boxscore_payloads
                + win_probability_payloads
            )
            source_failures = _write_payloads_with_failure_audit(
                source_payloads,
                run_id=run_id,
                stage="postgame_source_fetch",
                entity_type="game",
                default_entity_key=game_id,
                extra_metrics={"game_id": game_id},
            )
            upstream_failures += len(source_failures)

            normalized_game = normalize_game_summary(summary_data or {}, season=season)
            if normalized_game:
                write_games([normalized_game])

            merged_logs = _merge_advanced_and_tracking(advanced_logs, tracking_logs)
            write_players(_players_from_rows(merged_logs + shot_chart_rows + hustle_boxscore_rows))
            write_shot_chart_details(shot_chart_rows)
            write_hustle_stats_boxscores(hustle_boxscore_rows)
            write_matchup_boxscores(matchup_boxscore_rows)
            write_win_probability_entries(win_probability_rows)

            processed_games += 1
            enqueued_count = enqueue_rotation_games([game_id], season=season)
            rotation_queue_games_enqueued += enqueued_count
            shot_chart_rows_written += len(shot_chart_rows)
            hustle_boxscore_rows_written += len(hustle_boxscore_rows)
            matchup_boxscore_rows_written += len(matchup_boxscore_rows)
            win_probability_rows_written += len(win_probability_rows)
            if not merged_logs:
                failed_games += 1
                create_ingestion_run_item(
                    run_id=run_id,
                    entity_type="game",
                    entity_key=game_id,
                    stage="postgame_enrichment",
                    status="failed",
                    metrics={
                        "historical_players": row["historical_players"],
                        "advanced_players": row["advanced_players"],
                        "tracking_players": len(tracking_logs),
                        "shot_chart_rows": len(shot_chart_rows),
                        "hustle_boxscore_rows": len(hustle_boxscore_rows),
                        "matchup_boxscore_rows": len(matchup_boxscore_rows),
                        "win_probability_rows": len(win_probability_rows),
                        "rotation_queue_games_enqueued": enqueued_count,
                        "upstream_failures": len(source_failures),
                    },
                    error_text="Advanced and tracking endpoints returned no rows.",
                )
                continue

            write_advanced_logs(merged_logs)
            written_rows += len(merged_logs)
            successful_games += 1
            create_ingestion_run_item(
                run_id=run_id,
                entity_type="game",
                entity_key=game_id,
                stage="postgame_enrichment",
                status="success",
                metrics={
                    "historical_players": row["historical_players"],
                    "advanced_players": len(advanced_logs),
                    "tracking_players": len(tracking_logs),
                    "shot_chart_rows": len(shot_chart_rows),
                    "hustle_boxscore_rows": len(hustle_boxscore_rows),
                    "matchup_boxscore_rows": len(matchup_boxscore_rows),
                    "win_probability_rows": len(win_probability_rows),
                    "merged_players": len(merged_logs),
                    "rotation_queue_games_enqueued": enqueued_count,
                    "upstream_failures": len(source_failures),
                },
            )

    reconciliation = _reconcile_canonical_games_from_history_impl(season=season, run_id=run_id)
    return {
        "season": season,
        "games_seen": total_candidates,
        "games_processed": processed_games,
        "successful_games": successful_games,
        "failed_games": failed_games,
        "advanced_logs": written_rows,
        "shot_chart_rows": shot_chart_rows_written,
        "hustle_boxscore_rows": hustle_boxscore_rows_written,
        "matchup_boxscore_rows": matchup_boxscore_rows_written,
        "win_probability_rows": win_probability_rows_written,
        "rotation_stints": 0,
        "player_rotation_games": 0,
        "team_rotation_games": 0,
        "rotation_queue_games_enqueued": rotation_queue_games_enqueued,
        "upstream_failures": upstream_failures,
        "batches": batch_counter,
        "remaining_backlog": max(total_candidates - processed_games, 0),
        **reconciliation,
    }


def backfill_postgame_enrichment(
    season: str = DEFAULT_SEASON,
    batch_size: int = 25,
    max_batches: int | None = None,
    specific_game_ids: list[str] | None = None,
) -> dict[str, Any]:
    return _run_logged_job(
        "backfill_postgame_enrichment",
        _backfill_postgame_enrichment_impl,
        season,
        batch_size,
        max_batches,
        specific_game_ids,
    )


def ingestion_health_report() -> dict[str, Any]:
    return _run_logged_job("ingestion_health_report", lambda run_id=None: summarize_ingestion_health())


def get_current_mode() -> str:
    games, _ = get_live_scoreboard_bundle()
    if not games:
        return "idle"

    statuses = [game.get("game_status") for game in games]
    if STATUS_LIVE in statuses:
        return "live"
    if all(status == STATUS_FINISHED for status in statuses):
        return "postgame"
    if STATUS_SCHEDULED in statuses:
        return "pregame"
    return "idle"


def _sync_official_injury_report_impl(url: str, run_id: int | None = None) -> dict[str, Any]:
    return sync_official_injury_report_impl(url)


def sync_official_injury_report(url: str) -> dict[str, Any]:
    return _run_logged_job("sync_official_injury_report", _sync_official_injury_report_impl, url)


def _sync_scheduled_official_injury_report_impl(
    report_date: date,
    report_time_et: time,
    run_id: int | None = None,
) -> dict[str, Any]:
    url = build_injury_report_url(report_date, report_time_et)
    try:
        result = sync_official_injury_report_impl(url)
    except requests.HTTPError as exc:
        status_code = getattr(exc.response, "status_code", None)
        if status_code in {403, 404}:
            return {
                "status": "not_available",
                "url": url,
                "entries": 0,
                "report_date": report_date.isoformat(),
                "report_time_et": report_time_et.strftime("%H:%M"),
            }
        raise

    return {
        **result,
        "report_date": report_date.isoformat(),
        "report_time_et": report_time_et.strftime("%H:%M"),
    }


def sync_scheduled_official_injury_report(report_date: date, report_time_et: time) -> dict[str, Any]:
    return _run_logged_job(
        "sync_scheduled_official_injury_report",
        _sync_scheduled_official_injury_report_impl,
        report_date,
        report_time_et,
    )


def _backfill_official_injury_reports_impl(
    start_date: date,
    end_date: date,
    report_times: list[str] | None = None,
    delay_seconds: float = 0.0,
    run_id: int | None = None,
) -> dict[str, Any]:
    parsed_times = None
    if report_times is not None:
        parsed_times = [datetime.strptime(value, "%H:%M").time() for value in report_times]
    return backfill_official_injury_reports_impl(
        start_date=start_date,
        end_date=end_date,
        report_times=parsed_times,
        delay_seconds=delay_seconds,
    )


def backfill_official_injury_reports(
    start_date: date,
    end_date: date,
    report_times: list[str] | None = None,
    delay_seconds: float = 0.0,
) -> dict[str, Any]:
    return _run_logged_job(
        "backfill_official_injury_reports",
        _backfill_official_injury_reports_impl,
        start_date,
        end_date,
        report_times,
        delay_seconds,
    )


def _backfill_injury_entry_player_ids_impl(run_id: int | None = None) -> dict[str, Any]:
    return backfill_injury_entry_player_ids_impl()


def backfill_injury_entry_player_ids() -> dict[str, Any]:
    return _run_logged_job(
        "backfill_injury_entry_player_ids",
        _backfill_injury_entry_player_ids_impl,
    )


