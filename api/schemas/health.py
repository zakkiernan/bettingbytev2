from __future__ import annotations

from datetime import datetime

from api.schemas.base import APIModel


class LinesHealth(APIModel):
    tonight_game_count: int = 0
    tonight_prop_count: int = 0
    stale_captures: int = 0
    oldest_capture_age_minutes: int | None = None
    sportsbook: str = "fanduel"


class RotationsHealth(APIModel):
    coverage_pct: float = 0.0
    pending: int = 0
    retry: int = 0
    quarantined: int = 0


class InjuryReportsHealth(APIModel):
    latest_report_date: str | None = None
    reports_stored: int = 0
    entries_stored: int = 0


class PregameContextHealth(APIModel):
    tonight_games_with_context: int = 0
    tonight_games_missing_context: int = 0


class SignalRunHealth(APIModel):
    last_run_at: datetime | None = None
    signals_generated: int = 0
    signals_with_recommendation: int = 0
    signals_ready: int = 0
    signals_limited: int = 0
    signals_blocked: int = 0
    signals_using_fallback: int = 0
    signals_missing_source_game: int = 0


class IngestionHealthResponse(APIModel):
    health_captured_at: datetime
    lines: LinesHealth
    rotations: RotationsHealth
    injury_reports: InjuryReportsHealth
    pregame_context: PregameContextHealth
    signal_run: SignalRunHealth
