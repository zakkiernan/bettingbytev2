from __future__ import annotations

from datetime import datetime

from ingestion.scheduler import _resolve_first_tip_utc, _select_due_snapshot_phase


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
