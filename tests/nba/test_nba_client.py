from __future__ import annotations

from unittest.mock import patch

from ingestion.nba_client import get_live_scoreboard_bundle


def test_live_scoreboard_bundle_returns_structured_failure_payload() -> None:
    with patch("ingestion.nba_client.live_scoreboard.ScoreBoard", side_effect=RuntimeError("boom")):
        games, payloads = get_live_scoreboard_bundle()

    assert games == []
    assert len(payloads) == 1
    assert payloads[0]["payload"]["status"] == "error"
    assert payloads[0]["payload"]["endpoint"] == "live_scoreboard"
    assert payloads[0]["payload"]["error_type"] == "RuntimeError"
    assert payloads[0]["payload"]["error_message"] == "RuntimeError: boom"
