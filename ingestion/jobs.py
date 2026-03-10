from __future__ import annotations

import traceback
from datetime import date, timedelta
from typing import Any, Callable

from database.db import init_db
from ingestion.fanduel_client import fetch_current_prop_board
from ingestion.nba_client import (
    DEFAULT_SEASON,
    get_advanced_boxscore_bundle,
    get_boxscore_summary_bundle,
    get_game_rotation_bundle,
    get_historical_player_game_logs_bundle,
    get_live_boxscore_bundle,
    get_live_scoreboard_bundle,
    get_player_tracking_bundle,
    get_static_players,
    get_static_teams,
    get_team_defensive_stats_bundle,
    get_todays_games_bundle,
    normalize_game_summary,
)
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
    write_live_game_snapshots,
    write_live_player_snapshots,
    write_odds_snapshot,
    write_player_rotation_games,
    write_player_rotation_stints,
    write_players,
    write_prop_snapshot,
    write_source_payloads,
    write_sportsbook_event_mappings,
    write_team_defensive_stats,
    write_team_rotation_games,
    write_teams,
)

STATUS_SCHEDULED = 1
STATUS_LIVE = 2
STATUS_FINISHED = 3


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


def _sync_pregame_markets_impl(run_id: int | None = None) -> dict[str, int]:
    _sync_reference_entities_impl(run_id=run_id)

    board = fetch_current_prop_board()
    props = board["props"]
    event_mappings = board["event_mappings"]
    payloads = board.get("payloads", [])
    unmapped_events = sum(1 for mapping in event_mappings if not mapping.get("nba_game_id"))

    schedule_games_today, schedule_payloads_today = get_todays_games_bundle()
    schedule_games_tomorrow, schedule_payloads_tomorrow = get_todays_games_bundle(date.today() + timedelta(days=1))

    write_source_payloads(payloads + schedule_payloads_today + schedule_payloads_tomorrow)
    write_games(schedule_games_today + schedule_games_tomorrow)
    write_players(_players_from_rows(props))
    write_sportsbook_event_mappings(event_mappings)
    write_prop_snapshot(props, is_live=False)
    write_odds_snapshot(props, market_phase="pregame")

    return {
        "props": len(props),
        "event_mappings": len(event_mappings),
        "unmapped_events": unmapped_events,
        "raw_payloads": len(payloads) + len(schedule_payloads_today) + len(schedule_payloads_tomorrow),
    }


def sync_pregame_markets() -> dict[str, int]:
    return _run_logged_job("sync_pregame_markets", _sync_pregame_markets_impl)


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
    write_source_payloads(live_payloads)
    write_games(live_games)
    write_live_game_snapshots(live_games)

    live_player_snapshots: list[dict[str, Any]] = []
    live_boxscore_failures: list[str] = []
    box_payload_count = 0
    active_games = [game for game in live_games if game.get("game_status") == STATUS_LIVE]
    for game in active_games:
        snapshots, box_payloads = get_live_boxscore_bundle(game["game_id"])
        write_source_payloads(box_payloads)
        box_payload_count += len(box_payloads)
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
        "raw_payloads": len(payloads) + len(live_payloads) + box_payload_count,
    }


def sync_live_state_and_markets() -> dict[str, Any]:
    return _run_logged_job("sync_live_state_and_markets", _sync_live_state_and_markets_impl)


def _sync_game_rotation_for_game(game_id: str, run_id: int | None = None) -> dict[str, Any]:
    result = get_game_rotation_bundle(game_id)
    write_source_payloads(result.payloads)

    if not result.player_rotation_games:
        error_text = result.error_text or "GameRotation returned no player rotation summaries."
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
        }

    write_players(_players_from_rows(result.player_rotation_games))
    write_team_rotation_games(result.team_rotation_games)
    write_player_rotation_games(result.player_rotation_games)
    write_player_rotation_stints(result.rotations)

    if run_id is not None:
        create_ingestion_run_item(
            run_id=run_id,
            entity_type="game",
            entity_key=game_id,
            stage="game_rotation",
            status="success",
            metrics={
                "rotation_stints": len(result.rotations),
                "team_rotation_games": len(result.team_rotation_games),
                "player_rotation_games": len(result.player_rotation_games),
                "raw_payloads": len(result.payloads),
            },
        )

    return {
        "rotation_stints": len(result.rotations),
        "team_rotation_games": len(result.team_rotation_games),
        "player_rotation_games": len(result.player_rotation_games),
        "raw_payloads": len(result.payloads),
        "error_type": None,
        "error_text": None,
        "error_details": {},
    }



def _process_rotation_sync_queue_impl(
    season: str = DEFAULT_SEASON,
    batch_size: int = 5,
    max_batches: int | None = None,
    specific_game_ids: list[str] | None = None,
    force_retry: bool = False,
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
            "skipped_cooldown_games": 0,
            "quarantined_games": 0,
            "force_retry": force_retry,
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
    skipped_cooldown_games = 0
    quarantined_games = 0
    batch_counter = 0

    while True:
        if max_batches is not None and batch_counter >= max_batches:
            break

        selection = select_rotation_sync_batch(
            season=season,
            batch_size=batch_size,
            specific_game_ids=specific_game_ids,
            force_retry=force_retry,
        )
        selected_game_ids = selection["selected_game_ids"]
        if not selected_game_ids:
            skipped_cooldown_games += int(selection.get("skipped_cooldown_games", 0))
            quarantined_games += int(selection.get("quarantined_games", 0))
            break

        batch_counter += 1
        pending_games_selected += int(selection.get("pending_games_selected", 0))
        retry_games_selected += int(selection.get("retry_games_selected", 0))
        skipped_cooldown_games += int(selection.get("skipped_cooldown_games", 0))
        quarantined_games += int(selection.get("quarantined_games", 0))

        for game_id in selected_game_ids:
            metrics = _sync_game_rotation_for_game(game_id, run_id=run_id)
            processed_games += 1
            payload_count += int(metrics.get("raw_payloads", 0))
            successful = int(metrics.get("player_rotation_games", 0)) > 0
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
        "skipped_cooldown_games": skipped_cooldown_games,
        "quarantined_games": quarantined_games,
        "force_retry": force_retry,
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
    )


def _sync_postgame_enrichment_impl(run_id: int | None = None) -> dict[str, Any]:
    live_games, live_payloads = get_live_scoreboard_bundle()
    write_source_payloads(live_payloads)
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
    write_source_payloads(payloads)
    write_team_defensive_stats(defensive_stats)
    return {"season": season, "team_defense_rows": len(defensive_stats), "raw_payloads": len(payloads)}


def sync_daily_team_defense(season: str = DEFAULT_SEASON) -> dict[str, Any]:
    return _run_logged_job("sync_daily_team_defense", _sync_daily_team_defense_impl, season)


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
    write_source_payloads(payloads)
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
    rotation_queue_games_enqueued = 0
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

            write_source_payloads(summary_payloads + advanced_payloads + tracking_payloads)

            normalized_game = normalize_game_summary(summary_data or {}, season=season)
            if normalized_game:
                write_games([normalized_game])

            merged_logs = _merge_advanced_and_tracking(advanced_logs, tracking_logs)
            processed_games += 1
            enqueued_count = enqueue_rotation_games([game_id], season=season)
            rotation_queue_games_enqueued += enqueued_count
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
                        "rotation_queue_games_enqueued": enqueued_count,
                    },
                    error_text="Advanced and tracking endpoints returned no rows.",
                )
                continue

            write_players(_players_from_rows(merged_logs))
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
                    "merged_players": len(merged_logs),
                    "rotation_queue_games_enqueued": enqueued_count,
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
        "rotation_stints": 0,
        "player_rotation_games": 0,
        "team_rotation_games": 0,
        "rotation_queue_games_enqueued": rotation_queue_games_enqueued,
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
