from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from api.schemas.base import APIModel


class LinesHealth(APIModel):
    tonight_game_count: int = 0
    tonight_prop_count: int = 0
    stale_captures: int = 0
    oldest_capture_age_minutes: int | None = None
    sportsbook: str = "fanduel"
    total_odds_snapshots: int = 0
    odds_snapshot_rows_by_phase: dict[str, int] = Field(default_factory=dict)
    odds_snapshot_start_date: datetime | None = None
    odds_snapshot_end_date: datetime | None = None
    games_with_multi_pregame_snapshots: int = 0
    average_odds_snapshots_per_game: float = 0.0


class RotationsHealth(APIModel):
    coverage_pct: float = 0.0
    pending: int = 0
    retry: int = 0
    quarantined: int = 0


class InjuryReportsHealth(APIModel):
    latest_report_date: str | None = None
    reports_stored: int = 0
    entries_stored: int = 0
    entries_with_player_id: int = 0
    entries_without_player_id: int = 0
    entry_match_pct: float = 0.0
    named_entries_stored: int = 0
    named_entries_with_player_id: int = 0
    named_entries_without_player_id: int = 0
    named_entry_match_pct: float = 0.0
    entries_without_player_id_by_team: dict[str, int] = Field(default_factory=dict)
    named_entries_without_player_id_by_team: dict[str, int] = Field(default_factory=dict)
    most_recent_match_stats_report_date: str | None = None


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
    signals_by_stat_type: dict[str, int] = Field(default_factory=dict)
    blocked_by_stat_type: dict[str, int] = Field(default_factory=dict)
    blocked_reasons: dict[str, int] = Field(default_factory=dict)
    latest_persisted_at: datetime | None = None
    latest_audit_source_prop_captured_at: datetime | None = None
    audit_lag_minutes: int | None = None
    signals_missing_source_game: int = 0
    total_audit_rows: int = 0
    audit_rows_by_snapshot_phase: dict[str, int] = Field(default_factory=dict)
    games_with_full_audit_coverage: int = 0
    most_recent_audit_capture_at: datetime | None = None


class HealthAlert(APIModel):
    code: str
    severity: Literal["info", "warning", "critical"]
    message: str


class IngestionHealthResponse(APIModel):
    health_captured_at: datetime
    lines: LinesHealth
    rotations: RotationsHealth
    injury_reports: InjuryReportsHealth
    pregame_context: PregameContextHealth
    signal_run: SignalRunHealth
    alerts: list[HealthAlert] = Field(default_factory=list)


class SystemHealthResponse(APIModel):
    status: Literal["ok", "degraded"]
    db: Literal["connected", "disconnected"]
    version: str
