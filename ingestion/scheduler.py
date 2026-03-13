from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler

from database.db import session_scope
from database.models import PlayerPropSnapshot
from ingestion.jobs import (
    bootstrap_backend,
    get_current_mode,
    process_rotation_sync_queue,
    sync_daily_team_defense,
    sync_live_state_and_markets,
    sync_postgame_enrichment,
    sync_pregame_markets,
    sync_prop_snapshot_phase,
)
from ingestion.nba_client import get_todays_games_bundle

logger = logging.getLogger(__name__)

PREGAME_PROP_SNAPSHOT_OFFSETS = {
    "early": timedelta(hours=4),
    "late": timedelta(hours=1),
    "tip": timedelta(0),
}
TIP_SNAPSHOT_GRACE_PERIOD = timedelta(minutes=30)

_postgame_complete = False


def _resolve_first_tip_utc(games: list[dict[str, Any]]) -> datetime | None:
    tips = [game.get("game_time_utc") or game.get("game_date") for game in games]
    valid_tips = [tip for tip in tips if isinstance(tip, datetime)]
    return min(valid_tips, default=None)


def _select_due_snapshot_phase(now_utc: datetime, first_tip_utc: datetime) -> str | None:
    early_target = first_tip_utc - PREGAME_PROP_SNAPSHOT_OFFSETS["early"]
    late_target = first_tip_utc - PREGAME_PROP_SNAPSHOT_OFFSETS["late"]
    tip_target = first_tip_utc

    if early_target <= now_utc < late_target:
        return "early"
    if late_target <= now_utc < tip_target:
        return "late"
    if tip_target <= now_utc < tip_target + TIP_SNAPSHOT_GRACE_PERIOD:
        return "tip"
    return None


def _snapshot_phase_already_captured(game_ids: list[str], snapshot_phase: str) -> bool:
    if not game_ids:
        return False

    with session_scope() as session:
        return (
            session.query(PlayerPropSnapshot.id)
            .filter(
                PlayerPropSnapshot.game_id.in_(game_ids),
                PlayerPropSnapshot.is_live.is_(False),
                PlayerPropSnapshot.snapshot_phase == snapshot_phase,
            )
            .first()
            is not None
        )


def run_prop_snapshot_schedule_cycle(now_utc: datetime | None = None) -> None:
    games, _ = get_todays_games_bundle()
    if not games:
        logger.info("Skipping prop snapshot cycle because there are no games on today's slate")
        return

    first_tip_utc = _resolve_first_tip_utc(games)
    if first_tip_utc is None:
        logger.warning("Skipping prop snapshot cycle because today's slate has no scheduled tip time")
        return

    current_time = now_utc or datetime.utcnow()
    snapshot_phase = _select_due_snapshot_phase(current_time, first_tip_utc)
    if snapshot_phase is None:
        return

    game_ids = [str(game["game_id"]) for game in games if game.get("game_id")]
    if _snapshot_phase_already_captured(game_ids, snapshot_phase):
        logger.info("Skipping %s prop snapshot because it has already been captured for today's slate", snapshot_phase)
        return

    logger.info("Capturing %s prop snapshot for slate with first tip at %s", snapshot_phase, first_tip_utc.isoformat())
    sync_prop_snapshot_phase(snapshot_phase)


def run_scheduler_cycle() -> None:
    global _postgame_complete

    mode = get_current_mode()
    logger.info("Scheduler mode: %s", mode)

    if mode == "idle":
        return

    if mode == "live":
        _postgame_complete = False
        sync_live_state_and_markets()
        return

    if mode == "pregame":
        _postgame_complete = False
        sync_pregame_markets()
        return

    if mode == "postgame" and not _postgame_complete:
        sync_postgame_enrichment()
        _postgame_complete = True
        logger.info("Postgame enrichment completed for the current slate")


def run_rotation_queue_cycle() -> None:
    mode = get_current_mode()
    if mode == "live":
        logger.info("Skipping rotation queue cycle during live mode")
        return
    if mode == "postgame" and not _postgame_complete:
        logger.info("Skipping rotation queue cycle until postgame enrichment completes")
        return

    process_rotation_sync_queue(batch_size=5, max_batches=1)


def start_scheduler() -> BackgroundScheduler:
    bootstrap_backend()

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_scheduler_cycle,
        "interval",
        seconds=30,
        id="master_cycle",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        sync_daily_team_defense,
        "cron",
        hour=9,
        minute=0,
        id="daily_team_defense",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        run_rotation_queue_cycle,
        "interval",
        minutes=5,
        id="rotation_queue_cycle",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        run_prop_snapshot_schedule_cycle,
        "interval",
        minutes=5,
        id="prop_snapshot_cycle",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started")
    return scheduler
