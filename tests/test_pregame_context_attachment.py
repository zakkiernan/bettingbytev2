from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database.db import Base
from database.models import Game, PlayerPropSnapshot, Team
from ingestion.pregame_context import summarize_pregame_context_attachment


class PregameContextAttachmentSummaryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)
        Base.metadata.create_all(self.engine, tables=[Team.__table__, Game.__table__, PlayerPropSnapshot.__table__])

    def tearDown(self):
        Base.metadata.drop_all(self.engine, tables=[PlayerPropSnapshot.__table__, Game.__table__, Team.__table__])
        self.engine.dispose()

    @contextmanager
    def session_scope(self):
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _seed_team(self, session, team_id: str, abbr: str) -> None:
        session.add(Team(team_id=team_id, abbreviation=abbr, full_name=f"{abbr} Test", city=abbr, nickname=abbr))

    def test_summary_separates_empty_source_games_from_overlap_coverage(self):
        captured_at = datetime(2026, 3, 12, 18, 0, 0)
        with self.session_scope() as session:
            self._seed_team(session, "1", "AAA")
            self._seed_team(session, "2", "BBB")
            self._seed_team(session, "3", "CCC")
            self._seed_team(session, "4", "DDD")
            session.add_all([
                Game(game_id="G1", season="2025-26", game_date=captured_at, game_time_utc=captured_at, away_team_id="1", home_team_id="2", away_team_abbreviation="AAA", home_team_abbreviation="BBB", game_status=1, status_text="7:00 pm ET"),
                Game(game_id="G2", season="2025-26", game_date=captured_at, game_time_utc=captured_at, away_team_id="3", home_team_id="4", away_team_abbreviation="CCC", home_team_abbreviation="DDD", game_status=1, status_text="8:00 pm ET"),
                PlayerPropSnapshot(game_id="G1", player_id="10", player_name="Alpha One", team="AAA", opponent="BBB", stat_type="points", line=18.5, over_odds=-110, under_odds=-110, is_live=False, captured_at=captured_at),
                PlayerPropSnapshot(game_id="G2", player_id="20", player_name="Beta Two", team="CCC", opponent="DDD", stat_type="points", line=14.5, over_odds=-110, under_odds=-110, is_live=False, captured_at=captured_at),
            ])

        feature_rows = [
            {
                "game_id": "G1",
                "team_id": "1",
                "team_abbr": "AAA",
                "opponent_team_id": "2",
                "player_id": "10",
                "player_key": "id:10",
                "player_name": "Alpha One",
                "expected_start": True,
                "projected_available": True,
                "pregame_context_confidence": 0.9,
                "captured_at": captured_at,
            }
        ]
        payload = {
            "games": [
                {
                    "game_id": "G1",
                    "sources_present": {"nba_live_boxscore": True, "rotowire_lineups": True},
                    "availability": [{"player_name": "Alpha One"}],
                    "projected_starters": [],
                    "projected_absences": [],
                },
                {
                    "game_id": "G2",
                    "sources_present": {"nba_live_boxscore": False, "rotowire_lineups": False},
                    "availability": [],
                    "projected_starters": [],
                    "projected_absences": [],
                },
            ]
        }

        with patch('ingestion.pregame_context.session_scope', self.session_scope):
            summary = summarize_pregame_context_attachment(feature_rows=feature_rows, captured_at=captured_at, payload=payload)

        self.assertEqual(summary["market_count"], 2)
        self.assertEqual(summary["attached_count"], 1)
        self.assertEqual(summary["overlap_market_count"], 1)
        self.assertEqual(summary["overlap_attached_count"], 1)
        self.assertAlmostEqual(summary["overlap_attached_pct"], 1.0)
        self.assertEqual(summary["missing_context_game_ids"], ["G2"])
        self.assertEqual(summary["empty_source_game_ids"], ["G2"])
        self.assertEqual(summary["empty_source_market_count"], 1)
        self.assertEqual(summary["partial_source_game_ids"], [])

    def test_summary_tracks_missing_markets_inside_covered_games(self):
        captured_at = datetime(2026, 3, 12, 18, 0, 0)
        with self.session_scope() as session:
            self._seed_team(session, "1", "AAA")
            self._seed_team(session, "2", "BBB")
            session.add_all([
                Game(game_id="G1", season="2025-26", game_date=captured_at, game_time_utc=captured_at, away_team_id="1", home_team_id="2", away_team_abbreviation="AAA", home_team_abbreviation="BBB", game_status=1, status_text="7:00 pm ET"),
                PlayerPropSnapshot(game_id="G1", player_id="10", player_name="Alpha One", team="AAA", opponent="BBB", stat_type="points", line=18.5, over_odds=-110, under_odds=-110, is_live=False, captured_at=captured_at),
                PlayerPropSnapshot(game_id="G1", player_id="11", player_name="Gamma Three", team="AAA", opponent="BBB", stat_type="points", line=11.5, over_odds=-110, under_odds=-110, is_live=False, captured_at=captured_at),
            ])

        feature_rows = [
            {
                "game_id": "G1",
                "team_id": "1",
                "team_abbr": "AAA",
                "opponent_team_id": "2",
                "player_id": "10",
                "player_key": "id:10",
                "player_name": "Alpha One",
                "expected_start": True,
                "projected_available": True,
                "pregame_context_confidence": 0.9,
                "captured_at": captured_at,
            }
        ]
        payload = {
            "games": [
                {
                    "game_id": "G1",
                    "sources_present": {"nba_live_boxscore": False, "rotowire_lineups": True},
                    "availability": [],
                    "projected_starters": [{"player_name": "Alpha One"}],
                    "projected_absences": [],
                }
            ]
        }

        with patch('ingestion.pregame_context.session_scope', self.session_scope):
            summary = summarize_pregame_context_attachment(feature_rows=feature_rows, captured_at=captured_at, payload=payload)

        self.assertEqual(summary["overlap_market_count"], 2)
        self.assertEqual(summary["overlap_attached_count"], 1)
        self.assertEqual(summary["missing_overlap_market_count"], 1)
        self.assertEqual(summary["partial_source_game_ids"], ["G1"])
        self.assertEqual(summary["partial_source_market_count"], 2)
        self.assertEqual(summary["missing_overlap_examples"][0]["player_name"], "Gamma Three")


if __name__ == "__main__":
    unittest.main()
