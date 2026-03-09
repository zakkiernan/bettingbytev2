from __future__ import annotations

import unittest
from datetime import datetime
from json import JSONDecodeError
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from database import db as db_module
from database import models
from ingestion import jobs, nba_client, validation


class GameRotationBundleTests(unittest.TestCase):
    def test_retries_full_bundle_after_transient_json_error(self) -> None:
        expected = (
            [{"game_id": "002TEST"}],
            [{"game_id": "002TEST", "team_id": "1610612738"}],
            [{"game_id": "002TEST", "player_id": "1", "player_name": "Test Player"}],
            [{"source": "nba", "payload_type": "game_rotation", "payload": {}}],
        )

        with patch.object(nba_client, "NBA_GAME_ROTATION_PASSES", 2), patch(
            "ingestion.nba_client._fetch_game_rotation_bundle_once",
            side_effect=[JSONDecodeError("Expecting value", "", 0), expected],
        ) as fetch_mock, patch("ingestion.nba_client.time.sleep"), patch("ingestion.nba_client.logger.warning"), patch("ingestion.nba_client.logger.exception"):
            rotations, team_summaries, player_summaries, payloads, error_text = nba_client.get_game_rotation_bundle("002TEST")

        self.assertEqual(fetch_mock.call_count, 2)
        self.assertEqual(rotations, expected[0])
        self.assertEqual(team_summaries, expected[1])
        self.assertEqual(player_summaries, expected[2])
        self.assertEqual(payloads, expected[3])
        self.assertIsNone(error_text)

    def test_preserves_underlying_error_text_after_retries_fail(self) -> None:
        with patch.object(nba_client, "NBA_GAME_ROTATION_PASSES", 2), patch(
            "ingestion.nba_client._fetch_game_rotation_bundle_once",
            side_effect=JSONDecodeError("Expecting value", "", 0),
        ) as fetch_mock, patch("ingestion.nba_client.time.sleep"), patch("ingestion.nba_client.logger.warning"), patch("ingestion.nba_client.logger.exception"):
            rotations, team_summaries, player_summaries, payloads, error_text = nba_client.get_game_rotation_bundle("002TEST")

        self.assertEqual(fetch_mock.call_count, 2)
        self.assertEqual(rotations, [])
        self.assertEqual(team_summaries, [])
        self.assertEqual(player_summaries, [])
        self.assertEqual(payloads, [])
        self.assertIsNotNone(error_text)
        self.assertIn("JSONDecodeError", error_text)
        self.assertIn("Expecting value", error_text)


class SyncGameRotationTests(unittest.TestCase):
    def test_sync_game_rotation_records_underlying_error_text(self) -> None:
        with patch(
            "ingestion.jobs.get_game_rotation_bundle",
            return_value=([], [], [], [], "JSONDecodeError: Expecting value"),
        ), patch("ingestion.jobs.write_source_payloads"), patch("ingestion.jobs.create_ingestion_run_item") as run_item_mock:
            result = jobs._sync_game_rotation_for_game("0022500127", run_id=17)

        self.assertEqual(result["error_text"], "JSONDecodeError: Expecting value")
        self.assertEqual(result["player_rotation_games"], 0)
        self.assertEqual(run_item_mock.call_args.kwargs["error_text"], "JSONDecodeError: Expecting value")


class ValidationSeasonScopeTests(unittest.TestCase):
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
        self._seed_data()

    def tearDown(self) -> None:
        db_module.SessionLocal = self.original_session_local
        db_module.engine = self.original_engine
        self.engine.dispose()

    def _seed_data(self) -> None:
        with db_module.session_scope() as session:
            session.add_all(
                [
                    models.Team(team_id="1610612738", abbreviation="BOS", full_name="Boston Celtics", is_active=True),
                    models.Team(team_id="1610612752", abbreviation="NYK", full_name="New York Knicks", is_active=True),
                    models.Team(team_id="1610612747", abbreviation="LAL", full_name="Los Angeles Lakers", is_active=True),
                    models.Team(team_id="1610612743", abbreviation="DEN", full_name="Denver Nuggets", is_active=True),
                ]
            )
            session.add_all(
                [
                    self._historical_log(
                        game_id="0022500001",
                        game_date=datetime(2025, 10, 25, 19, 30),
                        player_id="1",
                        player_name="Current Home",
                        team="BOS",
                        opponent="NYK",
                        is_home=True,
                    ),
                    self._historical_log(
                        game_id="0022500001",
                        game_date=datetime(2025, 10, 25, 19, 30),
                        player_id="2",
                        player_name="Current Away",
                        team="NYK",
                        opponent="BOS",
                        is_home=False,
                    ),
                    self._historical_log(
                        game_id="0022400001",
                        game_date=datetime(2024, 11, 1, 20, 0),
                        player_id="3",
                        player_name="Prior Home",
                        team="LAL",
                        opponent="DEN",
                        is_home=True,
                    ),
                    self._historical_log(
                        game_id="0022400001",
                        game_date=datetime(2024, 11, 1, 20, 0),
                        player_id="4",
                        player_name="Prior Away",
                        team="DEN",
                        opponent="LAL",
                        is_home=False,
                    ),
                ]
            )

    def _historical_log(
        self,
        *,
        game_id: str,
        game_date: datetime,
        player_id: str,
        player_name: str,
        team: str,
        opponent: str,
        is_home: bool,
    ) -> models.HistoricalGameLog:
        return models.HistoricalGameLog(
            game_id=game_id,
            game_date=game_date,
            player_id=player_id,
            player_name=player_name,
            team=team,
            opponent=opponent,
            is_home=is_home,
        )

    def test_postgame_backlog_honors_season(self) -> None:
        all_game_ids = {row["game_id"] for row in validation.get_postgame_enrichment_backlog()}
        current_season_game_ids = {row["game_id"] for row in validation.get_postgame_enrichment_backlog(season="2025-26")}

        self.assertEqual(all_game_ids, {"0022400001", "0022500001"})
        self.assertEqual(current_season_game_ids, {"0022500001"})

    def test_rotation_backlog_honors_season(self) -> None:
        all_game_ids = {row["game_id"] for row in validation.get_rotation_backlog()}
        current_season_game_ids = {row["game_id"] for row in validation.get_rotation_backlog(season="2025-26")}

        self.assertEqual(all_game_ids, {"0022400001", "0022500001"})
        self.assertEqual(current_season_game_ids, {"0022500001"})

    def test_missing_canonical_games_honors_season(self) -> None:
        all_game_ids = {row["game_id"] for row in validation.get_missing_canonical_games_from_history()}
        current_season_rows = validation.get_missing_canonical_games_from_history(season="2025-26")

        self.assertEqual(all_game_ids, {"0022400001", "0022500001"})
        self.assertEqual({row["game_id"] for row in current_season_rows}, {"0022500001"})
        self.assertEqual(current_season_rows[0]["season"], "2025-26")


if __name__ == "__main__":
    unittest.main()
