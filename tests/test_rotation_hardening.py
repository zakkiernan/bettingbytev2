from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from database import db as db_module
from database import models
from ingestion import jobs, rotation_provider, rotation_sync, validation


class RotationScraperFetchTests(unittest.TestCase):
    def test_fetch_rotation_page_payload_classifies_source_missing_game(self) -> None:
        response = Mock()
        response.status_code = 200
        response.url = "https://nbarotations.info/game/002TEST"
        response.text = "<html><body><div>Page Not Found</div></body></html>"
        response.raise_for_status.return_value = None

        with patch("ingestion.rotation_provider.requests.get", return_value=response):
            with self.assertRaises(rotation_provider.RotationFetchError) as ctx:
                rotation_provider._fetch_rotation_page_payload("002TEST")

        self.assertEqual(ctx.exception.error_type, "source_missing_game")
        self.assertIn("missing game", ctx.exception.error_text)


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

    def add_rotation_success_item(self, game_id: str, created_at: datetime, metrics: dict[str, object]) -> None:
        with db_module.session_scope() as session:
            run = models.IngestionRun(
                job_name="test_rotation",
                status="success",
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
                    status="success",
                    metrics_json=json.dumps(metrics),
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

    def test_select_rotation_sync_batch_can_revisit_partial_success_for_backfill(self) -> None:
        rotation_sync.seed_rotation_sync_states("2025-26")

        selection = rotation_sync.select_rotation_sync_batch(
            season="2025-26",
            batch_size=6,
            include_partial_success=True,
        )

        self.assertEqual(selection["retry_games_selected"], 2)
        self.assertEqual(selection["pending_games_selected"], 3)
        self.assertEqual(selection["partial_success_games_selected"], 1)
        self.assertEqual(selection["selected_game_ids"][-1], "0022500001")

    def test_select_rotation_sync_batch_skips_covered_success_when_metrics_show_zero_window_player(self) -> None:
        self.add_rotation_success_item(
            "0022500001",
            datetime.utcnow(),
            {
                "expected_player_count": 2,
                "mapped_player_count": 1,
                "covered_player_count": 2,
                "zero_window_player_count": 1,
            },
        )
        rotation_sync.seed_rotation_sync_states("2025-26")

        selection = rotation_sync.select_rotation_sync_batch(
            season="2025-26",
            batch_size=6,
            include_partial_success=True,
        )

        self.assertEqual(selection["partial_success_games_selected"], 0)
        self.assertNotIn("0022500001", selection["selected_game_ids"])

    def test_source_missing_game_quarantines_immediately(self) -> None:
        rotation_sync.record_rotation_sync_attempt(
            "0022500003",
            "2025-26",
            successful=False,
            error_type="source_missing_game",
            error_text="Rotation source is missing game 0022500003.",
        )

        with db_module.session_scope() as session:
            state = session.get(models.RotationSyncState, "0022500003")
            self.assertEqual(state.status, rotation_sync.ROTATION_SYNC_STATUS_QUARANTINED)
            self.assertEqual(state.last_error_type, "source_missing_game")
            self.assertIsNone(state.next_retry_at)

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

    def test_rotation_backlog_uses_success_coverage_metrics(self) -> None:
        self.add_rotation_success_item(
            "0022500001",
            datetime.utcnow(),
            {
                "expected_player_count": 2,
                "mapped_player_count": 1,
                "covered_player_count": 2,
                "zero_window_player_count": 1,
            },
        )

        backlog = validation.get_rotation_backlog(season="2025-26")

        self.assertNotIn("0022500001", {row["game_id"] for row in backlog})

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



class RotationScraperNormalizationTests(DatabaseBackedTestCase):
    def test_normalize_scraped_game_builds_rotation_rows(self) -> None:
        with db_module.session_scope() as session:
            session.add(
                models.Game(
                    game_id="0022500998",
                    season="2025-26",
                    game_date=datetime(2025, 11, 3, 19, 30),
                    home_team_id="1610612738",
                    away_team_id="1610612752",
                    home_team_abbreviation="BOS",
                    away_team_abbreviation="NYK",
                )
            )
            session.add_all(
                [
                    models.HistoricalGameLog(
                        game_id="0022500998",
                        game_date=datetime(2025, 11, 3, 19, 30),
                        player_id="201",
                        player_name="Away Player",
                        team="NYK",
                        opponent="BOS",
                        is_home=False,
                    ),
                    models.HistoricalGameLog(
                        game_id="0022500998",
                        game_date=datetime(2025, 11, 3, 19, 30),
                        player_id="101",
                        player_name="Home Player",
                        team="BOS",
                        opponent="NYK",
                        is_home=True,
                    ),
                ]
            )

        payload = {
            "game_id": "0022500998",
            "url": "https://nbarotations.info/game/0022500998",
            "title": "New York Knicks 101 @ Boston Celtics 108",
            "raw_sections": {
                "away": [{"name": "Away Player", "histogram": [1, 1, 0, 0]}],
                "home": [{"name": "Home Player", "histogram": [0, 1, 1, 1]}],
            },
        }

        result = rotation_provider._normalize_scraped_game("0022500998", payload)

        self.assertIsNone(result.error_type)
        self.assertEqual(len(result.team_rotation_games), 2)
        self.assertEqual(len(result.player_rotation_games), 2)
        self.assertEqual(len(result.rotations), 2)
        away_summary = next(row for row in result.player_rotation_games if row["player_id"] == "201")
        home_summary = next(row for row in result.player_rotation_games if row["player_id"] == "101")
        self.assertTrue(away_summary["started"])
        self.assertFalse(home_summary["started"])
        self.assertEqual(away_summary["total_shift_duration_real"], 1200.0)
        self.assertEqual(home_summary["total_shift_duration_real"], 1800.0)

    def test_normalize_scraped_game_tolerates_missing_low_minute_box_score_players(self) -> None:
        with db_module.session_scope() as session:
            session.add(
                models.Game(
                    game_id="0022500996",
                    season="2025-26",
                    game_date=datetime(2025, 11, 5, 19, 30),
                    home_team_id="1610612738",
                    away_team_id="1610612752",
                    home_team_abbreviation="BOS",
                    away_team_abbreviation="NYK",
                )
            )
            session.add_all(
                [
                    models.HistoricalGameLog(
                        game_id="0022500996",
                        game_date=datetime(2025, 11, 5, 19, 30),
                        player_id="201",
                        player_name="Away Starter",
                        team="NYK",
                        opponent="BOS",
                        is_home=False,
                        minutes=28,
                    ),
                    models.HistoricalGameLog(
                        game_id="0022500996",
                        game_date=datetime(2025, 11, 5, 19, 30),
                        player_id="202",
                        player_name="Away Fringe",
                        team="NYK",
                        opponent="BOS",
                        is_home=False,
                        minutes=2,
                    ),
                    models.HistoricalGameLog(
                        game_id="0022500996",
                        game_date=datetime(2025, 11, 5, 19, 30),
                        player_id="101",
                        player_name="Home Starter",
                        team="BOS",
                        opponent="NYK",
                        is_home=True,
                        minutes=31,
                    ),
                    models.HistoricalGameLog(
                        game_id="0022500996",
                        game_date=datetime(2025, 11, 5, 19, 30),
                        player_id="102",
                        player_name="Home Fringe",
                        team="BOS",
                        opponent="NYK",
                        is_home=True,
                        minutes=1,
                    ),
                ]
            )

        payload = {
            "game_id": "0022500996",
            "url": "https://nbarotations.info/game/0022500996",
            "title": "New York Knicks 101 @ Boston Celtics 108",
            "raw_sections": {
                "away": [{"name": "Away Starter", "histogram": [1, 1, 0, 0]}],
                "home": [{"name": "Home Starter", "histogram": [0, 1, 1, 1]}],
            },
        }

        result = rotation_provider._normalize_scraped_game("0022500996", payload)

        self.assertIsNone(result.error_type)
        self.assertEqual(len(result.player_rotation_games), 2)
        self.assertEqual({row["player_id"] for row in result.player_rotation_games}, {"101", "201"})

    def test_normalize_scraped_game_accepts_additional_low_minute_scraper_players(self) -> None:
        with db_module.session_scope() as session:
            session.add(
                models.Game(
                    game_id="0022500995",
                    season="2025-26",
                    game_date=datetime(2025, 11, 6, 19, 30),
                    home_team_id="1610612738",
                    away_team_id="1610612752",
                    home_team_abbreviation="BOS",
                    away_team_abbreviation="NYK",
                )
            )
            session.add_all(
                [
                    models.HistoricalGameLog(
                        game_id="0022500995",
                        game_date=datetime(2025, 11, 6, 19, 30),
                        player_id="201",
                        player_name="Away Starter",
                        team="NYK",
                        opponent="BOS",
                        is_home=False,
                        minutes=28,
                    ),
                    models.HistoricalGameLog(
                        game_id="0022500995",
                        game_date=datetime(2025, 11, 6, 19, 30),
                        player_id="202",
                        player_name="Away Fringe",
                        team="NYK",
                        opponent="BOS",
                        is_home=False,
                        minutes=2,
                    ),
                    models.HistoricalGameLog(
                        game_id="0022500995",
                        game_date=datetime(2025, 11, 6, 19, 30),
                        player_id="101",
                        player_name="Home Starter",
                        team="BOS",
                        opponent="NYK",
                        is_home=True,
                        minutes=31,
                    ),
                ]
            )

        payload = {
            "game_id": "0022500995",
            "url": "https://nbarotations.info/game/0022500995",
            "title": "New York Knicks 101 @ Boston Celtics 108",
            "raw_sections": {
                "away": [
                    {"name": "Away Starter", "histogram": [1, 1, 0, 0]},
                    {"name": "Away Fringe", "histogram": [0, 0, 1, 0]},
                ],
                "home": [{"name": "Home Starter", "histogram": [0, 1, 1, 1]}],
            },
        }

        result = rotation_provider._normalize_scraped_game("0022500995", payload)

        self.assertIsNone(result.error_type)
        self.assertEqual(len(result.player_rotation_games), 3)
        self.assertEqual({row["player_id"] for row in result.player_rotation_games}, {"101", "201", "202"})

    def test_normalize_scraped_game_tolerates_zero_window_scraper_players(self) -> None:
        with db_module.session_scope() as session:
            session.add(
                models.Game(
                    game_id="0022500994",
                    season="2025-26",
                    game_date=datetime(2025, 11, 7, 19, 30),
                    home_team_id="1610612738",
                    away_team_id="1610612752",
                    home_team_abbreviation="BOS",
                    away_team_abbreviation="NYK",
                )
            )
            session.add_all(
                [
                    models.HistoricalGameLog(
                        game_id="0022500994",
                        game_date=datetime(2025, 11, 7, 19, 30),
                        player_id="201",
                        player_name="Away Starter",
                        team="NYK",
                        opponent="BOS",
                        is_home=False,
                        minutes=28,
                    ),
                    models.HistoricalGameLog(
                        game_id="0022500994",
                        game_date=datetime(2025, 11, 7, 19, 30),
                        player_id="101",
                        player_name="Home Starter",
                        team="BOS",
                        opponent="NYK",
                        is_home=True,
                        minutes=31,
                    ),
                    models.HistoricalGameLog(
                        game_id="0022500994",
                        game_date=datetime(2025, 11, 7, 19, 30),
                        player_id="102",
                        player_name="Home Zero Window",
                        team="BOS",
                        opponent="NYK",
                        is_home=True,
                        minutes=5,
                    ),
                ]
            )

        payload = {
            "game_id": "0022500994",
            "url": "https://nbarotations.info/game/0022500994",
            "title": "New York Knicks 101 @ Boston Celtics 108",
            "raw_sections": {
                "away": [{"name": "Away Starter", "histogram": [1, 1, 0, 0]}],
                "home": [
                    {"name": "Home Starter", "histogram": [0, 1, 1, 1]},
                    {"name": "Home Zero Window", "histogram": [0, 0, 0, 0]},
                ],
            },
        }

        result = rotation_provider._normalize_scraped_game("0022500994", payload)

        self.assertIsNone(result.error_type)
        self.assertEqual(len(result.player_rotation_games), 2)
        self.assertEqual({row["player_id"] for row in result.player_rotation_games}, {"101", "201"})

    def test_normalize_scraped_game_fails_when_players_do_not_map(self) -> None:
        with db_module.session_scope() as session:
            session.add(
                models.Game(
                    game_id="0022500997",
                    season="2025-26",
                    game_date=datetime(2025, 11, 4, 19, 30),
                    home_team_id="1610612738",
                    away_team_id="1610612752",
                    home_team_abbreviation="BOS",
                    away_team_abbreviation="NYK",
                )
            )
            session.add_all(
                [
                    models.HistoricalGameLog(
                        game_id="0022500997",
                        game_date=datetime(2025, 11, 4, 19, 30),
                        player_id="201",
                        player_name="Away Player",
                        team="NYK",
                        opponent="BOS",
                        is_home=False,
                    ),
                    models.HistoricalGameLog(
                        game_id="0022500997",
                        game_date=datetime(2025, 11, 4, 19, 30),
                        player_id="101",
                        player_name="Home Player",
                        team="BOS",
                        opponent="NYK",
                        is_home=True,
                    ),
                ]
            )

        payload = {
            "game_id": "0022500997",
            "url": "https://nbarotations.info/game/0022500997",
            "title": "New York Knicks 99 @ Boston Celtics 103",
            "raw_sections": {
                "away": [{"name": "Unknown Away", "histogram": [1, 1, 0, 0]}],
                "home": [{"name": "Home Player", "histogram": [1, 1, 1, 1]}],
            },
        }

        result = rotation_provider._normalize_scraped_game("0022500997", payload)

        self.assertEqual(result.error_type, "identity_mapping_failure")
        self.assertEqual(result.player_rotation_games, [])
        self.assertEqual(result.error_details["expected_player_count"], 2)
        self.assertEqual(result.error_details["mapped_player_count"], 1)

class SyncGameRotationTests(unittest.TestCase):
    def test_sync_rotation_records_underlying_error_text_and_details(self) -> None:
        failed_result = rotation_provider.RotationBundleResult(
            error_type="identity_mapping_failure",
            error_text="Rotation scraper could not map all players for game 0022500127.",
            error_details={"expected_player_count": 10, "mapped_player_count": 9},
        )

        with patch("ingestion.jobs.get_rotation_bundle", return_value=failed_result), patch("ingestion.jobs.write_source_payloads"), patch("ingestion.jobs.create_ingestion_run_item") as run_item_mock:
            result = jobs._sync_rotation_for_game("0022500127", run_id=17)

        self.assertEqual(result["error_type"], "identity_mapping_failure")
        self.assertIn("could not map", result["error_text"])

        self.assertFalse(result["complete"])
        self.assertEqual(result["error_details"]["expected_player_count"], 10)
        self.assertEqual(run_item_mock.call_args.kwargs["metrics"]["error_type"], "identity_mapping_failure")
        self.assertEqual(run_item_mock.call_args.kwargs["metrics"]["mapped_player_count"], 9)

    def test_sync_rotation_records_success_coverage_metrics(self) -> None:
        success_result = rotation_provider.RotationBundleResult(
            rotations=[{"game_id": "0022500127", "player_id": "1"}],
            team_rotation_games=[{"game_id": "0022500127", "team_id": "1"}],
            player_rotation_games=[{"game_id": "0022500127", "player_id": "1"}],
            coverage_metrics={
                "expected_player_count": 10,
                "historical_player_count": 12,
                "mapped_player_count": 9,
                "covered_player_count": 10,
                "zero_window_player_count": 1,
            },
        )

        with patch("ingestion.jobs.get_rotation_bundle", return_value=success_result), patch(
            "ingestion.jobs.write_source_payloads"
        ), patch("ingestion.jobs.write_players"), patch("ingestion.jobs.write_team_rotation_games"), patch(
            "ingestion.jobs.write_player_rotation_games"
        ), patch("ingestion.jobs.write_player_rotation_stints"), patch(
            "ingestion.jobs.create_ingestion_run_item"
        ) as run_item_mock:
            result = jobs._sync_rotation_for_game("0022500127", run_id=17)

        self.assertTrue(result["complete"])
        self.assertEqual(result["coverage_metrics"]["covered_player_count"], 10)
        self.assertEqual(run_item_mock.call_args.kwargs["metrics"]["expected_player_count"], 10)
        self.assertEqual(run_item_mock.call_args.kwargs["metrics"]["zero_window_player_count"], 1)


class RotationQueueExecutionTests(unittest.TestCase):
    def test_specific_game_retry_batches_do_not_repeat_same_ids(self) -> None:
        selection_calls: list[list[str] | None] = []

        def fake_select_rotation_sync_batch(
            *,
            season,
            batch_size,
            specific_game_ids,
            force_retry,
            include_partial_success=False,
            exclude_game_ids=None,
        ):
            selection_calls.append(list(specific_game_ids) if specific_game_ids is not None else None)
            if specific_game_ids:
                return {
                    "selected_game_ids": list(specific_game_ids),
                    "pending_games_selected": 0,
                    "retry_games_selected": len(specific_game_ids),
                    "partial_success_games_selected": 0,
                    "skipped_cooldown_games": 0,
                    "quarantined_games": 0,
                }
            return {
                "selected_game_ids": [],
                "pending_games_selected": 0,
                "retry_games_selected": 0,
                "partial_success_games_selected": 0,
                "skipped_cooldown_games": 0,
                "quarantined_games": 0,
            }

        with patch("ingestion.jobs.seed_rotation_sync_states", return_value={
            "seeded_games": 2,
            "created_states": 0,
            "success_states": 0,
            "pending_states": 0,
            "retry_states": 2,
            "quarantined_states": 0,
        }), patch("ingestion.jobs.select_rotation_sync_batch", side_effect=fake_select_rotation_sync_batch), patch(
            "ingestion.jobs._sync_rotation_for_game",
            return_value={
                "rotation_stints": 1,
                "team_rotation_games": 1,
                "player_rotation_games": 1,
                "raw_payloads": 1,
                "error_type": None,
                "error_text": None,
                "error_details": {},
                "complete": True,
            },
        ), patch("ingestion.jobs.record_rotation_sync_attempt"), patch(
            "ingestion.jobs.get_rotation_backlog", return_value=[]
        ):
            result = jobs._process_rotation_sync_queue_impl(
                season="2025-26",
                batch_size=5,
                max_batches=3,
                specific_game_ids=["0022500001", "0022500002"],
                force_retry=True,
                run_id=17,
            )

        self.assertEqual(result["games_processed"], 2)
        self.assertEqual(selection_calls, [["0022500001", "0022500002"], []])

    def test_backfill_revisits_partial_success_games_once_per_run(self) -> None:
        selection_calls: list[dict[str, object]] = []

        def fake_select_rotation_sync_batch(
            *,
            season,
            batch_size,
            specific_game_ids,
            force_retry,
            include_partial_success=False,
            exclude_game_ids=None,
        ):
            selection_calls.append(
                {
                    "include_partial_success": include_partial_success,
                    "exclude_game_ids": list(exclude_game_ids) if exclude_game_ids is not None else None,
                }
            )
            if exclude_game_ids:
                return {
                    "selected_game_ids": [],
                    "pending_games_selected": 0,
                    "retry_games_selected": 0,
                    "partial_success_games_selected": 0,
                    "skipped_cooldown_games": 0,
                    "quarantined_games": 0,
                }
            return {
                "selected_game_ids": ["0022500001"],
                "pending_games_selected": 0,
                "retry_games_selected": 0,
                "partial_success_games_selected": 1,
                "skipped_cooldown_games": 0,
                "quarantined_games": 0,
            }

        with patch("ingestion.jobs.seed_rotation_sync_states", return_value={
            "seeded_games": 1,
            "created_states": 0,
            "success_states": 1,
            "pending_states": 0,
            "retry_states": 0,
            "quarantined_states": 0,
        }), patch("ingestion.jobs.select_rotation_sync_batch", side_effect=fake_select_rotation_sync_batch), patch(
            "ingestion.jobs._sync_rotation_for_game",
            return_value={
                "rotation_stints": 1,
                "team_rotation_games": 1,
                "player_rotation_games": 1,
                "raw_payloads": 1,
                "error_type": None,
                "error_text": None,
                "error_details": {},
                "complete": True,
            },
        ), patch("ingestion.jobs.record_rotation_sync_attempt"), patch(
            "ingestion.jobs.get_rotation_backlog",
            return_value=[{"game_id": "0022500001", "historical_players": 2, "rotation_players": 1, "missing_players": 1}],
        ):
            result = jobs._process_rotation_sync_queue_impl(
                season="2025-26",
                batch_size=1,
                max_batches=2,
                include_partial_success=True,
                run_id=17,
            )

        self.assertEqual(result["games_processed"], 1)
        self.assertEqual(result["partial_success_games_selected"], 1)
        self.assertTrue(selection_calls[0]["include_partial_success"])
        self.assertEqual(selection_calls[1]["exclude_game_ids"], ["0022500001"])

    def test_backfill_historical_rotations_enables_partial_success_revisit(self) -> None:
        with patch("ingestion.jobs._run_logged_job", return_value={"run_id": 11}) as run_logged_job:
            jobs.backfill_historical_rotations(
                season="2025-26",
                batch_size=7,
                max_batches=2,
                specific_game_ids=["0022500001"],
            )

        self.assertEqual(
            run_logged_job.call_args.args,
            (
                "backfill_historical_rotations",
                jobs._process_rotation_sync_queue_impl,
                "2025-26",
                7,
                2,
                ["0022500001"],
                False,
                True,
            ),
        )

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
        ), patch("ingestion.jobs._sync_rotation_for_game", side_effect=AssertionError("rotation fetch should not run inline")):
            result = jobs._backfill_postgame_enrichment_impl(season="2025-26", batch_size=1, max_batches=1, run_id=11)

        self.assertEqual(result["rotation_queue_games_enqueued"], 1)
        enqueue_mock.assert_called_once_with(["0022500999"], season="2025-26")
        self.assertEqual(run_item_mock.call_args.kwargs["metrics"]["rotation_queue_games_enqueued"], 1)


if __name__ == "__main__":
    unittest.main()

