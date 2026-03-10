from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from database import db as db_module
from database import models
from ingestion import jobs, nba_client, rotation_sync, validation


class FakeResponse:
    def __init__(self, *, status_code: int = 200, text: str = "", headers: dict[str, str] | None = None, url: str = "https://stats.nba.com/stats/gamerotation") -> None:
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.url = url


class FakeSession:
    def __init__(self, responses: list[object]) -> None:
        self._responses = list(responses)

    def get(self, **kwargs):
        if not self._responses:
            raise AssertionError("No fake responses remaining")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _sample_rotation_payload(game_id: str = "002TEST") -> dict[str, object]:
    headers = [
        "GAME_ID",
        "TEAM_ID",
        "TEAM_CITY",
        "TEAM_NAME",
        "PERSON_ID",
        "PLAYER_FIRST",
        "PLAYER_LAST",
        "IN_TIME_REAL",
        "OUT_TIME_REAL",
        "PLAYER_PTS",
        "PT_DIFF",
        "USG_PCT",
    ]
    return {
        "resource": "gamerotation",
        "parameters": {"GameID": game_id, "LeagueID": "00"},
        "resultSets": [
            {
                "name": "AwayTeam",
                "headers": headers,
                "rowSet": [
                    [game_id, "1610612752", "New York", "Knicks", "2", "Away", "Player", 0.0, 720.0, 10, 5, 20.0],
                ],
            },
            {
                "name": "HomeTeam",
                "headers": headers,
                "rowSet": [
                    [game_id, "1610612738", "Boston", "Celtics", "1", "Home", "Player", 0.0, 720.0, 12, 7, 22.0],
                ],
            },
        ],
    }


class GameRotationFetchTests(unittest.TestCase):
    def test_request_game_rotation_payload_classifies_empty_response(self) -> None:
        session = FakeSession([
            FakeResponse(status_code=200, text="   ", headers={"Content-Type": "application/json"}),
        ])
        with patch.object(nba_client.NBAStatsHTTP, "get_session", return_value=session):
            with self.assertRaises(nba_client.RotationFetchError) as ctx:
                nba_client._request_game_rotation_payload("002TEST")

        self.assertEqual(ctx.exception.error_type, "empty_response")
        self.assertEqual(ctx.exception.status_code, 200)

    def test_request_game_rotation_payload_classifies_non_json_response(self) -> None:
        session = FakeSession([
            FakeResponse(status_code=200, text="<html>bad gateway</html>", headers={"Content-Type": "text/html"}),
        ])
        with patch.object(nba_client.NBAStatsHTTP, "get_session", return_value=session):
            with self.assertRaises(nba_client.RotationFetchError) as ctx:
                nba_client._request_game_rotation_payload("002TEST")

        self.assertEqual(ctx.exception.error_type, "non_json_response")
        self.assertIn("text/html", ctx.exception.error_text)
        self.assertIn("html", (ctx.exception.body_prefix or "").lower())

    def test_request_game_rotation_payload_classifies_malformed_json(self) -> None:
        session = FakeSession([
            FakeResponse(status_code=200, text="{", headers={"Content-Type": "application/json"}),
        ])
        with patch.object(nba_client.NBAStatsHTTP, "get_session", return_value=session):
            with self.assertRaises(nba_client.RotationFetchError) as ctx:
                nba_client._request_game_rotation_payload("002TEST")

        self.assertEqual(ctx.exception.error_type, "other_parse_error")
        self.assertIn("malformed JSON", ctx.exception.error_text)

    def test_get_game_rotation_bundle_returns_success_result_for_valid_json(self) -> None:
        session = FakeSession([
            FakeResponse(
                status_code=200,
                text=json.dumps(_sample_rotation_payload()),
                headers={"Content-Type": "application/json"},
            ),
        ])
        with patch.object(nba_client.NBAStatsHTTP, "get_session", return_value=session), patch("ingestion.nba_client.time.sleep"):
            result = nba_client.get_game_rotation_bundle("002TEST")

        self.assertIsNone(result.error_type)
        self.assertEqual(len(result.payloads), 1)
        self.assertEqual(len(result.team_rotation_games), 2)
        self.assertEqual(len(result.player_rotation_games), 2)
        self.assertEqual(len(result.rotations), 2)

    def test_get_game_rotation_bundle_retries_transient_rotation_failure(self) -> None:
        expected = nba_client.GameRotationBundleResult(
            rotations=[{"game_id": "002TEST"}],
            team_rotation_games=[{"game_id": "002TEST", "team_id": "1610612738"}],
            player_rotation_games=[{"game_id": "002TEST", "player_id": "1", "player_name": "Test Player"}],
            payloads=[{"source": "nba", "payload_type": "game_rotation", "payload": {}}],
        )

        with patch.object(nba_client, "NBA_GAME_ROTATION_PASSES", 2), patch(
            "ingestion.nba_client._fetch_game_rotation_bundle_once",
            side_effect=[nba_client.RotationFetchError("empty_response", "GameRotation returned an empty response body."), expected],
        ) as fetch_mock, patch("ingestion.nba_client.time.sleep"), patch("ingestion.nba_client.logger.warning"), patch("ingestion.nba_client.logger.exception"):
            result = nba_client.get_game_rotation_bundle("002TEST")

        self.assertEqual(fetch_mock.call_count, 2)
        self.assertEqual(result.player_rotation_games, expected.player_rotation_games)
        self.assertIsNone(result.error_type)


class DatabaseBackedTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.session_local = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            class_=Session,
        )
        self.original_engine = db_module.engine
        self.original_session_local = db_module.SessionLocal
        db_module.engine = self.engine
        db_module.SessionLocal = self.session_local
        models.Base.metadata.create_all(self.engine)
        self._seed_teams()

    def tearDown(self) -> None:
        db_module.SessionLocal = self.original_session_local
        db_module.engine = self.original_engine
        self.engine.dispose()

    def _seed_teams(self) -> None:
        with db_module.session_scope() as session:
            session.add_all(
                [
                    models.Team(team_id="1610612738", abbreviation="BOS", full_name="Boston Celtics", is_active=True),
                    models.Team(team_id="1610612752", abbreviation="NYK", full_name="New York Knicks", is_active=True),
                    models.Team(team_id="1610612747", abbreviation="LAL", full_name="Los Angeles Lakers", is_active=True),
                    models.Team(team_id="1610612743", abbreviation="DEN", full_name="Denver Nuggets", is_active=True),
                ]
            )

    def add_historical_game(self, game_id: str, game_date: datetime, home_team: str, away_team: str, player_total: int) -> None:
        with db_module.session_scope() as session:
            for index in range(player_total):
                is_home = index % 2 == 0
                team = home_team if is_home else away_team
                opponent = away_team if is_home else home_team
                session.add(
                    models.HistoricalGameLog(
                        game_id=game_id,
                        game_date=game_date,
                        player_id=f"{game_id}_{index}",
                        player_name=f"Player {game_id}_{index}",
                        team=team,
                        opponent=opponent,
                        is_home=is_home,
                    )
                )

    def add_rotation_row(self, game_id: str, team_id: str = "1610612738", player_id: str = "seed-player") -> None:
        with db_module.session_scope() as session:
            session.add(
                models.PlayerRotationGame(
                    game_id=game_id,
                    team_id=team_id,
                    team_abbreviation="BOS",
                    team_name="Boston Celtics",
                    player_id=player_id,
                    player_name="Seed Player",
                )
            )

    def add_rotation_failure_item(self, game_id: str, created_at: datetime, error_text: str) -> None:
        with db_module.session_scope() as session:
            run = models.IngestionRun(
                job_name="test_rotation",
                status="failed",
                started_at=created_at,
                finished_at=created_at,
            )
            session.add(run)
            session.flush()
            session.add(
                models.IngestionRunItem(
                    run_id=run.id,
                    entity_type="game",
                    entity_key=game_id,
                    stage="game_rotation",
                    status="failed",
                    error_text=error_text,
                    created_at=created_at,
                )
            )


class RotationSyncQueueTests(DatabaseBackedTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.add_historical_game("0022500001", datetime(2025, 10, 25, 19, 30), "BOS", "NYK", 2)
        self.add_historical_game("0022500002", datetime(2025, 10, 26, 19, 30), "BOS", "NYK", 2)
        self.add_historical_game("0022500003", datetime(2025, 10, 27, 19, 30), "BOS", "NYK", 4)
        self.add_historical_game("0022500004", datetime(2025, 10, 28, 19, 30), "BOS", "NYK", 2)
        self.add_historical_game("0022500005", datetime(2025, 10, 29, 19, 30), "BOS", "NYK", 2)
        self.add_historical_game("0022500006", datetime(2025, 10, 30, 19, 30), "BOS", "NYK", 2)
        self.add_historical_game("0022500007", datetime(2025, 10, 31, 19, 30), "BOS", "NYK", 5)
        self.add_historical_game("0022500008", datetime(2025, 11, 1, 19, 30), "BOS", "NYK", 3)
        self.add_historical_game("0022500009", datetime(2025, 11, 2, 19, 30), "BOS", "NYK", 2)
        self.add_historical_game("0022400001", datetime(2024, 11, 1, 20, 0), "LAL", "DEN", 2)

        self.add_rotation_row("0022500001")
        old_failure_time = datetime.utcnow() - timedelta(hours=2)
        self.add_rotation_failure_item("0022500002", old_failure_time, "GameRotation returned malformed JSON: JSONDecodeError: Expecting value")
        self.add_rotation_failure_item("0022500005", old_failure_time - timedelta(minutes=5), "GameRotation returned an empty response body.")
        self.add_rotation_failure_item("0022500006", old_failure_time - timedelta(minutes=10), "GameRotation timed out: TimeoutError")
        for offset in range(5):
            self.add_rotation_failure_item(
                "0022500004",
                old_failure_time - timedelta(minutes=offset + 20),
                "GameRotation returned malformed JSON: JSONDecodeError: Expecting value",
            )
        self.add_rotation_failure_item("0022500009", datetime.utcnow(), "GameRotation returned an empty response body.")

    def test_seed_rotation_sync_states_bootstraps_success_retry_pending_and_quarantine(self) -> None:
        metrics = rotation_sync.seed_rotation_sync_states("2025-26")

        self.assertEqual(metrics["seeded_games"], 9)
        with db_module.session_scope() as session:
            success_state = session.get(models.RotationSyncState, "0022500001")
            retry_state = session.get(models.RotationSyncState, "0022500002")
            pending_state = session.get(models.RotationSyncState, "0022500003")
            quarantined_state = session.get(models.RotationSyncState, "0022500004")
            prior_season_state = session.get(models.RotationSyncState, "0022400001")

            self.assertEqual(success_state.status, rotation_sync.ROTATION_SYNC_STATUS_SUCCESS)
            self.assertEqual(retry_state.status, rotation_sync.ROTATION_SYNC_STATUS_RETRY)
            self.assertEqual(retry_state.last_error_type, "other_parse_error")
            self.assertIsNotNone(retry_state.next_retry_at)
            self.assertEqual(pending_state.status, rotation_sync.ROTATION_SYNC_STATUS_PENDING)
            self.assertEqual(quarantined_state.status, rotation_sync.ROTATION_SYNC_STATUS_QUARANTINED)
            self.assertIsNone(prior_season_state)

    def test_select_rotation_sync_batch_caps_retry_games_and_fills_with_pending(self) -> None:
        rotation_sync.seed_rotation_sync_states("2025-26")

        selection = rotation_sync.select_rotation_sync_batch(season="2025-26", batch_size=5)

        self.assertEqual(selection["retry_games_selected"], 2)
        self.assertEqual(selection["pending_games_selected"], 3)
        self.assertEqual(selection["selected_game_ids"][:2], ["0022500006", "0022500005"])
        self.assertEqual(selection["selected_game_ids"][2:], ["0022500007", "0022500003", "0022500008"])
        self.assertEqual(selection["quarantined_games"], 1)

    def test_specific_game_ids_respect_cooldown_unless_forced(self) -> None:
        rotation_sync.seed_rotation_sync_states("2025-26")

        without_force = rotation_sync.select_rotation_sync_batch(
            season="2025-26",
            batch_size=5,
            specific_game_ids=["0022500009"],
            force_retry=False,
        )
        with_force = rotation_sync.select_rotation_sync_batch(
            season="2025-26",
            batch_size=5,
            specific_game_ids=["0022500009"],
            force_retry=True,
        )

        self.assertEqual(without_force["selected_game_ids"], [])
        self.assertEqual(without_force["skipped_cooldown_games"], 1)
        self.assertEqual(with_force["selected_game_ids"], ["0022500009"])
        self.assertEqual(with_force["retry_games_selected"], 1)

    def test_validation_helpers_honor_season(self) -> None:
        all_postgame = {row["game_id"] for row in validation.get_postgame_enrichment_backlog()}
        current_postgame = {row["game_id"] for row in validation.get_postgame_enrichment_backlog(season="2025-26")}
        all_rotation = {row["game_id"] for row in validation.get_rotation_backlog()}
        current_rotation = {row["game_id"] for row in validation.get_rotation_backlog(season="2025-26")}
        current_missing_games = validation.get_missing_canonical_games_from_history(season="2025-26")

        self.assertIn("0022400001", all_postgame)
        self.assertNotIn("0022400001", current_postgame)
        self.assertIn("0022400001", all_rotation)
        self.assertNotIn("0022400001", current_rotation)
        self.assertEqual({row["game_id"] for row in current_missing_games}, {f"002250000{i}" for i in range(1, 10)})
        self.assertEqual({row["season"] for row in current_missing_games}, {"2025-26"})

    def test_summarize_ingestion_health_includes_rotation_queue_metrics(self) -> None:
        rotation_sync.seed_rotation_sync_states("2025-26")

        health = validation.summarize_ingestion_health()

        self.assertEqual(health["rotation_queue_pending"], 3)
        self.assertEqual(health["rotation_queue_retry"], 4)
        self.assertEqual(health["rotation_queue_quarantined"], 1)
        self.assertGreaterEqual(health["rotation_queue_due_now"], 3)
        self.assertIn("other_parse_error", health["rotation_recent_failure_counts"])

    def test_rotation_queue_diagnostics_returns_retry_and_quarantine_rows(self) -> None:
        rotation_sync.seed_rotation_sync_states("2025-26")

        rows = validation.get_rotation_queue_diagnostics(
            season="2025-26",
            statuses=[rotation_sync.ROTATION_SYNC_STATUS_RETRY, rotation_sync.ROTATION_SYNC_STATUS_QUARANTINED],
            limit=10,
        )

        self.assertEqual({row["game_id"] for row in rows}, {"0022500002", "0022500004", "0022500005", "0022500006", "0022500009"})


class SyncGameRotationTests(unittest.TestCase):
    def test_sync_game_rotation_records_underlying_error_text_and_details(self) -> None:
        failed_result = nba_client.GameRotationBundleResult(
            error_type="other_parse_error",
            error_text="GameRotation returned malformed JSON: JSONDecodeError: Expecting value",
            error_details={"status_code": 200, "content_type": "application/json", "body_prefix": "{"},
        )

        with patch("ingestion.jobs.get_game_rotation_bundle", return_value=failed_result), patch("ingestion.jobs.write_source_payloads"), patch("ingestion.jobs.create_ingestion_run_item") as run_item_mock:
            result = jobs._sync_game_rotation_for_game("0022500127", run_id=17)

        self.assertEqual(result["error_type"], "other_parse_error")
        self.assertIn("malformed JSON", result["error_text"])
        self.assertEqual(result["error_details"]["status_code"], 200)
        self.assertEqual(run_item_mock.call_args.kwargs["metrics"]["error_type"], "other_parse_error")
        self.assertEqual(run_item_mock.call_args.kwargs["metrics"]["status_code"], 200)


class PostgameDecouplingTests(unittest.TestCase):
    def test_postgame_enrichment_enqueues_rotation_without_inline_fetch(self) -> None:
        advanced_rows = [
            {
                "game_id": "0022500999",
                "player_id": "1",
                "player_name": "Test Player",
                "usage_percentage": 25.0,
            }
        ]
        backlog = [{"game_id": "0022500999", "historical_players": 1, "advanced_players": 0, "missing_players": 1}]

        with patch("ingestion.jobs.get_postgame_enrichment_backlog", return_value=backlog), patch(
            "ingestion.jobs.get_boxscore_summary_bundle", return_value=({}, [])
        ), patch("ingestion.jobs.get_advanced_boxscore_bundle", return_value=(advanced_rows, [])), patch(
            "ingestion.jobs.get_player_tracking_bundle", return_value=([], [])
        ), patch("ingestion.jobs.normalize_game_summary", return_value=None), patch(
            "ingestion.jobs.write_source_payloads"
        ), patch("ingestion.jobs.write_games"), patch("ingestion.jobs.write_players"), patch(
            "ingestion.jobs.write_advanced_logs"
        ), patch("ingestion.jobs.create_ingestion_run_item") as run_item_mock, patch(
            "ingestion.jobs.enqueue_rotation_games", return_value=1
        ) as enqueue_mock, patch(
            "ingestion.jobs._reconcile_canonical_games_from_history_impl", return_value={"reconciled_games": 0}
        ), patch("ingestion.jobs._sync_game_rotation_for_game", side_effect=AssertionError("rotation fetch should not run inline")):
            result = jobs._backfill_postgame_enrichment_impl(season="2025-26", batch_size=1, max_batches=1, run_id=11)

        self.assertEqual(result["rotation_queue_games_enqueued"], 1)
        enqueue_mock.assert_called_once_with(["0022500999"], season="2025-26")
        self.assertEqual(run_item_mock.call_args.kwargs["metrics"]["rotation_queue_games_enqueued"], 1)


if __name__ == "__main__":
    unittest.main()
