from __future__ import annotations

from datetime import date, datetime, time, timezone
from unittest.mock import patch

from ingestion.scheduler import (
    OFFICIAL_INJURY_REPORT_INTERVAL_MINUTES,
    _resolve_first_tip_utc,
    _coerce_utc_datetime,
    _select_injury_report_window,
    _select_pregame_market_window,
    _select_due_injury_report_slot,
    _select_due_snapshot_phase,
    run_odds_accumulation_cycle,
    run_prop_snapshot_schedule_cycle,
    run_signal_snapshot_repair_cycle,
    run_scheduled_official_injury_report_cycle,
    run_scheduled_pregame_markets_cycle,
    run_scheduler_cycle,
    start_scheduler,
)


def test_resolve_first_tip_utc_uses_earliest_scheduled_game() -> None:
    first_tip = _resolve_first_tip_utc(
        [
            {"game_id": "002", "game_time_utc": datetime(2026, 3, 13, 1, 0, 0)},
            {"game_id": "001", "game_time_utc": datetime(2026, 3, 12, 23, 30, 0)},
        ]
    )

    assert first_tip == datetime(2026, 3, 12, 23, 30, 0)


def test_select_due_snapshot_phase_returns_early_within_early_window() -> None:
    first_tip = datetime(2026, 3, 13, 0, 0, 0)

    assert _select_due_snapshot_phase(datetime(2026, 3, 12, 20, 30, 0), first_tip) == "early"


def test_select_due_snapshot_phase_returns_late_within_late_window() -> None:
    first_tip = datetime(2026, 3, 13, 0, 0, 0)

    assert _select_due_snapshot_phase(datetime(2026, 3, 12, 23, 15, 0), first_tip) == "late"


def test_select_due_snapshot_phase_returns_tip_within_grace_period() -> None:
    first_tip = datetime(2026, 3, 13, 0, 0, 0)

    assert _select_due_snapshot_phase(datetime(2026, 3, 13, 0, 20, 0), first_tip) == "tip"


def test_select_due_snapshot_phase_returns_none_outside_all_windows() -> None:
    first_tip = datetime(2026, 3, 13, 0, 0, 0)

    assert _select_due_snapshot_phase(datetime(2026, 3, 12, 19, 0, 0), first_tip) is None
    assert _select_due_snapshot_phase(datetime(2026, 3, 13, 1, 0, 0), first_tip) is None


def test_select_pregame_market_window_starts_at_11am_for_early_tip() -> None:
    active_window = _select_pregame_market_window(
        datetime(2026, 3, 15, 11, 5, 0),
        [{"game_id": "001", "game_time_utc": datetime(2026, 3, 15, 16, 0, 0, tzinfo=timezone.utc)}],
    )

    assert active_window is not None
    window_start, window_end = active_window
    assert window_start.hour == 11
    assert window_start.minute == 0
    assert window_end == datetime(2026, 3, 15, 16, 0, 0, tzinfo=timezone.utc).astimezone(window_end.tzinfo)


def test_select_pregame_market_window_waits_until_six_hours_before_evening_tip() -> None:
    games = [{"game_id": "001", "game_time_utc": datetime(2026, 3, 15, 23, 30, 0, tzinfo=timezone.utc)}]

    assert _select_pregame_market_window(datetime(2026, 3, 15, 13, 15, 0), games) is None
    assert _select_pregame_market_window(datetime(2026, 3, 15, 13, 30, 0), games) is not None


def test_select_pregame_market_window_stays_open_until_latest_tip_on_split_slate() -> None:
    active_window = _select_pregame_market_window(
        datetime(2026, 3, 15, 18, 45, 0),
        [
            {"game_id": "001", "game_time_utc": datetime(2026, 3, 15, 17, 0, 0, tzinfo=timezone.utc)},
            {"game_id": "002", "game_time_utc": datetime(2026, 3, 16, 0, 0, 0, tzinfo=timezone.utc)},
        ],
    )

    assert active_window is not None
    _, window_end = active_window
    assert window_end.hour == 20
    assert window_end.minute == 0


def test_select_injury_report_window_starts_at_8am_for_matinee_tip() -> None:
    active_window = _select_injury_report_window(
        datetime(2026, 3, 15, 8, 15, 0),
        [{"game_id": "001", "game_time_utc": datetime(2026, 3, 15, 16, 0, 0, tzinfo=timezone.utc)}],
    )

    assert active_window is not None
    window_start, window_end = active_window
    assert window_start.hour == 8
    assert window_start.minute == 0
    assert window_end == datetime(2026, 3, 15, 16, 0, 0, tzinfo=timezone.utc).astimezone(window_end.tzinfo)


def test_select_injury_report_window_waits_until_six_hours_before_evening_tip() -> None:
    games = [{"game_id": "001", "game_time_utc": datetime(2026, 3, 15, 23, 30, 0, tzinfo=timezone.utc)}]

    assert _select_injury_report_window(datetime(2026, 3, 15, 13, 15, 0), games) is None
    assert _select_injury_report_window(datetime(2026, 3, 15, 13, 30, 0), games) is not None


def test_select_due_injury_report_slot_rounds_down_to_quarter_hour_within_window() -> None:
    report_date, report_time = _select_due_injury_report_slot(datetime(2026, 3, 15, 19, 44, 12))

    assert report_date == date(2026, 3, 15)
    assert report_time == time(19, 30)


def test_select_due_injury_report_slot_returns_midnight_report_in_opening_window() -> None:
    report_date, report_time = _select_due_injury_report_slot(datetime(2026, 3, 15, 0, OFFICIAL_INJURY_REPORT_INTERVAL_MINUTES - 1, 0))

    assert report_date == date(2026, 3, 15)
    assert report_time == time(0, 0)


def test_coerce_utc_datetime_normalizes_aware_values() -> None:
    aware_value = datetime(2026, 3, 15, 21, 0, 0, tzinfo=timezone.utc)

    assert _coerce_utc_datetime(aware_value) == datetime(2026, 3, 15, 21, 0, 0)


def test_run_scheduled_pregame_markets_cycle_invokes_sync_inside_active_window() -> None:
    with (
        patch(
            "ingestion.scheduler.get_todays_games_bundle",
            return_value=(
                [{"game_id": "001", "game_time_utc": datetime(2026, 3, 15, 16, 0, 0, tzinfo=timezone.utc)}],
                [],
            ),
        ),
        patch("ingestion.scheduler.sync_pregame_markets") as sync_mock,
    ):
        run_scheduled_pregame_markets_cycle(datetime(2026, 3, 15, 11, 15, 0))

    sync_mock.assert_called_once_with()


def test_run_scheduled_pregame_markets_cycle_skips_outside_active_window() -> None:
    with (
        patch(
            "ingestion.scheduler.get_todays_games_bundle",
            return_value=(
                [{"game_id": "001", "game_time_utc": datetime(2026, 3, 16, 2, 30, 0, tzinfo=timezone.utc)}],
                [],
            ),
        ),
        patch("ingestion.scheduler.sync_pregame_markets") as sync_mock,
    ):
        run_scheduled_pregame_markets_cycle(datetime(2026, 3, 15, 12, 45, 0))

    sync_mock.assert_not_called()


def test_run_signal_snapshot_repair_cycle_invokes_repair_inside_active_window() -> None:
    with (
        patch(
            "ingestion.scheduler.get_todays_games_bundle",
            return_value=(
                [{"game_id": "001", "game_time_utc": datetime(2026, 3, 15, 16, 0, 0, tzinfo=timezone.utc)}],
                [],
            ),
        ),
        patch("ingestion.scheduler.repair_current_signal_snapshots") as repair_mock,
    ):
        run_signal_snapshot_repair_cycle(datetime(2026, 3, 15, 11, 20, 0))

    repair_mock.assert_called_once_with()


def test_run_odds_accumulation_cycle_invokes_sync_inside_active_window() -> None:
    with (
        patch(
            "ingestion.scheduler.get_todays_games_bundle",
            return_value=(
                [{"game_id": "001", "game_time_utc": datetime(2026, 3, 15, 16, 0, 0, tzinfo=timezone.utc)}],
                [],
            ),
        ),
        patch("ingestion.scheduler.sync_odds_accumulation") as sync_mock,
    ):
        run_odds_accumulation_cycle(datetime(2026, 3, 15, 11, 30, 0))

    sync_mock.assert_called_once_with()


def test_run_odds_accumulation_cycle_skips_outside_active_window() -> None:
    with (
        patch(
            "ingestion.scheduler.get_todays_games_bundle",
            return_value=(
                [{"game_id": "001", "game_time_utc": datetime(2026, 3, 16, 2, 30, 0, tzinfo=timezone.utc)}],
                [],
            ),
        ),
        patch("ingestion.scheduler.sync_odds_accumulation") as sync_mock,
    ):
        run_odds_accumulation_cycle(datetime(2026, 3, 15, 12, 45, 0))

    sync_mock.assert_not_called()


def test_run_prop_snapshot_schedule_cycle_accepts_aware_tip_times() -> None:
    with (
        patch(
            "ingestion.scheduler.get_todays_games_bundle",
            return_value=(
                [{"game_id": "001", "game_time_utc": datetime(2026, 3, 15, 23, 0, 0, tzinfo=timezone.utc)}],
                [],
            ),
        ),
        patch("ingestion.scheduler._snapshot_phase_already_captured", return_value=False),
        patch("ingestion.scheduler.sync_prop_snapshot_phase") as sync_mock,
    ):
        run_prop_snapshot_schedule_cycle(datetime(2026, 3, 15, 20, 0, 0))

    sync_mock.assert_called_once_with("early")


def test_run_scheduled_official_injury_report_cycle_invokes_sync_with_due_slot() -> None:
    with (
        patch(
            "ingestion.scheduler.get_todays_games_bundle",
            return_value=(
                [{"game_id": "001", "game_time_utc": datetime(2026, 3, 16, 2, 30, 0, tzinfo=timezone.utc)}],
                [],
            ),
        ),
        patch("ingestion.scheduler.sync_scheduled_official_injury_report") as sync_mock,
    ):
        run_scheduled_official_injury_report_cycle(datetime(2026, 3, 15, 21, 17, 0))

    sync_mock.assert_called_once_with(date(2026, 3, 15), time(21, 15))


def test_run_scheduled_official_injury_report_cycle_skips_outside_active_window() -> None:
    with (
        patch(
            "ingestion.scheduler.get_todays_games_bundle",
            return_value=(
                [{"game_id": "001", "game_time_utc": datetime(2026, 3, 15, 23, 30, 0, tzinfo=timezone.utc)}],
                [],
            ),
        ),
        patch("ingestion.scheduler.sync_scheduled_official_injury_report") as sync_mock,
    ):
        run_scheduled_official_injury_report_cycle(datetime(2026, 3, 15, 12, 45, 0))

    sync_mock.assert_not_called()


def test_run_scheduler_cycle_does_not_poll_pregame_markets_between_scheduled_slots() -> None:
    with (
        patch("ingestion.scheduler.get_current_mode", return_value="pregame"),
        patch("ingestion.scheduler.sync_pregame_markets") as sync_pregame_mock,
        patch("ingestion.scheduler.sync_live_state_and_markets") as sync_live_mock,
        patch("ingestion.scheduler.sync_postgame_enrichment") as sync_postgame_mock,
    ):
        run_scheduler_cycle()

    sync_pregame_mock.assert_not_called()
    sync_live_mock.assert_not_called()
    sync_postgame_mock.assert_not_called()


def test_start_scheduler_registers_official_injury_report_cycle() -> None:
    scheduled_jobs: list[dict[str, object]] = []

    class FakeScheduler:
        def add_job(self, func, trigger, **kwargs):
            scheduled_jobs.append({"func": func, "trigger": trigger, "kwargs": kwargs})

        def start(self) -> None:
            return None

    with (
        patch("ingestion.scheduler.bootstrap_backend"),
        patch("ingestion.scheduler.BackgroundScheduler", return_value=FakeScheduler()),
    ):
        start_scheduler()

    official_job = next(job for job in scheduled_jobs if job["kwargs"].get("id") == "official_injury_report_cycle")
    assert official_job["func"] is run_scheduled_official_injury_report_cycle
    assert official_job["trigger"] == "cron"
    assert official_job["kwargs"]["hour"] == "8-23"
    assert official_job["kwargs"]["minute"] == "0,15,30,45"

    pregame_job = next(job for job in scheduled_jobs if job["kwargs"].get("id") == "scheduled_pregame_markets_cycle")
    assert pregame_job["func"] is run_scheduled_pregame_markets_cycle
    assert pregame_job["trigger"] == "cron"
    assert pregame_job["kwargs"]["hour"] == "11-23"
    assert pregame_job["kwargs"]["minute"] == "0,15,30,45"

    accumulation_job = next(job for job in scheduled_jobs if job["kwargs"].get("id") == "odds_accumulation_cycle")
    assert accumulation_job["func"] is run_odds_accumulation_cycle
    assert accumulation_job["trigger"] == "cron"
    assert accumulation_job["kwargs"]["hour"] == "11-23"
    assert accumulation_job["kwargs"]["minute"] == "0,30"

    repair_job = next(job for job in scheduled_jobs if job["kwargs"].get("id") == "signal_snapshot_repair_cycle")
    assert repair_job["func"] is run_signal_snapshot_repair_cycle
    assert repair_job["trigger"] == "cron"
    assert repair_job["kwargs"]["hour"] == "11-23"
    assert repair_job["kwargs"]["minute"] == "5,20,35,50"
