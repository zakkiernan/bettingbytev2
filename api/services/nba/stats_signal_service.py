from __future__ import annotations

from analytics.nba.signals_data import (
    base_snapshot_query as _base_snapshot_query,
    build_cards_from_snapshots as _build_cards_from_snapshots,
    load_current_snapshots as _load_current_snapshots,
    load_features_by_snapshot as _load_features_by_snapshot,
    load_injury_entries_by_team_date as _load_injury_entries_by_team_date,
    load_latest_injury_reports_by_date as _load_latest_injury_reports_by_date,
    load_latest_odds_snapshot_times as _load_latest_odds_snapshot_times,
    load_latest_signal_audit_metrics as _load_latest_signal_audit_metrics,
    load_recent_logs_by_player as _load_recent_logs_by_player,
    load_signal_audit_archive_summary as _load_signal_audit_archive_summary,
    load_snapshots_for_today as _load_snapshots_for_today,
    utcnow as _utcnow,
)
from analytics.nba.signals_profile import POINTS_STAT_TYPE, build_fallback_signal_profile, build_stats_signal_profile
from analytics.nba.signals_readiness import _build_signal_readiness, build_signal_readiness
from analytics.nba.signals_types import StatsSignalCard, StatsSignalProfile
from api.services.nba.stats_signal_history import (
    get_historical_pregame_lines,
    get_line_movement,
    get_player_signal_history,
)
from api.services.nba.stats_signal_narrative import get_narrative_context
from api.services.nba.stats_signal_queries import (
    build_signal_run_health,
    get_active_prop_rows_for_player,
    get_edges_today_response,
    get_prop_board_response,
    get_prop_counts_by_game,
    get_prop_detail_response,
)
from ingestion.nba.signal_jobs import (
    _serialize_signal_audit_row,
    _serialize_signal_snapshot,
    persist_current_signal_snapshots,
    repair_current_signal_snapshots,
)

__all__ = [
    "POINTS_STAT_TYPE",
    "StatsSignalCard",
    "StatsSignalProfile",
    "_base_snapshot_query",
    "_build_cards_from_snapshots",
    "_build_signal_readiness",
    "_load_current_snapshots",
    "_load_features_by_snapshot",
    "_load_injury_entries_by_team_date",
    "_load_latest_injury_reports_by_date",
    "_load_latest_odds_snapshot_times",
    "_load_latest_signal_audit_metrics",
    "_load_recent_logs_by_player",
    "_load_signal_audit_archive_summary",
    "_load_snapshots_for_today",
    "_serialize_signal_audit_row",
    "_serialize_signal_snapshot",
    "_utcnow",
    "build_fallback_signal_profile",
    "build_signal_readiness",
    "build_signal_run_health",
    "build_stats_signal_profile",
    "get_active_prop_rows_for_player",
    "get_edges_today_response",
    "get_historical_pregame_lines",
    "get_line_movement",
    "get_narrative_context",
    "get_player_signal_history",
    "get_prop_board_response",
    "get_prop_counts_by_game",
    "get_prop_detail_response",
    "persist_current_signal_snapshots",
    "repair_current_signal_snapshots",
]
