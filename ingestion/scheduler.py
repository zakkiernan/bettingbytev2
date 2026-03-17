from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import MetaData, Table, select

from database.db import session_scope
from ingestion.jobs import (
    bootstrap_backend,
    get_current_mode,
    process_rotation_sync_queue,
    repair_current_signal_snapshots,
    sync_daily_team_defense,
    sync_live_state_and_markets,
    sync_postgame_enrichment,
    sync_pregame_markets,
    sync_prop_snapshot_phase,
    sync_scheduled_official_injury_report,
)
from ingestion.nba_client import get_todays_games_bundle

logger = logging.getLogger(__name__)

SCHEDULER_TIMEZONE = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
PREGAME_MARKET_INTERVAL_MINUTES = 15
PREGAME_MARKET_LOOKAHEAD = timedelta(hours=6)
PREGAME_MARKET_EARLIEST_START_ET = time(hour=11, minute=0)
OFFICIAL_INJURY_REPORT_INTERVAL_MINUTES = 15
OFFICIAL_INJURY_REPORT_LOOKAHEAD = timedelta(hours=6)
OFFICIAL_INJURY_REPORT_EARLIEST_START_ET = time(hour=8, minute=0)

PREGAME_PROP_SNAPSHOT_OFFSETS = {
    "early": timedelta(hours=4),
    "late": timedelta(hours=1),
    "tip": timedelta(0),
}
TIP_SNAPSHOT_GRACE_PERIOD = timedelta(minutes=30)

_postgame_complete = False


def _coerce_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _coerce_et_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(SCHEDULER_TIMEZONE)


def _resolve_first_tip_utc(games: list[dict[str, Any]]) -> datetime | None:
    tips = [game.get("game_time_utc") or game.get("game_date") for game in games]
    valid_tips = [tip for tip in tips if isinstance(tip, datetime)]
    return min(valid_tips, default=None)


def _resolve_tip_window_et(games: list[dict[str, Any]]) -> tuple[datetime, datetime] | None:
    tips = [_coerce_et_datetime(tip) for tip in (game.get("game_time_utc") or game.get("game_date") for game in games) if isinstance(tip, datetime)]
    if not tips:
        return None
    return min(tips), max(tips)


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
        table = Table("player_prop_snapshots", MetaData(), autoload_with=session.bind)
        if "snapshot_phase" not in table.c:
            logger.info("Skipping phased prop snapshot lookup because player_prop_snapshots has no snapshot_phase column")
            return True

        return (
            session.execute(
                select(table.c.id)
                .where(
                    table.c.game_id.in_(game_ids),
                    table.c.is_live.is_(False),
                    table.c.snapshot_phase == snapshot_phase,
                )
                .limit(1)
            ).scalar_one_or_none()
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

    current_time = _coerce_utc_datetime(now_utc or datetime.now(tz=ZoneInfo("UTC")))
    snapshot_phase = _select_due_snapshot_phase(current_time, _coerce_utc_datetime(first_tip_utc))
    if snapshot_phase is None:
        return

    game_ids = [str(game["game_id"]) for game in games if game.get("game_id")]
    if _snapshot_phase_already_captured(game_ids, snapshot_phase):
        logger.info("Skipping %s prop snapshot because it has already been captured for today's slate", snapshot_phase)
        return

    logger.info("Capturing %s prop snapshot for slate with first tip at %s", snapshot_phase, first_tip_utc.isoformat())
    sync_prop_snapshot_phase(snapshot_phase)


def _select_pregame_market_window(now_et: datetime, games: list[dict[str, Any]]) -> tuple[datetime, datetime] | None:
    tip_window = _resolve_tip_window_et(games)
    if tip_window is None:
        return None

    localized_now = now_et.astimezone(SCHEDULER_TIMEZONE) if now_et.tzinfo else now_et.replace(tzinfo=SCHEDULER_TIMEZONE)
    first_tip_et, last_tip_et = tip_window
    earliest_start_et = datetime.combine(first_tip_et.date(), PREGAME_MARKET_EARLIEST_START_ET, tzinfo=SCHEDULER_TIMEZONE)
    window_start = max(earliest_start_et, first_tip_et - PREGAME_MARKET_LOOKAHEAD)
    window_end = last_tip_et
    if window_start <= localized_now <= window_end:
        return window_start, window_end
    return None


def _select_injury_report_window(now_et: datetime, games: list[dict[str, Any]]) -> tuple[datetime, datetime] | None:
    tip_window = _resolve_tip_window_et(games)
    if tip_window is None:
        return None

    localized_now = now_et.astimezone(SCHEDULER_TIMEZONE) if now_et.tzinfo else now_et.replace(tzinfo=SCHEDULER_TIMEZONE)
    first_tip_et, last_tip_et = tip_window
    earliest_start_et = datetime.combine(first_tip_et.date(), OFFICIAL_INJURY_REPORT_EARLIEST_START_ET, tzinfo=SCHEDULER_TIMEZONE)
    window_start = max(earliest_start_et, first_tip_et - OFFICIAL_INJURY_REPORT_LOOKAHEAD)
    window_end = last_tip_et
    if window_start <= localized_now <= window_end:
        return window_start, window_end
    return None


def run_scheduled_pregame_markets_cycle(now_et: datetime | None = None) -> None:
    games, _ = get_todays_games_bundle()
    if not games:
        logger.info("Skipping scheduled pregame market capture because there are no games on today's slate")
        return

    current_time = now_et or datetime.now(tz=SCHEDULER_TIMEZONE)
    active_window = _select_pregame_market_window(current_time, games)
    if active_window is None:
        logger.info("Skipping scheduled pregame market capture outside the active slate window")
        return

    window_start, window_end = active_window
    logger.info(
        "Running scheduled pregame market capture for slate window %s to %s ET",
        window_start.strftime("%Y-%m-%d %H:%M"),
        window_end.strftime("%Y-%m-%d %H:%M"),
    )
    sync_pregame_markets()


def run_signal_snapshot_repair_cycle(now_et: datetime | None = None) -> None:
    games, _ = get_todays_games_bundle()
    if not games:
        logger.info("Skipping signal snapshot repair because there are no games on today's slate")
        return

    current_time = now_et or datetime.now(tz=SCHEDULER_TIMEZONE)
    active_window = _select_pregame_market_window(current_time, games)
    if active_window is None:
        logger.info("Skipping signal snapshot repair outside the active slate window")
        return

    window_start, window_end = active_window
    logger.info(
        "Running signal snapshot repair for slate window %s to %s ET",
        window_start.strftime("%Y-%m-%d %H:%M"),
        window_end.strftime("%Y-%m-%d %H:%M"),
    )
    repair_current_signal_snapshots()


def _select_due_injury_report_slot(now_et: datetime) -> tuple[date, time]:
    localized_now = now_et.astimezone(SCHEDULER_TIMEZONE) if now_et.tzinfo else now_et.replace(tzinfo=SCHEDULER_TIMEZONE)
    floored_minute = localized_now.minute - (localized_now.minute % OFFICIAL_INJURY_REPORT_INTERVAL_MINUTES)
    scheduled_time = localized_now.replace(minute=floored_minute, second=0, microsecond=0)
    return scheduled_time.date(), scheduled_time.timetz().replace(tzinfo=None)


def run_scheduled_official_injury_report_cycle(now_et: datetime | None = None) -> None:
    games, _ = get_todays_games_bundle()
    if not games:
        logger.info("Skipping official injury report capture because there are no games on today's slate")
        return

    current_time = now_et or datetime.now(tz=SCHEDULER_TIMEZONE)
    active_window = _select_injury_report_window(current_time, games)
    if active_window is None:
        logger.info("Skipping official injury report capture outside the active slate window")
        return

    window_start, window_end = active_window
    report_date, report_time_et = _select_due_injury_report_slot(current_time)
    logger.info(
        "Running scheduled official injury report capture for %s %s ET within window %s to %s ET",
        report_date.isoformat(),
        report_time_et.strftime("%H:%M"),
        window_start.strftime("%Y-%m-%d %H:%M"),
        window_end.strftime("%Y-%m-%d %H:%M"),
    )
    sync_scheduled_official_injury_report(report_date, report_time_et)


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
        logger.info("Pregame mode active; waiting for scheduled pre-tip market capture jobs")
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

    scheduler = BackgroundScheduler(timezone=SCHEDULER_TIMEZONE)
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
    scheduler.add_job(
        run_scheduled_official_injury_report_cycle,
        "cron",
        hour="8-23",
        minute="0,15,30,45",
        id="official_injury_report_cycle",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        run_scheduled_pregame_markets_cycle,
        "cron",
        hour="11-23",
        minute="0,15,30,45",
        id="scheduled_pregame_markets_cycle",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        run_signal_snapshot_repair_cycle,
        "cron",
        hour="11-23",
        minute="5,20,35,50",
        id="signal_snapshot_repair_cycle",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started")
    return scheduler
