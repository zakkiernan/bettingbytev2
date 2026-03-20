from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from api.schemas.health import (
    InjuryReportsHealth,
    LinesHealth,
    PregameContextHealth,
    SignalRunHealth,
)
from api.services.health_service import _build_health_alerts, get_injury_matching_coverage, get_odds_snapshot_coverage


def test_build_health_alerts_flags_stale_injury_and_missing_audit() -> None:
    alerts = _build_health_alerts(
        now=datetime(2026, 3, 16, 18, 0, 0),
        today_game_ids=["G1"],
        lines=LinesHealth(tonight_game_count=1, tonight_prop_count=12, stale_captures=0),
        injury_reports=InjuryReportsHealth(latest_report_date="2026-03-15"),
        pregame_context=PregameContextHealth(tonight_games_with_context=1, tonight_games_missing_context=0),
        signal_run=SignalRunHealth(
            signals_generated=12,
            latest_persisted_at=None,
        ),
    )

    codes = {alert.code for alert in alerts}

    assert "injury_reports_stale" in codes
    assert "signal_audit_missing" in codes


def test_build_health_alerts_warns_on_signal_audit_lag_and_fallback_usage() -> None:
    alerts = _build_health_alerts(
        now=datetime(2026, 3, 16, 18, 0, 0),
        today_game_ids=["G1"],
        lines=LinesHealth(tonight_game_count=1, tonight_prop_count=12, stale_captures=0),
        injury_reports=InjuryReportsHealth(latest_report_date="2026-03-16"),
        pregame_context=PregameContextHealth(tonight_games_with_context=1, tonight_games_missing_context=0),
        signal_run=SignalRunHealth(
            signals_generated=12,
            signals_blocked=2,
            signals_using_fallback=3,
            latest_persisted_at=datetime(2026, 3, 16, 17, 45, 0),
            latest_audit_source_prop_captured_at=datetime(2026, 3, 16, 17, 35, 0),
            audit_lag_minutes=25,
        ),
    )

    codes = {alert.code for alert in alerts}

    assert "signal_audit_lag" in codes
    assert "signals_partially_blocked" in codes
    assert "signals_using_fallback" in codes


def test_build_health_alerts_escalates_when_all_signals_are_blocked() -> None:
    alerts = _build_health_alerts(
        now=datetime(2026, 3, 16, 18, 0, 0),
        today_game_ids=["G1"],
        lines=LinesHealth(tonight_game_count=1, tonight_prop_count=8, stale_captures=8),
        injury_reports=InjuryReportsHealth(latest_report_date="2026-03-16"),
        pregame_context=PregameContextHealth(tonight_games_with_context=0, tonight_games_missing_context=1),
        signal_run=SignalRunHealth(
            signals_generated=8,
            signals_blocked=8,
            latest_persisted_at=datetime(2026, 3, 16, 17, 30, 0),
            latest_audit_source_prop_captured_at=datetime(2026, 3, 16, 17, 30, 0),
            audit_lag_minutes=0,
        ),
    )

    severities_by_code = {alert.code: alert.severity for alert in alerts}

    assert severities_by_code["lines_stale"] == "critical"
    assert severities_by_code["pregame_context_missing"] == "critical"
    assert severities_by_code["signals_all_blocked"] == "critical"


def test_get_odds_snapshot_coverage_summarizes_archive_density() -> None:
    db = MagicMock()
    db.execute.side_effect = [
        SimpleNamespace(scalar=lambda: 120),
        SimpleNamespace(all=lambda: [("accumulation", 30), ("pregame", 40), ("tip", 10)]),
        SimpleNamespace(one=lambda: (datetime(2026, 3, 1, 12, 0, 0), datetime(2026, 3, 16, 18, 0, 0))),
        SimpleNamespace(scalar=lambda: 14),
        SimpleNamespace(scalar=lambda: 8),
    ]

    coverage = get_odds_snapshot_coverage(db)

    assert coverage["total_odds_snapshots"] == 120
    assert coverage["odds_snapshot_rows_by_phase"]["pregame"] == 40
    assert coverage["games_with_multi_pregame_snapshots"] == 14
    assert coverage["average_odds_snapshots_per_game"] == 15.0
    assert coverage["odds_snapshot_start_date"] == datetime(2026, 3, 1, 12, 0, 0)
    assert coverage["odds_snapshot_end_date"] == datetime(2026, 3, 16, 18, 0, 0)


def test_get_injury_matching_coverage_summarizes_named_and_overall_rows() -> None:
    db = MagicMock()
    db.execute.side_effect = [
        SimpleNamespace(scalar=lambda: 100),
        SimpleNamespace(scalar=lambda: 92),
        SimpleNamespace(scalar=lambda: 80),
        SimpleNamespace(scalar=lambda: 78),
        SimpleNamespace(all=lambda: [("POR", 6), ("ATL", 2)]),
        SimpleNamespace(all=lambda: [("POR", 2)]),
        SimpleNamespace(scalar=lambda: date(2026, 3, 12)),
    ]

    coverage = get_injury_matching_coverage(db)

    assert coverage["entries_stored"] == 100
    assert coverage["entries_with_player_id"] == 92
    assert coverage["entries_without_player_id"] == 8
    assert coverage["entry_match_pct"] == 0.92
    assert coverage["named_entries_stored"] == 80
    assert coverage["named_entries_with_player_id"] == 78
    assert coverage["named_entries_without_player_id"] == 2
    assert coverage["named_entry_match_pct"] == 0.975
    assert coverage["entries_without_player_id_by_team"]["POR"] == 6
    assert coverage["named_entries_without_player_id_by_team"]["POR"] == 2
    assert coverage["most_recent_match_stats_report_date"] == "2026-03-12"
