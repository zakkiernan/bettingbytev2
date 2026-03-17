from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from database.db import Base
from database.models import PregameContextSnapshot
from ingestion.pregame_context import backfill_pregame_context_snapshots_from_files, _serialize_feature_rows
from ingestion.writer import write_pregame_context_snapshots, write_prop_snapshot


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

    def test_serialize_feature_rows_converts_datetimes_to_iso_strings(self):
        rows = _serialize_feature_rows([
            {
                "game_id": "002TEST",
                "player_name": "Jaylen Brown",
                "captured_at": datetime(2026, 3, 12, 18, 0, 0),
                "source_captured_at": datetime(2026, 3, 12, 17, 45, 0),
            }
        ])

        self.assertEqual(rows[0]["captured_at"], "2026-03-12T18:00:00")
        self.assertEqual(rows[0]["source_captured_at"], "2026-03-12T17:45:00")

    def test_backfill_pregame_context_snapshots_from_files_normalizes_legacy_rows(self):
        legacy_rows = [
            {
                "asof_utc": "2026-03-12T01:50:42.253258+00:00",
                "game_id": "002TEST",
                "team_id": 1610612738,
                "team_abbr": "BOS",
                "opponent_team_id": 1610612752,
                "player_id": 7,
                "player_key": "id:7",
                "player_name": "Jaylen Brown",
                "expected_start": True,
                "starter_confidence": 0.9,
                "official_available": True,
                "projected_available": True,
                "late_scratch_risk": 0.05,
                "teammate_out_count_top7": 1,
                "teammate_out_count_top9": 2,
                "missing_high_usage_teammates": 1,
                "missing_primary_ballhandler": False,
                "missing_frontcourt_rotation_piece": False,
                "vacated_minutes_proxy": 18.0,
                "vacated_usage_proxy": 0.05,
                "projected_lineup_confirmed": True,
                "official_starter_flag": True,
                "pregame_context_confidence": 0.95,
            }
        ]

        temp_dir = Path('tests') / '_tmp_pregame_context_storage'
        shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            history_dir = temp_dir / "history"
            history_dir.mkdir(parents=True, exist_ok=True)
            (history_dir / "20260312_015001.json").write_text(json.dumps(legacy_rows), encoding="utf-8")

            isolated_latest = temp_dir / 'latest.json'
            with patch('ingestion.writer.session_scope', self.session_scope):
                result = backfill_pregame_context_snapshots_from_files(history_dir=history_dir, latest_path=isolated_latest)

            self.assertEqual(result["file_count"], 1)
            self.assertEqual(result["row_count"], 1)

            with self.session_scope() as session:
                stored = session.query(PregameContextSnapshot).one()
                self.assertEqual(stored.team_abbreviation, "BOS")
                self.assertEqual(stored.player_id, "7")
                self.assertEqual(stored.normalized_player_name, "jaylen brown")
                self.assertEqual(stored.captured_at.isoformat(), "2026-03-12T01:50:42.253258")
                self.assertEqual(stored.source_captured_at.isoformat(), "2026-03-12T01:50:42.253258")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_write_prop_snapshot_handles_legacy_schema_without_snapshot_phase(self):
        engine = create_engine("sqlite:///:memory:", future=True)
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)

        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE player_prop_snapshots (
                    id INTEGER PRIMARY KEY,
                    game_id VARCHAR NOT NULL,
                    player_id VARCHAR NOT NULL,
                    player_name VARCHAR NOT NULL,
                    team VARCHAR NULL,
                    opponent VARCHAR NULL,
                    stat_type VARCHAR NOT NULL,
                    line FLOAT NOT NULL,
                    over_odds INTEGER NOT NULL,
                    under_odds INTEGER NOT NULL,
                    is_live BOOLEAN NOT NULL,
                    captured_at DATETIME NOT NULL
                )
            """))

        @contextmanager
        def legacy_session_scope():
            session = SessionLocal()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        captured_at = datetime(2026, 3, 13, 18, 0, 0)
        base_prop = {
            "game_id": "002TEST",
            "player_id": "7",
            "player_name": "Jaylen Brown",
            "team": "BOS",
            "opponent": "NYK",
            "stat_type": "points",
            "line": 24.5,
            "over_odds": -110,
            "under_odds": -110,
            "captured_at": captured_at,
        }
        updated_prop = dict(base_prop)
        updated_prop.update({
            "line": 25.5,
            "captured_at": datetime(2026, 3, 13, 18, 5, 0),
        })

        with patch('ingestion.writer.session_scope', legacy_session_scope):
            write_prop_snapshot([base_prop], is_live=False)
            write_prop_snapshot([updated_prop], is_live=False)

        with legacy_session_scope() as session:
            rows = session.execute(text("SELECT game_id, player_id, line, captured_at FROM player_prop_snapshots")).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].game_id, "002TEST")
            self.assertEqual(rows[0].player_id, "7")
            self.assertEqual(rows[0].line, 25.5)

        engine.dispose()

    def test_write_prop_snapshot_prunes_stale_rows_for_games_in_latest_board(self):
        engine = create_engine("sqlite:///:memory:", future=True)
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)

        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE player_prop_snapshots (
                    id INTEGER PRIMARY KEY,
                    game_id VARCHAR NOT NULL,
                    player_id VARCHAR NOT NULL,
                    player_name VARCHAR NOT NULL,
                    team VARCHAR NULL,
                    opponent VARCHAR NULL,
                    stat_type VARCHAR NOT NULL,
                    line FLOAT NOT NULL,
                    over_odds INTEGER NOT NULL,
                    under_odds INTEGER NOT NULL,
                    is_live BOOLEAN NOT NULL,
                    captured_at DATETIME NOT NULL,
                    snapshot_phase VARCHAR NOT NULL
                )
            """))

        @contextmanager
        def prop_session_scope():
            session = SessionLocal()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        captured_at = datetime(2026, 3, 16, 4, 35, 36)
        base_props = [
            {
                "game_id": "0022500989",
                "player_id": "2544",
                "player_name": "LeBron James",
                "team": "LAL",
                "opponent": "HOU",
                "stat_type": "points",
                "line": 18.5,
                "over_odds": -102,
                "under_odds": -118,
                "captured_at": captured_at,
            },
            {
                "game_id": "0022500989",
                "player_id": "203954",
                "player_name": "Jabari Smith",
                "team": None,
                "opponent": None,
                "stat_type": "points",
                "line": 15.5,
                "over_odds": -110,
                "under_odds": -110,
                "captured_at": captured_at,
            },
        ]
        refreshed_props = [dict(base_props[0], captured_at=datetime(2026, 3, 16, 4, 49, 49))]

        with patch('ingestion.writer.session_scope', prop_session_scope):
            write_prop_snapshot(base_props, is_live=False, snapshot_phase="current")
            write_prop_snapshot(refreshed_props, is_live=False, snapshot_phase="current")

        with prop_session_scope() as session:
            rows = session.execute(
                text("SELECT game_id, player_id, player_name FROM player_prop_snapshots ORDER BY player_id")
            ).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].player_id, "2544")
            self.assertEqual(rows[0].player_name, "LeBron James")

        engine.dispose()


if __name__ == "__main__":
    unittest.main()
