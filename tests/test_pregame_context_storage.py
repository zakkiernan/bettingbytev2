from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database.db import Base
from database.models import PregameContextSnapshot
from ingestion.writer import write_pregame_context_snapshots


class PregameContextStorageTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)
        Base.metadata.create_all(self.engine, tables=[PregameContextSnapshot.__table__])

    def tearDown(self):
        Base.metadata.drop_all(self.engine, tables=[PregameContextSnapshot.__table__])
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

    def test_write_pregame_context_snapshots_upserts_by_game_player_and_capture(self):
        captured_at = datetime(2026, 3, 12, 18, 0, 0)
        base_row = {
            "game_id": "002TEST",
            "team_id": "1610612738",
            "team_abbr": "BOS",
            "opponent_team_id": "1610612752",
            "player_id": "7",
            "player_key": "7",
            "normalized_player_name": "jaylen brown",
            "player_name": "Jaylen Brown",
            "expected_start": False,
            "starter_confidence": 0.35,
            "official_available": True,
            "projected_available": True,
            "late_scratch_risk": 0.1,
            "teammate_out_count_top7": 1.0,
            "teammate_out_count_top9": 1.0,
            "missing_high_usage_teammates": 1.0,
            "missing_primary_ballhandler": False,
            "missing_frontcourt_rotation_piece": False,
            "vacated_minutes_proxy": 18.0,
            "vacated_usage_proxy": 0.05,
            "projected_lineup_confirmed": False,
            "official_starter_flag": False,
            "pregame_context_confidence": 0.55,
            "source_captured_at": captured_at,
            "captured_at": captured_at,
        }

        updated_row = dict(base_row)
        updated_row.update({
            "expected_start": True,
            "starter_confidence": 0.92,
            "projected_lineup_confirmed": True,
            "pregame_context_confidence": 0.88,
        })

        with patch('ingestion.writer.session_scope', self.session_scope):
            write_pregame_context_snapshots([base_row], captured_at=captured_at)
            write_pregame_context_snapshots([updated_row], captured_at=captured_at)

        with self.session_scope() as session:
            rows = session.query(PregameContextSnapshot).all()
            self.assertEqual(len(rows), 1)
            stored = rows[0]
            self.assertTrue(stored.expected_start)
            self.assertAlmostEqual(stored.starter_confidence, 0.92)
            self.assertTrue(stored.projected_lineup_confirmed)
            self.assertAlmostEqual(stored.pregame_context_confidence, 0.88)
            self.assertEqual(stored.normalized_player_name, "jaylen brown")


if __name__ == "__main__":
    unittest.main()
