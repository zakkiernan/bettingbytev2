from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from analytics.absence_impact import (
    build_absence_impact_rows,
    build_and_persist_first_pass_absence_impact_batch,
    build_and_persist_starter_pool_absence_impact_batch,
    persist_absence_impact_rows,
    select_first_pass_absence_sources,
    select_starter_pool_absence_sources,
)
from database.db import Base
from database.models import (
    AbsenceImpactSummary,
    AbsenceSourceOverride,
    HistoricalAdvancedLog,
    HistoricalGameLog,
    OfficialInjuryReport,
    OfficialInjuryReportEntry,
    PlayerRotationGame,
)


class AbsenceImpactTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)
        Base.metadata.create_all(
            self.engine,
            tables=[
                HistoricalGameLog.__table__,
                HistoricalAdvancedLog.__table__,
                PlayerRotationGame.__table__,
                OfficialInjuryReport.__table__,
                OfficialInjuryReportEntry.__table__,
                AbsenceImpactSummary.__table__,
                AbsenceSourceOverride.__table__,
            ],
        )

    def tearDown(self):
        Base.metadata.drop_all(
            self.engine,
            tables=[
                AbsenceSourceOverride.__table__,
                AbsenceImpactSummary.__table__,
                OfficialInjuryReportEntry.__table__,
                OfficialInjuryReport.__table__,
                PlayerRotationGame.__table__,
                HistoricalAdvancedLog.__table__,
                HistoricalGameLog.__table__,
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

    def _seed(self) -> None:
        with self.session_scope() as session:
            # source active games
            active_games = [
                ("G1", datetime(2026, 1, 1), "100", "Source Star", "AAA", "BBB", True),
                ("G2", datetime(2026, 1, 3), "100", "Source Star", "AAA", "CCC", False),
                ("G3", datetime(2026, 1, 5), "100", "Source Star", "AAA", "DDD", True),
                ("G4", datetime(2026, 1, 7), "100", "Source Star", "AAA", "EEE", False),
                ("G5", datetime(2026, 1, 9), "100", "Source Star", "AAA", "FFF", True),
            ]
            for game_id, game_date, player_id, player_name, team, opp, is_home in active_games:
                session.add(HistoricalGameLog(
                    game_id=game_id,
                    game_date=game_date,
                    player_id=player_id,
                    player_name=player_name,
                    team=team,
                    opponent=opp,
                    is_home=is_home,
                    minutes=35.0,
                    points=28.0,
                    rebounds=7.0,
                    assists=8.0,
                    steals=1.0,
                    blocks=0.5,
                    turnovers=3.0,
                    threes_made=2.0,
                    threes_attempted=6.0,
                    field_goals_made=10.0,
                    field_goals_attempted=20.0,
                    free_throws_made=6.0,
                    free_throws_attempted=7.0,
                    plus_minus=5.0,
                ))
                session.add(HistoricalAdvancedLog(
                    game_id=game_id,
                    player_id=player_id,
                    player_name=player_name,
                    usage_percentage=0.31,
                    estimated_usage_percentage=0.31,
                    touches=75.0,
                    passes=55.0,
                ))

            # alternate source on same team that should lose the selector to Source Star
            alt_source_rows = [
                ("G1", datetime(2026, 1, 1), "101", "Alt Star", "AAA", "BBB", True, 20.0, 10.0, 3.0, 2.0, 0.2, 0.16, 28.0, 16.0),
                ("G2", datetime(2026, 1, 3), "101", "Alt Star", "AAA", "CCC", False, 21.0, 11.0, 3.0, 2.0, 0.2, 0.17, 29.0, 17.0),
                ("G3", datetime(2026, 1, 5), "101", "Alt Star", "AAA", "DDD", True, 19.0, 9.0, 3.0, 2.0, 0.2, 0.15, 27.0, 15.0),
                ("G4", datetime(2026, 1, 7), "101", "Alt Star", "AAA", "EEE", False, 20.0, 10.0, 3.0, 2.0, 0.2, 0.16, 28.0, 16.0),
                ("G5", datetime(2026, 1, 9), "101", "Alt Star", "AAA", "FFF", True, 21.0, 11.0, 3.0, 2.0, 0.2, 0.17, 29.0, 17.0),
                ("G8", datetime(2026, 1, 15), "101", "Alt Star", "AAA", "III", False, 22.0, 12.0, 3.0, 2.0, 0.2, 0.18, 30.0, 18.0),
            ]
            for game_id, game_date, player_id, player_name, team, opp, is_home, minutes, points, rebounds, assists, blocks, usage, touches, passes in alt_source_rows:
                session.add(HistoricalGameLog(
                    game_id=game_id,
                    game_date=game_date,
                    player_id=player_id,
                    player_name=player_name,
                    team=team,
                    opponent=opp,
                    is_home=is_home,
                    minutes=minutes,
                    points=points,
                    rebounds=rebounds,
                    assists=assists,
                    steals=1.0,
                    blocks=blocks,
                    turnovers=2.0,
                    threes_made=1.0,
                    threes_attempted=3.0,
                    field_goals_made=5.0,
                    field_goals_attempted=11.0,
                    free_throws_made=2.0,
                    free_throws_attempted=3.0,
                    plus_minus=1.0,
                ))
                session.add(HistoricalAdvancedLog(
                    game_id=game_id,
                    player_id=player_id,
                    player_name=player_name,
                    usage_percentage=usage,
                    estimated_usage_percentage=usage,
                    touches=touches,
                    passes=passes,
                ))

            # second team source + beneficiary so batch path covers >1 team
            team_b_rows = [
                ("H1", datetime(2026, 1, 2), "400", "Other Star", "BBB", "AAA", True, 34.0, 24.0, 6.0, 7.0, 0.5, 0.29, 68.0, 49.0),
                ("H2", datetime(2026, 1, 4), "400", "Other Star", "BBB", "CCC", False, 35.0, 25.0, 6.0, 8.0, 0.5, 0.30, 69.0, 50.0),
                ("H3", datetime(2026, 1, 6), "400", "Other Star", "BBB", "DDD", True, 34.0, 23.0, 5.0, 7.0, 0.5, 0.29, 67.0, 48.0),
                ("H4", datetime(2026, 1, 8), "400", "Other Star", "BBB", "EEE", False, 35.0, 24.0, 6.0, 7.0, 0.5, 0.30, 68.0, 49.0),
                ("H5", datetime(2026, 1, 10), "400", "Other Star", "BBB", "FFF", True, 35.0, 25.0, 6.0, 8.0, 0.5, 0.31, 70.0, 51.0),
                ("H1", datetime(2026, 1, 2), "500", "BBB Benefit", "BBB", "AAA", True, 22.0, 10.0, 5.0, 3.0, 0.6, 0.18, 34.0, 20.0),
                ("H2", datetime(2026, 1, 4), "500", "BBB Benefit", "BBB", "CCC", False, 23.0, 11.0, 5.0, 3.0, 0.6, 0.18, 35.0, 21.0),
                ("H3", datetime(2026, 1, 6), "500", "BBB Benefit", "BBB", "DDD", True, 22.0, 10.0, 5.0, 3.0, 0.6, 0.17, 33.0, 20.0),
                ("H4", datetime(2026, 1, 8), "500", "BBB Benefit", "BBB", "EEE", False, 23.0, 11.0, 5.0, 4.0, 0.6, 0.18, 34.0, 20.0),
                ("H5", datetime(2026, 1, 10), "500", "BBB Benefit", "BBB", "FFF", True, 22.0, 10.0, 5.0, 3.0, 0.6, 0.17, 33.0, 19.0),
                ("H6", datetime(2026, 1, 12), "500", "BBB Benefit", "BBB", "GGG", False, 33.0, 19.0, 7.0, 5.0, 0.8, 0.25, 55.0, 34.0),
                ("H7", datetime(2026, 1, 14), "500", "BBB Benefit", "BBB", "HHH", True, 32.0, 18.0, 8.0, 5.0, 0.8, 0.24, 54.0, 33.0),
            ]
            for game_id, game_date, player_id, player_name, team, opp, is_home, minutes, points, rebounds, assists, blocks, usage, touches, passes in team_b_rows:
                session.add(HistoricalGameLog(
                    game_id=game_id,
                    game_date=game_date,
                    player_id=player_id,
                    player_name=player_name,
                    team=team,
                    opponent=opp,
                    is_home=is_home,
                    minutes=minutes,
                    points=points,
                    rebounds=rebounds,
                    assists=assists,
                    steals=1.0,
                    blocks=blocks,
                    turnovers=2.0,
                    threes_made=1.0,
                    threes_attempted=3.0,
                    field_goals_made=7.0,
                    field_goals_attempted=14.0,
                    free_throws_made=3.0,
                    free_throws_attempted=4.0,
                    plus_minus=2.0,
                ))
                session.add(HistoricalAdvancedLog(
                    game_id=game_id,
                    player_id=player_id,
                    player_name=player_name,
                    usage_percentage=usage,
                    estimated_usage_percentage=usage,
                    touches=touches,
                    passes=passes,
                ))

            # beneficiary + teammate rows across active and out games
            teammate_rows = [
                ("G1", datetime(2026, 1, 1), "200", "Benefit Guy", "AAA", "BBB", True, 24.0, 12.0, 5.0, 3.0, 0.7, 0.18, 38.0, 24.0),
                ("G2", datetime(2026, 1, 3), "200", "Benefit Guy", "AAA", "CCC", False, 23.0, 11.0, 4.0, 3.0, 0.5, 0.18, 37.0, 23.0),
                ("G3", datetime(2026, 1, 5), "200", "Benefit Guy", "AAA", "DDD", True, 25.0, 13.0, 5.0, 3.0, 0.6, 0.19, 39.0, 25.0),
                ("G4", datetime(2026, 1, 7), "200", "Benefit Guy", "AAA", "EEE", False, 24.0, 12.0, 4.0, 4.0, 0.6, 0.18, 38.0, 24.0),
                ("G5", datetime(2026, 1, 9), "200", "Benefit Guy", "AAA", "FFF", True, 23.0, 11.0, 4.0, 3.0, 0.5, 0.17, 36.0, 23.0),
                ("G6", datetime(2026, 1, 11), "200", "Benefit Guy", "AAA", "GGG", False, 34.0, 20.0, 8.0, 5.0, 1.0, 0.26, 52.0, 32.0),
                ("G7", datetime(2026, 1, 13), "200", "Benefit Guy", "AAA", "HHH", True, 33.0, 18.0, 9.0, 4.0, 1.1, 0.25, 50.0, 31.0),
            ]
            for game_id, game_date, player_id, player_name, team, opp, is_home, minutes, points, rebounds, assists, blocks, usage, touches, passes in teammate_rows:
                session.add(HistoricalGameLog(
                    game_id=game_id,
                    game_date=game_date,
                    player_id=player_id,
                    player_name=player_name,
                    team=team,
                    opponent=opp,
                    is_home=is_home,
                    minutes=minutes,
                    points=points,
                    rebounds=rebounds,
                    assists=assists,
                    steals=1.0,
                    blocks=blocks,
                    turnovers=2.0,
                    threes_made=1.0,
                    threes_attempted=3.0,
                    field_goals_made=7.0,
                    field_goals_attempted=14.0,
                    free_throws_made=3.0,
                    free_throws_attempted=4.0,
                    plus_minus=2.0,
                ))
                session.add(HistoricalAdvancedLog(
                    game_id=game_id,
                    player_id=player_id,
                    player_name=player_name,
                    usage_percentage=usage,
                    estimated_usage_percentage=usage,
                    touches=touches,
                    passes=passes,
                ))

            # other teammate to prove multiple rows can exist
            for game_id, game_date, opp, is_home, minutes, points, usage in [
                ("G1", datetime(2026, 1, 1), "BBB", True, 30.0, 15.0, 0.20),
                ("G2", datetime(2026, 1, 3), "CCC", False, 31.0, 16.0, 0.21),
                ("G3", datetime(2026, 1, 5), "DDD", True, 29.0, 14.0, 0.19),
                ("G4", datetime(2026, 1, 7), "EEE", False, 30.0, 15.0, 0.20),
                ("G5", datetime(2026, 1, 9), "FFF", True, 30.0, 15.0, 0.20),
                ("G6", datetime(2026, 1, 11), "GGG", False, 28.0, 14.0, 0.18),
                ("G7", datetime(2026, 1, 13), "HHH", True, 28.0, 13.0, 0.18),
            ]:
                session.add(HistoricalGameLog(
                    game_id=game_id,
                    game_date=game_date,
                    player_id="300",
                    player_name="Neutral Guy",
                    team="AAA",
                    opponent=opp,
                    is_home=is_home,
                    minutes=minutes,
                    points=points,
                    rebounds=4.0,
                    assists=2.0,
                    steals=1.0,
                    blocks=0.3,
                    turnovers=1.0,
                    threes_made=1.0,
                    threes_attempted=2.0,
                    field_goals_made=6.0,
                    field_goals_attempted=12.0,
                    free_throws_made=2.0,
                    free_throws_attempted=2.0,
                    plus_minus=1.0,
                ))
                session.add(HistoricalAdvancedLog(
                    game_id=game_id,
                    player_id="300",
                    player_name="Neutral Guy",
                    usage_percentage=usage,
                    estimated_usage_percentage=usage,
                    touches=30.0,
                    passes=18.0,
                ))

            report = OfficialInjuryReport(
                id=1,
                season="2025-26",
                report_date=date(2026, 1, 11),
                report_time_et="1:00 PM",
                report_datetime_utc=datetime(2026, 1, 11, 18, 0, 0),
                pdf_url="https://example.com/report-1.pdf",
                pdf_sha256="deadbeef1",
                game_count=1,
                entry_count=1,
            )
            report2 = OfficialInjuryReport(
                id=2,
                season="2025-26",
                report_date=date(2026, 1, 13),
                report_time_et="1:00 PM",
                report_datetime_utc=datetime(2026, 1, 13, 18, 0, 0),
                pdf_url="https://example.com/report-2.pdf",
                pdf_sha256="deadbeef2",
                game_count=1,
                entry_count=1,
            )
            report3 = OfficialInjuryReport(
                id=3,
                season="2025-26",
                report_date=date(2026, 1, 12),
                report_time_et="1:00 PM",
                report_datetime_utc=datetime(2026, 1, 12, 18, 0, 0),
                pdf_url="https://example.com/report-3.pdf",
                pdf_sha256="deadbeef3",
                game_count=1,
                entry_count=1,
            )
            report4 = OfficialInjuryReport(
                id=4,
                season="2025-26",
                report_date=date(2026, 1, 14),
                report_time_et="1:00 PM",
                report_datetime_utc=datetime(2026, 1, 14, 18, 0, 0),
                pdf_url="https://example.com/report-4.pdf",
                pdf_sha256="deadbeef4",
                game_count=1,
                entry_count=1,
            )
            session.add_all([report, report2, report3, report4])
            session.add_all([
                OfficialInjuryReportEntry(
                    report_id=1,
                    season="2025-26",
                    report_datetime_utc=datetime(2026, 1, 11, 18, 0, 0),
                    game_date=date(2026, 1, 11),
                    matchup="AAA @ GGG",
                    team_abbreviation="AAA",
                    player_id="100",
                    player_name="Source Star",
                    current_status="OUT",
                ),
                OfficialInjuryReportEntry(
                    report_id=2,
                    season="2025-26",
                    report_datetime_utc=datetime(2026, 1, 13, 18, 0, 0),
                    game_date=date(2026, 1, 13),
                    matchup="HHH @ AAA",
                    team_abbreviation="AAA",
                    player_id="100",
                    player_name="Source Star",
                    current_status="OUT",
                ),
                OfficialInjuryReportEntry(
                    report_id=3,
                    season="2025-26",
                    report_datetime_utc=datetime(2026, 1, 12, 18, 0, 0),
                    game_date=date(2026, 1, 12),
                    matchup="BBB @ GGG",
                    team_abbreviation="BBB",
                    player_id="400",
                    player_name="Other Star",
                    current_status="OUT",
                ),
                OfficialInjuryReportEntry(
                    report_id=4,
                    season="2025-26",
                    report_datetime_utc=datetime(2026, 1, 14, 18, 0, 0),
                    game_date=date(2026, 1, 14),
                    matchup="HHH @ BBB",
                    team_abbreviation="BBB",
                    player_id="400",
                    player_name="Other Star",
                    current_status="OUT",
                ),
            ])

    def _add_override(
        self,
        *,
        team_abbreviation: str,
        player_id: str | None = None,
        player_name: str | None = None,
        include_as_source: bool = True,
        start_date: date | None = None,
        end_date: date | None = None,
        note: str | None = None,
        normalized_player_name: str | None = None,
    ) -> None:
        with self.session_scope() as session:
            session.add(AbsenceSourceOverride(
                team_abbreviation=team_abbreviation,
                player_id=player_id,
                player_name=player_name,
                normalized_player_name=normalized_player_name,
                include_as_source=include_as_source,
                start_date=start_date,
                end_date=end_date,
                note=note,
            ))

    def test_build_and_persist_absence_impact_rows(self):
        self._seed()
        with patch("analytics.absence_impact.session_scope", self.session_scope):
            result = build_absence_impact_rows(
                source_player_id="100",
                team_abbreviation="AAA",
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 1, 31, 23, 59, 59),
                min_active_games=8,
                min_out_games=2,
            )
            self.assertEqual(result.source_out_game_count, 2)
            self.assertEqual(result.source_active_game_count, 5)
            self.assertGreaterEqual(result.summary_count, 2)

            benefit = next(row for row in result.rows if row.beneficiary_player_id == "200")
            self.assertGreater(benefit.minutes_delta or 0.0, 8.0)
            self.assertGreater(benefit.usage_delta or 0.0, 0.05)
            self.assertGreater(benefit.impact_score or 0.0, 0.0)

            persisted = persist_absence_impact_rows(result)
            self.assertEqual(persisted, result.summary_count)

        with self.session_scope() as session:
            rows = session.query(AbsenceImpactSummary).all()
            self.assertEqual(len(rows), result.summary_count)
            stored = next(row for row in rows if row.beneficiary_player_id == "200")
            self.assertEqual(stored.source_player_id, "100")
            self.assertEqual(stored.team_abbreviation, "AAA")
            self.assertGreater(stored.sample_confidence or 0.0, 0.0)

    def test_select_first_pass_absence_sources_picks_one_per_team(self):
        self._seed()
        with patch("analytics.absence_impact.session_scope", self.session_scope):
            selections = select_first_pass_absence_sources(
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 1, 31, 23, 59, 59),
                min_active_games=5,
                min_out_games=2,
            )

        self.assertEqual(len(selections), 2)
        by_team = {row.team_abbreviation: row for row in selections}
        self.assertEqual(by_team["AAA"].source_player_id, "100")
        self.assertEqual(by_team["BBB"].source_player_id, "400")
        self.assertGreater(by_team["AAA"].selection_score, 0.0)
        self.assertEqual(by_team["AAA"].out_game_count, 2)

    def test_select_starter_pool_absence_sources_respects_team_tenure_and_thresholds(self):
        self._seed()
        with patch("analytics.absence_impact.session_scope", self.session_scope):
            selections = select_starter_pool_absence_sources(
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 1, 31, 23, 59, 59),
                min_active_games=5,
                min_out_games=2,
                max_sources_per_team=5,
                min_avg_minutes=24.0,
                min_start_rate=0.35,
            )

        aaa = [row for row in selections if row.team_abbreviation == "AAA"]
        bbb = [row for row in selections if row.team_abbreviation == "BBB"]
        self.assertEqual([row.source_player_id for row in aaa], ["100"])
        self.assertEqual([row.source_player_id for row in bbb], ["400"])
        self.assertTrue(all(row.tenure_end_date is not None for row in selections))

    def test_include_override_forces_thin_sample_player_into_source_pool(self):
        self._seed()
        self._add_override(
            team_abbreviation="AAA",
            player_name="Neutral Guy",
            include_as_source=True,
            note="manual include for thin-sample source selection",
        )

        with patch("analytics.absence_impact.session_scope", self.session_scope):
            selections = select_starter_pool_absence_sources(
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 1, 31, 23, 59, 59),
                min_active_games=8,
                min_out_games=2,
                max_sources_per_team=5,
                min_avg_minutes=24.0,
                min_start_rate=0.35,
            )

        aaa = [row for row in selections if row.team_abbreviation == "AAA"]
        self.assertIn("300", [row.source_player_id for row in aaa])

    def test_include_override_bypasses_stale_recency_guard(self):
        self._seed()
        self._add_override(
            team_abbreviation="AAA",
            player_id="300",
            player_name="Neutral Guy",
            include_as_source=True,
            note="manual include for stale returning source",
        )

        with patch("analytics.absence_impact.session_scope", self.session_scope):
            selections = select_starter_pool_absence_sources(
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 2, 10, 23, 59, 59),
                min_active_games=8,
                min_out_games=2,
                max_sources_per_team=5,
                min_avg_minutes=24.0,
                min_start_rate=0.35,
                max_days_since_last_team_game=10,
            )

        aaa = [row for row in selections if row.team_abbreviation == "AAA"]
        self.assertIn("300", [row.source_player_id for row in aaa])

    def test_exclude_override_suppresses_otherwise_selected_player(self):
        self._seed()
        self._add_override(
            team_abbreviation="AAA",
            player_id="100",
            player_name="Source Star",
            include_as_source=False,
            note="manual exclude for stale build run",
        )

        with patch("analytics.absence_impact.session_scope", self.session_scope):
            selections = select_starter_pool_absence_sources(
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 1, 31, 23, 59, 59),
                min_active_games=5,
                min_out_games=0,
                max_sources_per_team=1,
                min_avg_minutes=18.0,
                min_start_rate=0.0,
            )

        by_team = {row.team_abbreviation: row for row in selections}
        self.assertIn("AAA", by_team)
        self.assertNotEqual(by_team["AAA"].source_player_id, "100")
        self.assertEqual(by_team["BBB"].source_player_id, "400")

    def test_override_date_window_is_respected(self):
        self._seed()
        with self.session_scope() as session:
            session.add(HistoricalGameLog(
                game_id="J1",
                game_date=datetime(2026, 1, 25),
                player_id="900",
                player_name="Late Window Guard",
                team="CCC",
                opponent="DDD",
                is_home=True,
                minutes=10.0,
                points=4.0,
                rebounds=1.0,
                assists=1.0,
                steals=0.0,
                blocks=0.0,
                turnovers=1.0,
                threes_made=1.0,
                threes_attempted=2.0,
                field_goals_made=1.0,
                field_goals_attempted=3.0,
                free_throws_made=1.0,
                free_throws_attempted=2.0,
                plus_minus=0.0,
            ))
        self._add_override(
            team_abbreviation="AAA",
            player_id="300",
            player_name="Neutral Guy",
            include_as_source=True,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 20),
            note="temporary include",
        )

        with patch("analytics.absence_impact.session_scope", self.session_scope):
            early_selections = select_starter_pool_absence_sources(
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 1, 15, 23, 59, 59),
                min_active_games=8,
                min_out_games=2,
                max_sources_per_team=5,
                min_avg_minutes=24.0,
                min_start_rate=0.35,
            )
            late_selections = select_starter_pool_absence_sources(
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 1, 31, 23, 59, 59),
                min_active_games=8,
                min_out_games=2,
                max_sources_per_team=5,
                min_avg_minutes=24.0,
                min_start_rate=0.35,
            )

        self.assertIn("300", [row.source_player_id for row in early_selections if row.team_abbreviation == "AAA"])
        self.assertNotIn("300", [row.source_player_id for row in late_selections if row.team_abbreviation == "AAA"])

    def test_build_and_persist_first_pass_absence_impact_batch(self):
        self._seed()
        with patch("analytics.absence_impact.session_scope", self.session_scope):
            batch = build_and_persist_first_pass_absence_impact_batch(
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 1, 31, 23, 59, 59),
                min_active_games=5,
                min_out_games=2,
            )

        self.assertEqual(batch.source_count, 2)
        self.assertTrue(batch.persisted)
        self.assertGreater(batch.summary_count, 0)
        self.assertEqual(len(batch.results), 2)
        teams = {result.team_abbreviation for result in batch.results}
        self.assertEqual(teams, {"AAA", "BBB"})

        with self.session_scope() as session:
            stored_rows = session.query(AbsenceImpactSummary).all()
            self.assertEqual(len(stored_rows), batch.summary_count)
            self.assertTrue(any(row.source_player_id == "100" for row in stored_rows))
            self.assertTrue(any(row.source_player_id == "400" for row in stored_rows))

    def test_build_and_persist_starter_pool_batch_uses_same_clean_sources(self):
        self._seed()
        with patch("analytics.absence_impact.session_scope", self.session_scope):
            batch = build_and_persist_starter_pool_absence_impact_batch(
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 1, 31, 23, 59, 59),
                min_active_games=5,
                min_out_games=2,
                selection_min_out_games=0,
                max_sources_per_team=1,
                min_avg_minutes=24.0,
                min_start_rate=0.35,
            )

        self.assertEqual(batch.source_count, 2)
        self.assertTrue(batch.persisted)
        self.assertEqual({row.source_player_id for row in batch.selections}, {"100", "400"})


if __name__ == "__main__":
    unittest.main()
