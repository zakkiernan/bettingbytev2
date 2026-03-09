from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from ingestion.jobs import (
    bootstrap_backend,
    get_current_mode,
    sync_daily_team_defense,
    sync_live_state_and_markets,
    sync_postgame_enrichment,
    sync_pregame_markets,
)

logger = logging.getLogger(__name__)

_postgame_complete = False


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

    scheduler.start()
    logger.info("Scheduler started")
    return scheduler
