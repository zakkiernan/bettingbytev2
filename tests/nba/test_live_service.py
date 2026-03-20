from __future__ import annotations

import json
import unittest
from contextlib import contextmanager
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from analytics.live_model import compute_game_pace, generate_alerts, project_live_player
from api.main import app
from database.db import Base, get_db
from database.models import Game, LiveGameSnapshot, LivePlayerSnapshot, StatsSignalSnapshot, Team


class LiveModelTests(unittest.TestCase):
    def test_project_live_player_uses_live_rate_and_foul_trouble_discount(self):
        game_snapshot = LiveGameSnapshot(
            game_id="G1",
            home_team_id="HOME",
            away_team_id="AWAY",
            home_team_score=60,
            away_team_score=58,
            period=3,
            game_clock="PT06M00.00S",
            game_status=2,
            status_text="Q3",
            captured_at=datetime(2026, 3, 19, 20, 30, 0),
        )
        player_snapshot = LivePlayerSnapshot(
            game_id="G1",
            player_id="P1",
            player_name="Test Player",
            team_id="HOME",
            minutes=24.0,
            points=20.0,
            rebounds=5.0,
            assists=4.0,
            threes_made=3.0,
            fouls=4.0,
            on_court=True,
            starter=True,
            captured_at=datetime(2026, 3, 19, 20, 30, 0),
        )

        pace = compute_game_pace(game_snapshot, expected_pace=100.0)
        projection = project_live_player(
            pregame_projection=28.0,
            pregame_line=27.5,
            stat_type="points",
            player_snapshot=player_snapshot,
            game_snapshot=game_snapshot,
            expected_pace=100.0,
        )

        self.assertAlmostEqual(pace.current_pace, 84.29, places=2)
        self.assertAlmostEqual(projection.pace_projection, 32.64, places=2)
        self.assertAlmostEqual(projection.live_projection, 30.32, places=2)
        self.assertAlmostEqual(projection.live_edge, 2.82, places=2)

    def test_generate_alerts_emits_hot_start_edge_and_pace_shift(self):
        projections = [
            project_live_player(
                pregame_projection=24.0,
                pregame_line=24.5,
                stat_type="points",
                player_snapshot=LivePlayerSnapshot(
                    game_id="G1",
                    player_id="P1",
                    player_name="Heat Check",
                    team_id="HOME",
                    minutes=10.0,
                    points=10.0,
                    rebounds=2.0,
                    assists=1.0,
                    threes_made=2.0,
                    fouls=1.0,
                    on_court=True,
                    starter=True,
                    captured_at=datetime(2026, 3, 19, 19, 10, 0),
                ),
                game_snapshot=LiveGameSnapshot(
                    game_id="G1",
                    home_team_id="HOME",
                    away_team_id="AWAY",
                    home_team_score=36,
                    away_team_score=34,
                    period=1,
                    game_clock="PT02M00.00S",
                    game_status=2,
                    status_text="Q1",
                    captured_at=datetime(2026, 3, 19, 19, 10, 0),
                ),
                expected_pace=98.0,
            )
        ]
        projections[0].team_abbreviation = "BOS"

        alerts = generate_alerts(
            projections,
            pregame_projections={"P1:points": 24.0},
            pace=compute_game_pace(
                LiveGameSnapshot(
                    game_id="G1",
                    home_team_id="HOME",
                    away_team_id="AWAY",
                    home_team_score=36,
                    away_team_score=34,
                    period=1,
                    game_clock="PT02M00.00S",
                    game_status=2,
                    status_text="Q1",
                    captured_at=datetime(2026, 3, 19, 19, 10, 0),
                ),
                expected_pace=98.0,
            ),
        )

        alert_types = {alert["type"] for alert in alerts}
        self.assertIn("hot_start", alert_types)
        self.assertIn("edge_emerged", alert_types)
        self.assertIn("pace_shift", alert_types)


class LiveRouteTests(unittest.TestCase):
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

        @contextmanager
        def session_scope():
            session = self.SessionLocal()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        self.session_scope = session_scope

        def override_get_db():
            with self.session_scope() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_live_active_returns_empty_list_when_no_active_games(self):
        response = self.client.get("/api/live/active")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_live_routes_return_real_snapshot_payload(self):
        created_at = datetime(2026, 3, 19, 19, 45, 0)

        with self.session_scope() as session:
            session.add_all(
                [
                    Team(team_id="HOME", abbreviation="BOS", full_name="Boston Celtics", city="Boston", nickname="Celtics"),
                    Team(team_id="AWAY", abbreviation="MIA", full_name="Miami Heat", city="Miami", nickname="Heat"),
                    Game(
                        game_id="G1",
                        season="2025-26",
                        game_date=datetime(2026, 3, 19, 0, 0, 0),
                        game_time_utc=datetime(2026, 3, 19, 23, 0, 0),
                        home_team_id="HOME",
                        away_team_id="AWAY",
                        home_team_abbreviation="BOS",
                        away_team_abbreviation="MIA",
                        game_status=2,
                        status_text="In Progress",
                    ),
                    LiveGameSnapshot(
                        game_id="G1",
                        home_team_id="HOME",
                        away_team_id="AWAY",
                        home_team_score=54,
                        away_team_score=48,
                        period=2,
                        game_clock="PT04M32.00S",
                        game_status=2,
                        status_text="Q2",
                        captured_at=created_at,
                    ),
                    LivePlayerSnapshot(
                        game_id="G1",
                        player_id="P1",
                        player_name="Jayson Tatum",
                        team_id="HOME",
                        minutes=18.0,
                        points=14.0,
                        rebounds=5.0,
                        assists=3.0,
                        steals=1.0,
                        blocks=0.0,
                        turnovers=1.0,
                        field_goals_made=5.0,
                        field_goals_attempted=11.0,
                        threes_made=2.0,
                        threes_attempted=5.0,
                        free_throws_made=2.0,
                        free_throws_attempted=2.0,
                        fouls=1.0,
                        plus_minus=7.0,
                        on_court=True,
                        starter=True,
                        captured_at=created_at,
                    ),
                    StatsSignalSnapshot(
                        game_id="G1",
                        player_id="P1",
                        player_name="Jayson Tatum",
                        team_abbreviation="BOS",
                        opponent_abbreviation="MIA",
                        stat_type="points",
                        snapshot_phase="current",
                        line=28.5,
                        over_odds=-110,
                        under_odds=-110,
                        projected_value=29.0,
                        edge_over=0.5,
                        edge_under=-0.5,
                        over_probability=0.52,
                        under_probability=0.48,
                        confidence=0.63,
                        recommended_side=None,
                        recent_hit_rate=0.5,
                        recent_games_count=10,
                        key_factor="Pace support",
                        is_ready=True,
                        readiness_status="ready",
                        using_fallback=False,
                        readiness_json=json.dumps({"status": "ready"}),
                        breakdown_json=json.dumps({}),
                        opportunity_json=json.dumps({}),
                        features_json=json.dumps({"team_pace": 102.0, "opponent_pace": 99.0}),
                        source_prop_captured_at=created_at,
                        source_context_captured_at=created_at,
                        source_injury_report_at=created_at,
                        created_at=created_at,
                    ),
                ]
            )

        active_response = self.client.get("/api/live/active")
        self.assertEqual(active_response.status_code, 200)
        active_payload = active_response.json()
        self.assertEqual(len(active_payload), 1)
        self.assertEqual(active_payload[0]["game_id"], "G1")
        self.assertEqual(active_payload[0]["home_team"]["abbreviation"], "BOS")
        self.assertEqual(active_payload[0]["game_clock"], "4:32")

        detail_response = self.client.get("/api/live/G1")
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()

        self.assertEqual(detail_payload["game_id"], "G1")
        self.assertEqual(detail_payload["pace"]["expected_pace"], 100.5)
        self.assertEqual(len(detail_payload["players"]), 1)
        self.assertEqual(detail_payload["players"][0]["player_name"], "Jayson Tatum")
        self.assertGreater(detail_payload["players"][0]["live_projection"], 0.0)
        self.assertGreaterEqual(detail_payload["live_edge_count"], 0)


if __name__ == "__main__":
    unittest.main()
