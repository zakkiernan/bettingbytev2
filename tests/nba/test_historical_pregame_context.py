from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database.db import Base
from database.models import (
    Game,
    HistoricalAdvancedLog,
    HistoricalGameLog,
    OddsSnapshot,
    OfficialInjuryReport,
    OfficialInjuryReportEntry,
    PlayerRotationGame,
    PregameContextSnapshot,
    Team,
)
from ingestion.historical_pregame_context import backfill_historical_pregame_context


class HistoricalPregameContextBackfillTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)
        Base.metadata.create_all(
            self.engine,
            tables=[
                Team.__table__,
                Game.__table__,
                HistoricalGameLog.__table__,
                HistoricalAdvancedLog.__table__,
                PlayerRotationGame.__table__,
                OddsSnapshot.__table__,
                OfficialInjuryReport.__table__,
                OfficialInjuryReportEntry.__table__,
                PregameContextSnapshot.__table__,
            ],
        )

    def tearDown(self):
        Base.metadata.drop_all(
            self.engine,
            tables=[
                PregameContextSnapshot.__table__,
                OfficialInjuryReportEntry.__table__,
                OfficialInjuryReport.__table__,
                OddsSnapshot.__table__,
                PlayerRotationGame.__table__,
                HistoricalAdvancedLog.__table__,
                HistoricalGameLog.__table__,
                Game.__table__,
                Team.__table__,
            ],
        )
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

    def _seed_core(self) -> None:
        with self.session_scope() as session:
            session.add_all([
                Team(team_id="1610612739", abbreviation="CLE", full_name="Cleveland Cavaliers"),
                Team(team_id="1610612742", abbreviation="DAL", full_name="Dallas Mavericks"),
            ])
            game_dt = datetime(2026, 3, 10, 23, 0, 0)
            session.add(
                Game(
                    game_id="002TEST",
                    season="2025-26",
                    game_date=game_dt,
                    game_time_utc=game_dt,
                    home_team_id="1610612739",
                    away_team_id="1610612742",
                    home_team_abbreviation="CLE",
                    away_team_abbreviation="DAL",
                    game_status=1,
                    status_text="7:00 pm ET",
                )
            )
            # prior logs + one current-game participant row for reconstruction target
            for game_id, game_date, player_id, player_name, team, opp, minutes, points, rebounds, assists, blocks in [
                ("P1", datetime(2026, 3, 1, 0, 0, 0), "1", "Evan Mobley", "CLE", "BOS", 34.0, 21.0, 10.0, 4.0, 1.8),
                ("P2", datetime(2026, 3, 3, 0, 0, 0), "1", "Evan Mobley", "CLE", "POR", 35.0, 24.0, 11.0, 3.0, 2.1),
                ("P3", datetime(2026, 3, 1, 0, 0, 0), "2", "Jarrett Allen", "CLE", "BOS", 33.0, 17.0, 12.0, 2.0, 1.6),
                ("P4", datetime(2026, 3, 3, 0, 0, 0), "2", "Jarrett Allen", "CLE", "POR", 32.0, 18.0, 13.0, 1.0, 1.7),
                ("P5", datetime(2026, 3, 1, 0, 0, 0), "3", "Darius Garland", "CLE", "BOS", 34.0, 19.0, 2.0, 8.0, 0.1),
                ("P6", datetime(2026, 3, 3, 0, 0, 0), "3", "Darius Garland", "CLE", "POR", 35.0, 22.0, 3.0, 9.0, 0.1),
                ("002TEST", datetime(2026, 3, 10, 23, 0, 0), "1", "Evan Mobley", "CLE", "DAL", 36.0, 26.0, 12.0, 4.0, 2.0),
            ]:
                session.add(HistoricalGameLog(
                    game_id=game_id,
                    game_date=game_date,
                    player_id=player_id,
                    player_name=player_name,
                    team=team,
                    opponent=opp,
                    is_home=True,
                    minutes=minutes,
                    points=points,
                    rebounds=rebounds,
                    assists=assists,
                    steals=1.0,
                    blocks=blocks,
                    turnovers=2.0,
                    threes_made=1.0,
                    threes_attempted=3.0,
                    field_goals_made=8.0,
                    field_goals_attempted=15.0,
                    free_throws_made=4.0,
                    free_throws_attempted=5.0,
                    plus_minus=3.0,
                ))
            for game_id, player_id, usage, touches, passes in [
                ("P1", "1", 0.24, 46.0, 28.0),
                ("P2", "1", 0.25, 47.0, 27.0),
                ("P3", "2", 0.21, 41.0, 18.0),
                ("P4", "2", 0.22, 40.0, 17.0),
                ("P5", "3", 0.27, 76.0, 58.0),
                ("P6", "3", 0.28, 74.0, 57.0),
            ]:
                session.add(HistoricalAdvancedLog(
                    game_id=game_id,
                    player_id=player_id,
                    player_name="x",
                    usage_percentage=usage,
                    estimated_usage_percentage=usage,
                    touches=touches,
                    passes=passes,
                ))
            for game_id, player_id, started, closed in [
                ("P1", "1", True, True),
                ("P2", "1", True, True),
                ("P3", "2", True, True),
                ("P4", "2", True, True),
                ("P5", "3", True, True),
                ("P6", "3", True, True),
            ]:
                session.add(PlayerRotationGame(
                    game_id=game_id,
                    team_id="1610612739",
                    team_abbreviation="CLE",
                    player_id=player_id,
                    player_name="x",
                    started=started,
                    played_opening_stint=started,
                    closed_game=closed,
                    stint_count=6,
                    total_shift_duration_real=32.0,
                ))
            session.add(OddsSnapshot(
                game_id="002TEST",
                player_id="1",
                player_name="Evan Mobley",
                stat_type="points",
                line=18.5,
                over_odds=-110,
                under_odds=-110,
                source="fanduel",
                market_phase="pregame",
                captured_at=datetime(2026, 3, 10, 20, 0, 0),
            ))
            report_dt = datetime(2026, 3, 10, 18, 0, 0)
            session.add(OfficialInjuryReport(
                id=1,
                season="2025-26",
                report_date=date(2026, 3, 10),
                report_time_et="1:00 PM",
                report_datetime_utc=report_dt,
                pdf_url="https://example.com/report.pdf",
                pdf_sha256="deadbeef",
                game_count=1,
                entry_count=1,
            ))
            session.add(OfficialInjuryReportEntry(
                report_id=1,
                game_date=date(2026, 3, 10),
                report_datetime_utc=report_dt,
                matchup="DAL @ CLE",
                team_id="1610612739",
                team_abbreviation="CLE",
                team_name="Cleveland Cavaliers",
                player_id="2",
                player_name="Jarrett Allen",
                current_status="Out",
                reason="Rest",
                report_submitted=True,
            ))

    def test_backfill_reconstructs_role_based_context_and_writes_snapshot(self):
        self._seed_core()

        with patch("ingestion.historical_pregame_context.session_scope", self.session_scope), patch("ingestion.writer.session_scope", self.session_scope):
            result = backfill_historical_pregame_context(
                start_date=datetime(2026, 3, 10, 0, 0, 0),
                end_date=datetime(2026, 3, 10, 23, 59, 59),
                persist=True,
            )

        self.assertEqual(result["game_count"], 1)
        self.assertEqual(result["row_count"], 1)

        with self.session_scope() as session:
            row = session.query(PregameContextSnapshot).one()
            self.assertEqual(row.player_id, "1")
            self.assertEqual(row.team_abbreviation, "CLE")
            self.assertGreater(row.vacated_minutes_proxy or 0.0, 0.0)
            self.assertGreater(row.pregame_context_confidence or 0.0, 0.0)
            self.assertTrue(
                (row.role_replacement_minutes_proxy or 0.0) > 0.0
                or bool(row.missing_frontcourt_rotation_piece)
            )


if __name__ == "__main__":
    unittest.main()
