from __future__ import annotations

from datetime import date, time
from types import SimpleNamespace
from unittest.mock import patch

import requests

from ingestion.jobs import _sync_pregame_markets_impl, _sync_scheduled_official_injury_report_impl


def _build_http_error(status_code: int) -> requests.HTTPError:
    error = requests.HTTPError(f"{status_code} error")
    error.response = SimpleNamespace(status_code=status_code)
    return error


def test_sync_scheduled_official_injury_report_treats_403_as_not_available() -> None:
    with patch(
        "ingestion.jobs.sync_official_injury_report_impl",
        side_effect=_build_http_error(403),
    ):
        result = _sync_scheduled_official_injury_report_impl(date(2026, 3, 15), time(21, 30))

    assert result["status"] == "not_available"
    assert result["report_date"] == "2026-03-15"
    assert result["report_time_et"] == "21:30"


def test_sync_scheduled_official_injury_report_treats_404_as_not_available() -> None:
    with patch(
        "ingestion.jobs.sync_official_injury_report_impl",
        side_effect=_build_http_error(404),
    ):
        result = _sync_scheduled_official_injury_report_impl(date(2026, 3, 15), time(21, 45))

    assert result["status"] == "not_available"
    assert result["report_date"] == "2026-03-15"
    assert result["report_time_et"] == "21:45"


def test_sync_pregame_markets_persists_stats_signal_snapshots() -> None:
    board = {
        "props": [
            {
                "game_id": "G1",
                "player_id": "123",
                "player_name": "Test Player",
                "team": "BOS",
                "opponent": "NYK",
                "stat_type": "points",
                "line": 24.5,
                "over_odds": -110,
                "under_odds": -110,
                "captured_at": "2026-03-16T18:00:00",
            }
        ],
        "event_mappings": [{"event_id": "EV1", "nba_game_id": "G1"}],
        "payloads": [],
        "captured_at": "2026-03-16T18:00:00",
    }
    pregame_context_result = SimpleNamespace(
        payload={"games": [{"game_id": "G1"}]},
        feature_rows=[{"game_id": "G1", "player_id": "123"}],
        attachment_metrics={
            "attached_count": 1,
            "attached_pct": 100.0,
            "overlap_game_count": 1,
            "missing_context_game_ids": [],
            "projected_unavailable_count": 0,
            "high_late_scratch_risk_count": 0,
        },
    )

    with patch("ingestion.jobs._sync_reference_entities_impl"), patch(
        "ingestion.jobs.fetch_current_prop_board", return_value=board
    ), patch(
        "ingestion.jobs.get_todays_games_bundle", return_value=([], [])
    ), patch(
        "ingestion.jobs.write_source_payloads"
    ), patch(
        "ingestion.jobs.write_games"
    ), patch(
        "ingestion.jobs.write_players"
    ), patch(
        "ingestion.jobs.write_sportsbook_event_mappings"
    ), patch(
        "ingestion.jobs.write_prop_snapshot"
    ), patch(
        "ingestion.jobs.write_odds_snapshot"
    ), patch(
        "ingestion.jobs.sync_current_pregame_context", return_value=pregame_context_result
    ), patch(
        "ingestion.jobs.build_pregame_context_source_payloads", return_value=[]
    ), patch(
        "ingestion.jobs.persist_current_signal_snapshots",
        return_value={"signal_snapshots": 1, "signal_games": 1, "signal_recommendations": 1, "signal_blocked": 0},
    ) as persist_mock, patch(
        "ingestion.jobs.create_ingestion_run_item"
    ) as run_item_mock:
        result = _sync_pregame_markets_impl(run_id=41)

    persist_mock.assert_called_once_with()
    assert result["signal_snapshots"] == 1
    assert result["signal_recommendations"] == 1
    assert run_item_mock.call_args.kwargs["stage"] == "stats_signal_snapshot"
