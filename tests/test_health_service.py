from __future__ import annotations

from datetime import datetime

from api.schemas.health import (
    InjuryReportsHealth,
    LinesHealth,
    PregameContextHealth,
    SignalRunHealth,
)
from api.services.health_service import _build_health_alerts


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
