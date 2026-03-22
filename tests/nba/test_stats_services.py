from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.services.nba import game_stats_service, player_stats_service
from database.db import Base
from database.models import Game, Player, PlayerOnOffStats, ShotChartDetail, WinProbabilityEntry


class StatsServiceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            class_=Session,
        )
        Base.metadata.create_all(self.engine)

    def tearDown(self) -> None:
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

    def test_game_win_probability_converts_decimal_probabilities_to_percentage_points(self) -> None:
        with self.session_scope() as session:
            session.add(
                Game(
                    game_id="G1",
                    season="2025-26",
                    game_date=datetime(2026, 3, 20, 0, 0, 0),
                    game_time_utc=datetime(2026, 3, 20, 23, 0, 0),
                    home_team_abbreviation="BOS",
                    away_team_abbreviation="NYK",
                )
            )
            session.add_all(
                [
                    WinProbabilityEntry(
                        game_id="G1",
                        event_num=1,
                        home_pct=0.25,
                        visitor_pct=0.75,
                        home_pts=10,
                        visitor_pts=12,
                        period=1,
                        seconds_remaining=660.0,
                    ),
                    WinProbabilityEntry(
                        game_id="G1",
                        event_num=2,
                        home_pct=None,
                        visitor_pct=None,
                        home_pts=12,
                        visitor_pts=12,
                        period=1,
                        seconds_remaining=600.0,
                    ),
                ]
            )

        with self.session_scope() as session:
            response = game_stats_service.get_game_win_probability(session, "G1")

        assert response is not None
        self.assertEqual(response.points[0].home_pct, 25.0)
        self.assertEqual(response.points[0].visitor_pct, 75.0)
        self.assertEqual(response.points[1].home_pct, 50.0)
        self.assertEqual(response.points[1].visitor_pct, 50.0)

    def test_player_shot_chart_last_n_uses_game_date_not_row_created_at(self) -> None:
        with self.session_scope() as session:
            session.add(
                Player(
                    player_id="P1",
                    full_name="Test Shooter",
                    first_name="Test",
                    last_name="Shooter",
                )
            )
            session.add_all(
                [
                    Game(
                        game_id="OLD",
                        season="2025-26",
                        game_date=datetime(2026, 3, 10, 0, 0, 0),
                        game_time_utc=datetime(2026, 3, 10, 23, 0, 0),
                        home_team_abbreviation="BOS",
                        away_team_abbreviation="NYK",
                    ),
                    Game(
                        game_id="NEW",
                        season="2025-26",
                        game_date=datetime(2026, 3, 12, 0, 0, 0),
                        game_time_utc=datetime(2026, 3, 12, 23, 0, 0),
                        home_team_abbreviation="BOS",
                        away_team_abbreviation="NYK",
                    ),
                ]
            )
            session.add_all(
                [
                    ShotChartDetail(
                        game_id="OLD",
                        player_id="P1",
                        player_name="Test Shooter",
                        team_id="BOS",
                        loc_x=10.0,
                        loc_y=20.0,
                        shot_made_flag=True,
                        period=1,
                        minutes_remaining=11,
                        seconds_remaining=30,
                        created_at=datetime(2026, 3, 15, 12, 0, 0),
                    ),
                    ShotChartDetail(
                        game_id="NEW",
                        player_id="P1",
                        player_name="Test Shooter",
                        team_id="BOS",
                        loc_x=15.0,
                        loc_y=25.0,
                        shot_made_flag=False,
                        period=1,
                        minutes_remaining=10,
                        seconds_remaining=45,
                        created_at=datetime(2026, 3, 13, 12, 0, 0),
                    ),
                ]
            )

        with self.session_scope() as session:
            response = player_stats_service.get_player_shot_chart(session, "P1", last_n=1)

        assert response is not None
        self.assertEqual(response.total_shots, 1)
        self.assertEqual({shot.game_id for shot in response.shots}, {"NEW"})

    def test_player_on_off_normalizes_court_status_values(self) -> None:
        with self.session_scope() as session:
            session.add(
                Player(
                    player_id="P1",
                    full_name="Test Guard",
                    first_name="Test",
                    last_name="Guard",
                )
            )
            session.add_all(
                [
                    PlayerOnOffStats(
                        player_id="P1",
                        player_name="Test Guard",
                        team_id="BOS",
                        season="2025-26",
                        court_status="On",
                        gp=50,
                        off_rating=118.2,
                    ),
                    PlayerOnOffStats(
                        player_id="P1",
                        player_name="Test Guard",
                        team_id="BOS",
                        season="2025-26",
                        court_status="OFF",
                        gp=50,
                        off_rating=111.0,
                    ),
                ]
            )

        with self.session_scope() as session:
            response = player_stats_service.get_player_on_off(session, "P1", season="2025-26")

        assert response is not None
        self.assertEqual({split.court_status for split in response.splits}, {"on", "off"})


if __name__ == "__main__":
    unittest.main()
