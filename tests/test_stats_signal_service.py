from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from analytics.features_pregame import PregamePointsFeatures
from api.schemas.board import SignalReadiness
from api.schemas.detail import FeatureSnapshot, InjuryEntry, OpportunityContext, PointsBreakdown
from api.services.stats_signal_service import (
    _build_signal_readiness,
    build_signal_run_health,
    build_stats_signal_profile,
    get_player_signal_history,
    get_historical_pregame_lines,
    persist_current_signal_snapshots,
    repair_current_signal_snapshots,
)
from database.db import Base
from database.models import Game, OddsSnapshot, PlayerPropSnapshot, StatsSignalSnapshot


class StatsSignalProfileTests(unittest.TestCase):
    def build_feature(self, **overrides) -> PregamePointsFeatures:
        base = PregamePointsFeatures(
            game_id="002TEST",
            player_id="123",
            player_name="Test Player",
            line=24.5,
            over_odds=-110,
            under_odds=-110,
            captured_at=datetime(2026, 3, 9, 12, 0, 0),
            game_date=datetime(2026, 3, 9, 19, 0, 0),
            team_abbreviation="BOS",
            opponent_abbreviation="NYK",
            is_home=True,
            days_rest=2,
            back_to_back=False,
            sample_size=15,
            last5_count=5,
            last10_count=10,
            season_points_avg=24.0,
            last10_points_avg=25.4,
            last5_points_avg=27.5,
            last10_points_median=25.0,
            last10_points_std=4.1,
            season_minutes_avg=34.0,
            last10_minutes_avg=35.5,
            last5_minutes_avg=36.0,
            last10_minutes_std=2.0,
            rotation_sample_size=8,
            season_rotation_minutes_avg=34.5,
            last10_rotation_minutes_avg=36.0,
            last5_rotation_minutes_avg=36.4,
            last10_rotation_minutes_std=1.5,
            season_stint_count_avg=3.0,
            last10_stint_count_avg=3.0,
            last5_stint_count_avg=2.8,
            season_started_rate=0.9,
            last10_started_rate=1.0,
            last5_started_rate=1.0,
            season_closed_rate=0.8,
            last10_closed_rate=0.8,
            last5_closed_rate=0.8,
            season_usage_pct=0.28,
            last10_usage_pct=0.295,
            last5_usage_pct=0.302,
            season_est_usage_pct=0.275,
            last10_est_usage_pct=0.288,
            last5_est_usage_pct=0.296,
            season_touches=58.0,
            last10_touches=61.0,
            last5_touches=63.0,
            season_passes=42.0,
            last10_passes=44.0,
            last5_passes=45.0,
            season_off_rating=116.0,
            last10_off_rating=119.0,
            last5_off_rating=120.0,
            team_pace=100.5,
            opponent_def_rating=112.0,
            opponent_pace=99.4,
            opponent_points_allowed=111.0,
            opponent_fg_pct_allowed=0.46,
            opponent_3pt_pct_allowed=0.36,
            league_avg_def_rating=114.5,
            league_avg_pace=99.0,
            league_avg_opponent_points=113.0,
            expected_start=True,
            starter_confidence=0.9,
            projected_available=True,
            official_available=True,
            late_scratch_risk=0.05,
            teammate_out_count_top7=2.0,
            teammate_out_count_top9=2.0,
            missing_high_usage_teammates=1.0,
            vacated_minutes_proxy=18.0,
            vacated_usage_proxy=0.04,
            role_replacement_minutes_proxy=10.0,
            role_replacement_usage_proxy=0.02,
            role_replacement_touches_proxy=10.0,
            role_replacement_passes_proxy=5.0,
            pregame_context_confidence=0.85,
            context_source="pregame_context",
        )
        for key, value in overrides.items():
            setattr(base, key, value)
        return base

    def test_profile_recommends_over_for_strong_stats_context_signal(self):
        recent_logs = [SimpleNamespace(points=score) for score in (30, 29, 28, 26, 31, 27, 25, 32, 24, 28)]

        profile = build_stats_signal_profile(
            self.build_feature(),
            recent_logs=recent_logs,
            injury_entries=[],
        )

        self.assertGreater(profile.projected_value, 24.5)
        self.assertEqual(profile.recommended_side, "OVER")
        self.assertGreater(profile.confidence, 0.55)
        self.assertIsNotNone(profile.recent_hit_rate)
        self.assertEqual(profile.feature_snapshot.context_source, "pregame_context")

    def test_profile_suppresses_pick_when_player_is_officially_out(self):
        recent_logs = [SimpleNamespace(points=score) for score in (30, 29, 28, 26, 31)]
        injury_entries = [
            InjuryEntry(
                player_name="Test Player",
                team_abbreviation="BOS",
                current_status="Out",
                reason="Rest",
            )
        ]

        profile = build_stats_signal_profile(
            self.build_feature(
                official_available=False,
                projected_available=False,
                late_scratch_risk=1.0,
                official_injury_status="OUT",
                context_source="official_injury_player",
            ),
            recent_logs=recent_logs,
            injury_entries=injury_entries,
        )

        self.assertIsNone(profile.recommended_side)
        self.assertLess(profile.opportunity.availability_modifier, 0.2)
        self.assertEqual(profile.opportunity.injury_entries[0].current_status, "Out")


class HistoricalLineLookupTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)
        Base.metadata.create_all(
            self.engine,
            tables=[PlayerPropSnapshot.__table__, OddsSnapshot.__table__],
        )

    def tearDown(self):
        Base.metadata.drop_all(
            self.engine,
            tables=[OddsSnapshot.__table__, PlayerPropSnapshot.__table__],
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

    def test_lookup_prefers_odds_snapshot_and_falls_back_to_prop_snapshot(self):
        with self.session_scope() as session:
            session.add(
                OddsSnapshot(
                    game_id="G1",
                    player_id="123",
                    player_name="Test Player",
                    stat_type="points",
                    line=24.5,
                    over_odds=-110,
                    under_odds=-110,
                    source="fanduel",
                    market_phase="pregame",
                    captured_at=datetime(2026, 3, 9, 17, 30, 0),
                )
            )
            session.add(
                PlayerPropSnapshot(
                    game_id="G2",
                    player_id="123",
                    player_name="Test Player",
                    team="BOS",
                    opponent="NYK",
                    stat_type="points",
                    line=25.5,
                    over_odds=-110,
                    under_odds=-110,
                    is_live=False,
                    snapshot_phase="current",
                    captured_at=datetime(2026, 3, 9, 18, 0, 0),
                )
            )

        with self.session_scope() as session:
            lines = get_historical_pregame_lines(
                session,
                player_id="123",
                stat_type="points",
                game_ids=["G1", "G2"],
            )

        self.assertEqual(lines["G1"], 24.5)
        self.assertEqual(lines["G2"], 25.5)


class SignalReadinessTests(unittest.TestCase):
    def test_readiness_blocks_fallback_and_small_sample_inside_pregame_window(self):
        snapshot = PlayerPropSnapshot(
            id=1,
            game_id="G1",
            player_id="123",
            player_name="Test Player",
            team="BOS",
            opponent="NYK",
            stat_type="points",
            line=24.5,
            over_odds=-110,
            under_odds=-110,
            is_live=False,
            snapshot_phase="current",
            captured_at=datetime(2026, 3, 16, 18, 0, 0),
        )
        game = SimpleNamespace(game_time_utc=datetime(2026, 3, 16, 20, 0, 0))

        readiness = _build_signal_readiness(
            snapshot=snapshot,
            game=game,
            feature=None,
            recent_games_count=4,
            latest_injury_report_at=None,
            evaluation_time=datetime(2026, 3, 16, 18, 30, 0),
        )

        self.assertFalse(readiness.is_ready)
        self.assertEqual(readiness.status, "blocked")
        self.assertTrue(readiness.using_fallback)
        self.assertIn("Pregame feature build is unavailable for this snapshot", readiness.blockers)
        self.assertIn("Only 4 recent games are available", readiness.blockers)
        self.assertIn("Official injury report is missing inside the pregame window", readiness.blockers)

    def test_readiness_marks_low_confidence_context_as_limited(self):
        snapshot = PlayerPropSnapshot(
            id=1,
            game_id="G1",
            player_id="123",
            player_name="Test Player",
            team="BOS",
            opponent="NYK",
            stat_type="points",
            line=24.5,
            over_odds=-110,
            under_odds=-110,
            is_live=False,
            snapshot_phase="current",
            captured_at=datetime(2026, 3, 16, 18, 0, 0),
        )
        feature = StatsSignalProfileTests().build_feature(
            context_source="official_injury_team",
            pregame_context_confidence=0.40,
        )

        readiness = _build_signal_readiness(
            snapshot=snapshot,
            game=SimpleNamespace(game_time_utc=datetime(2026, 3, 16, 22, 0, 0)),
            feature=feature,
            recent_games_count=10,
            latest_injury_report_at=datetime(2026, 3, 16, 17, 45, 0),
            evaluation_time=datetime(2026, 3, 16, 18, 20, 0),
        )

        self.assertTrue(readiness.is_ready)
        self.assertEqual(readiness.status, "limited")
        self.assertIn("Signal is leaning on official injury team context", readiness.warnings)
        self.assertIn("Pregame context confidence is only 0.40", readiness.warnings)


class SignalRunHealthTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)
        Base.metadata.create_all(
            self.engine,
            tables=[PlayerPropSnapshot.__table__, StatsSignalSnapshot.__table__],
        )

    def tearDown(self):
        Base.metadata.drop_all(
            self.engine,
            tables=[StatsSignalSnapshot.__table__, PlayerPropSnapshot.__table__],
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

    def test_signal_run_health_summarizes_readiness_counts(self):
        with self.session_scope() as session:
            session.add(
                PlayerPropSnapshot(
                    game_id="G1",
                    player_id="123",
                    player_name="Test Player",
                    team="BOS",
                    opponent="NYK",
                    stat_type="points",
                    line=24.5,
                    over_odds=-110,
                    under_odds=-110,
                    is_live=False,
                    snapshot_phase="current",
                    captured_at=datetime(2026, 3, 16, 18, 0, 0),
                )
            )
            session.add(
                StatsSignalSnapshot(
                    game_id="G1",
                    player_id="123",
                    player_name="Test Player",
                    team_abbreviation="BOS",
                    opponent_abbreviation="NYK",
                    stat_type="points",
                    snapshot_phase="current",
                    line=24.5,
                    over_odds=-110,
                    under_odds=-110,
                    projected_value=25.0,
                    edge_over=0.5,
                    edge_under=-0.5,
                    over_probability=0.52,
                    under_probability=0.48,
                    confidence=0.6,
                    recommended_side=None,
                    recent_hit_rate=0.5,
                    recent_games_count=10,
                    key_factor="Earlier audit",
                    is_ready=True,
                    readiness_status="ready",
                    using_fallback=False,
                    readiness_json=SignalReadiness(status="ready", is_ready=True).model_dump_json(),
                    breakdown_json=PointsBreakdown(base_scoring=25.0, projected_points=25.0).model_dump_json(),
                    opportunity_json=OpportunityContext(expected_minutes=34.0).model_dump_json(),
                    features_json=FeatureSnapshot(team_abbreviation="BOS", opponent_abbreviation="NYK", is_home=True).model_dump_json(),
                    source_prop_captured_at=datetime(2026, 3, 16, 17, 50, 0),
                    created_at=datetime(2026, 3, 16, 17, 55, 0),
                )
            )

        ready_row = SimpleNamespace(
            recommended_side="OVER",
            readiness=SignalReadiness(status="ready", is_ready=True),
        )
        blocked_row = SimpleNamespace(
            recommended_side=None,
            readiness=SignalReadiness(status="blocked", is_ready=False, using_fallback=True),
        )

        class _FakeCard:
            def __init__(self, row):
                self._row = row

            def to_board_row(self):
                return self._row

        with self.session_scope() as session:
            with patch(
                "api.services.stats_signal_service._build_cards_from_snapshots",
                return_value=[_FakeCard(ready_row), _FakeCard(blocked_row)],
            ):
                health = build_signal_run_health(session, ["G1"])

        self.assertEqual(health.signals_generated, 2)
        self.assertEqual(health.signals_with_recommendation, 1)
        self.assertEqual(health.signals_ready, 1)
        self.assertEqual(health.signals_blocked, 1)
        self.assertEqual(health.signals_using_fallback, 1)
        self.assertEqual(health.latest_persisted_at, datetime(2026, 3, 16, 17, 55, 0))
        self.assertEqual(health.latest_audit_source_prop_captured_at, datetime(2026, 3, 16, 17, 50, 0))
        self.assertEqual(health.audit_lag_minutes, 10)


class SignalSnapshotPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)
        Base.metadata.create_all(
            self.engine,
            tables=[StatsSignalSnapshot.__table__],
        )

    def tearDown(self):
        Base.metadata.drop_all(
            self.engine,
            tables=[StatsSignalSnapshot.__table__],
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

    def test_persist_current_signal_snapshots_writes_audit_rows(self):
        snapshot = PlayerPropSnapshot(
            id=11,
            game_id="G1",
            player_id="123",
            player_name="Test Player",
            team="BOS",
            opponent="NYK",
            stat_type="points",
            line=24.5,
            over_odds=-110,
            under_odds=-110,
            is_live=False,
            snapshot_phase="current",
            captured_at=datetime(2026, 3, 16, 18, 0, 0),
        )
        fake_card = SimpleNamespace(
            snapshot=snapshot,
            profile=SimpleNamespace(
                projected_value=26.2,
                edge_over=1.7,
                edge_under=-1.7,
                over_probability=0.61,
                under_probability=0.39,
                confidence=0.66,
                recommended_side="OVER",
                recent_hit_rate=0.7,
                recent_games_count=10,
                key_factor="Recent form is supportive",
                readiness=SignalReadiness(
                    is_ready=True,
                    status="ready",
                    blockers=[],
                    warnings=[],
                    line_age_minutes=0,
                    minutes_to_tip=90,
                    using_fallback=False,
                ),
                breakdown=PointsBreakdown(
                    base_scoring=24.8,
                    recent_form_adjustment=0.7,
                    minutes_adjustment=0.2,
                    usage_adjustment=0.3,
                    efficiency_adjustment=0.1,
                    opponent_adjustment=0.0,
                    pace_adjustment=0.0,
                    context_adjustment=0.1,
                    expected_minutes=35.0,
                    expected_usage_pct=0.29,
                    points_per_minute=0.75,
                    projected_points=26.2,
                ),
                opportunity=OpportunityContext(
                    expected_minutes=35.0,
                    season_minutes_avg=34.0,
                    expected_usage_pct=0.29,
                    expected_start_rate=1.0,
                    expected_close_rate=0.8,
                    role_stability=0.8,
                    opportunity_score=0.82,
                    opportunity_confidence=0.77,
                    availability_modifier=1.0,
                    vacated_minutes_bonus=0.0,
                    vacated_usage_bonus=0.0,
                    injury_entries=[],
                ),
                feature_snapshot=FeatureSnapshot(
                    team_abbreviation="BOS",
                    opponent_abbreviation="NYK",
                    is_home=True,
                    days_rest=1,
                    back_to_back=False,
                    sample_size=10,
                    season_points_avg=24.0,
                    last10_points_avg=25.0,
                    last5_points_avg=26.0,
                    season_minutes_avg=34.0,
                    last10_minutes_avg=35.0,
                    last5_minutes_avg=35.5,
                    season_usage_pct=0.28,
                    opponent_def_rating=112.0,
                    opponent_pace=99.0,
                    team_pace=100.0,
                    context_source="pregame_context",
                ),
                source_context_captured_at=datetime(2026, 3, 16, 18, 0, 0),
                source_injury_report_at=datetime(2026, 3, 16, 17, 45, 0),
            ),
        )

        with patch("api.services.stats_signal_service.session_scope", self.session_scope), patch(
            "api.services.stats_signal_service._load_current_snapshots",
            return_value=[snapshot],
        ), patch(
            "api.services.stats_signal_service._build_cards_from_snapshots",
            return_value=[fake_card],
        ):
            metrics = persist_current_signal_snapshots()

        self.assertEqual(metrics["signal_snapshots"], 1)
        self.assertEqual(metrics["signal_recommendations"], 1)

        with self.session_scope() as session:
            row = session.query(StatsSignalSnapshot).one()

        self.assertEqual(row.player_id, "123")
        self.assertEqual(row.readiness_status, "ready")
        self.assertEqual(row.snapshot_phase, "current")
        self.assertEqual(row.source_injury_report_at, datetime(2026, 3, 16, 17, 45, 0))


class SignalSnapshotRepairTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)
        Base.metadata.create_all(
            self.engine,
            tables=[StatsSignalSnapshot.__table__],
        )

    def tearDown(self):
        Base.metadata.drop_all(
            self.engine,
            tables=[StatsSignalSnapshot.__table__],
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

    def _fake_card(self, snapshot: PlayerPropSnapshot, *, created_context_at: datetime | None = None):
        return SimpleNamespace(
            snapshot=snapshot,
            profile=SimpleNamespace(
                projected_value=26.2,
                edge_over=1.7,
                edge_under=-1.7,
                over_probability=0.61,
                under_probability=0.39,
                confidence=0.66,
                recommended_side="OVER",
                recent_hit_rate=0.7,
                recent_games_count=10,
                key_factor="Recent form is supportive",
                readiness=SignalReadiness(
                    is_ready=True,
                    status="ready",
                    blockers=[],
                    warnings=[],
                    line_age_minutes=0,
                    minutes_to_tip=90,
                    using_fallback=False,
                ),
                breakdown=PointsBreakdown(
                    base_scoring=24.8,
                    recent_form_adjustment=0.7,
                    minutes_adjustment=0.2,
                    usage_adjustment=0.3,
                    efficiency_adjustment=0.1,
                    opponent_adjustment=0.0,
                    pace_adjustment=0.0,
                    context_adjustment=0.1,
                    expected_minutes=35.0,
                    expected_usage_pct=0.29,
                    points_per_minute=0.75,
                    projected_points=26.2,
                ),
                opportunity=OpportunityContext(
                    expected_minutes=35.0,
                    season_minutes_avg=34.0,
                    expected_usage_pct=0.29,
                    expected_start_rate=1.0,
                    expected_close_rate=0.8,
                    role_stability=0.8,
                    opportunity_score=0.82,
                    opportunity_confidence=0.77,
                    availability_modifier=1.0,
                    vacated_minutes_bonus=0.0,
                    vacated_usage_bonus=0.0,
                    injury_entries=[],
                ),
                feature_snapshot=FeatureSnapshot(
                    team_abbreviation="BOS",
                    opponent_abbreviation="NYK",
                    is_home=True,
                    days_rest=1,
                    back_to_back=False,
                    sample_size=10,
                    season_points_avg=24.0,
                    last10_points_avg=25.0,
                    last5_points_avg=26.0,
                    season_minutes_avg=34.0,
                    last10_minutes_avg=35.0,
                    last5_minutes_avg=35.5,
                    season_usage_pct=0.28,
                    opponent_def_rating=112.0,
                    opponent_pace=99.0,
                    team_pace=100.0,
                    context_source="pregame_context",
                ),
                source_context_captured_at=created_context_at,
                source_injury_report_at=datetime(2026, 3, 16, 17, 45, 0),
            ),
        )

    def test_repair_current_signal_snapshots_skips_when_audit_is_current(self):
        snapshot = PlayerPropSnapshot(
            id=11,
            game_id="G1",
            player_id="123",
            player_name="Test Player",
            team="BOS",
            opponent="NYK",
            stat_type="points",
            line=24.5,
            over_odds=-110,
            under_odds=-110,
            is_live=False,
            snapshot_phase="current",
            captured_at=datetime(2026, 3, 16, 18, 0, 0),
        )

        with self.session_scope() as session:
            session.add(
                StatsSignalSnapshot(
                    game_id="G1",
                    player_id="123",
                    player_name="Test Player",
                    team_abbreviation="BOS",
                    opponent_abbreviation="NYK",
                    stat_type="points",
                    snapshot_phase="current",
                    line=24.5,
                    over_odds=-110,
                    under_odds=-110,
                    projected_value=25.0,
                    edge_over=0.5,
                    edge_under=-0.5,
                    over_probability=0.52,
                    under_probability=0.48,
                    confidence=0.6,
                    recommended_side=None,
                    recent_hit_rate=0.5,
                    recent_games_count=10,
                    key_factor="Current audit",
                    is_ready=True,
                    readiness_status="ready",
                    using_fallback=False,
                    readiness_json=SignalReadiness(status="ready", is_ready=True).model_dump_json(),
                    breakdown_json=PointsBreakdown(base_scoring=25.0, projected_points=25.0).model_dump_json(),
                    opportunity_json=OpportunityContext(expected_minutes=34.0).model_dump_json(),
                    features_json=FeatureSnapshot(team_abbreviation="BOS", opponent_abbreviation="NYK", is_home=True).model_dump_json(),
                    source_prop_captured_at=datetime(2026, 3, 16, 18, 0, 0),
                    created_at=datetime(2026, 3, 16, 18, 5, 0),
                )
            )

        with patch("api.services.stats_signal_service.session_scope", self.session_scope), patch(
            "api.services.stats_signal_service._load_current_snapshots",
            return_value=[snapshot],
        ):
            metrics = repair_current_signal_snapshots()

        self.assertEqual(metrics["repair_performed"], 0)
        self.assertEqual(metrics["repair_reason"], "up_to_date")

    def test_repair_current_signal_snapshots_replays_when_audit_is_stale(self):
        snapshot = PlayerPropSnapshot(
            id=11,
            game_id="G1",
            player_id="123",
            player_name="Test Player",
            team="BOS",
            opponent="NYK",
            stat_type="points",
            line=24.5,
            over_odds=-110,
            under_odds=-110,
            is_live=False,
            snapshot_phase="current",
            captured_at=datetime(2026, 3, 16, 18, 0, 0),
        )
        fake_card = self._fake_card(snapshot, created_context_at=datetime(2026, 3, 16, 18, 0, 0))

        with self.session_scope() as session:
            session.add(
                StatsSignalSnapshot(
                    game_id="G1",
                    player_id="123",
                    player_name="Test Player",
                    team_abbreviation="BOS",
                    opponent_abbreviation="NYK",
                    stat_type="points",
                    snapshot_phase="current",
                    line=24.5,
                    over_odds=-110,
                    under_odds=-110,
                    projected_value=24.9,
                    edge_over=0.4,
                    edge_under=-0.4,
                    over_probability=0.51,
                    under_probability=0.49,
                    confidence=0.58,
                    recommended_side=None,
                    recent_hit_rate=0.5,
                    recent_games_count=10,
                    key_factor="Stale audit",
                    is_ready=True,
                    readiness_status="ready",
                    using_fallback=False,
                    readiness_json=SignalReadiness(status="ready", is_ready=True).model_dump_json(),
                    breakdown_json=PointsBreakdown(base_scoring=24.9, projected_points=24.9).model_dump_json(),
                    opportunity_json=OpportunityContext(expected_minutes=34.0).model_dump_json(),
                    features_json=FeatureSnapshot(team_abbreviation="BOS", opponent_abbreviation="NYK", is_home=True).model_dump_json(),
                    source_prop_captured_at=datetime(2026, 3, 16, 17, 40, 0),
                    created_at=datetime(2026, 3, 16, 17, 45, 0),
                )
            )

        with patch("api.services.stats_signal_service.session_scope", self.session_scope), patch(
            "api.services.stats_signal_service._load_current_snapshots",
            return_value=[snapshot],
        ), patch(
            "api.services.stats_signal_service._build_cards_from_snapshots",
            return_value=[fake_card],
        ):
            metrics = repair_current_signal_snapshots()

        self.assertEqual(metrics["repair_performed"], 1)
        self.assertEqual(metrics["signal_snapshots"], 1)

        with self.session_scope() as session:
            rows = session.query(StatsSignalSnapshot).order_by(StatsSignalSnapshot.created_at).all()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1].source_prop_captured_at, datetime(2026, 3, 16, 18, 0, 0))


class SignalHistoryLookupTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)
        Base.metadata.create_all(
            self.engine,
            tables=[Game.__table__, StatsSignalSnapshot.__table__],
        )

    def tearDown(self):
        Base.metadata.drop_all(
            self.engine,
            tables=[StatsSignalSnapshot.__table__, Game.__table__],
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

    def test_player_signal_history_returns_latest_snapshot_per_game(self):
        readiness_json = SignalReadiness(status="blocked", is_ready=False, blockers=["Missing report"], using_fallback=True).model_dump_json()
        breakdown_json = PointsBreakdown(base_scoring=21.0, projected_points=21.0).model_dump_json()
        opportunity_json = OpportunityContext(expected_minutes=31.0).model_dump_json()
        features_json = FeatureSnapshot(
            team_abbreviation="BOS",
            opponent_abbreviation="NYK",
            is_home=True,
            context_source="official_injury_team",
        ).model_dump_json()

        with self.session_scope() as session:
            session.add(
                Game(
                    game_id="G1",
                    season="2025-26",
                    game_date=datetime(2026, 3, 17, 0, 0, 0),
                    game_time_utc=datetime(2026, 3, 17, 0, 30, 0),
                    home_team_abbreviation="BOS",
                    away_team_abbreviation="NYK",
                )
            )
            session.add(
                StatsSignalSnapshot(
                    game_id="G1",
                    player_id="123",
                    player_name="Test Player",
                    team_abbreviation="BOS",
                    opponent_abbreviation="NYK",
                    stat_type="points",
                    snapshot_phase="current",
                    line=24.5,
                    over_odds=-110,
                    under_odds=-110,
                    projected_value=22.0,
                    edge_over=-2.5,
                    edge_under=2.5,
                    over_probability=0.35,
                    under_probability=0.65,
                    confidence=0.62,
                    recommended_side=None,
                    recent_hit_rate=0.4,
                    recent_games_count=10,
                    key_factor="Earlier run",
                    is_ready=False,
                    readiness_status="blocked",
                    using_fallback=True,
                    readiness_json=readiness_json,
                    breakdown_json=breakdown_json,
                    opportunity_json=opportunity_json,
                    features_json=features_json,
                    source_prop_captured_at=datetime(2026, 3, 16, 18, 0, 0),
                    source_context_captured_at=None,
                    source_injury_report_at=None,
                    created_at=datetime(2026, 3, 16, 18, 5, 0),
                )
            )
            session.add(
                StatsSignalSnapshot(
                    game_id="G1",
                    player_id="123",
                    player_name="Test Player",
                    team_abbreviation="BOS",
                    opponent_abbreviation="NYK",
                    stat_type="points",
                    snapshot_phase="current",
                    line=24.5,
                    over_odds=-110,
                    under_odds=-110,
                    projected_value=25.4,
                    edge_over=0.9,
                    edge_under=-0.9,
                    over_probability=0.54,
                    under_probability=0.46,
                    confidence=0.64,
                    recommended_side="OVER",
                    recent_hit_rate=0.6,
                    recent_games_count=10,
                    key_factor="Latest run",
                    is_ready=True,
                    readiness_status="ready",
                    using_fallback=False,
                    readiness_json=SignalReadiness(status="ready", is_ready=True).model_dump_json(),
                    breakdown_json=PointsBreakdown(base_scoring=25.4, projected_points=25.4).model_dump_json(),
                    opportunity_json=OpportunityContext(expected_minutes=34.0).model_dump_json(),
                    features_json=FeatureSnapshot(
                        team_abbreviation="BOS",
                        opponent_abbreviation="NYK",
                        is_home=True,
                        context_source="pregame_context",
                    ).model_dump_json(),
                    source_prop_captured_at=datetime(2026, 3, 16, 18, 15, 0),
                    source_context_captured_at=datetime(2026, 3, 16, 18, 15, 0),
                    source_injury_report_at=datetime(2026, 3, 16, 18, 0, 0),
                    created_at=datetime(2026, 3, 16, 18, 20, 0),
                )
            )

        with self.session_scope() as session:
            history = get_player_signal_history(session, player_id="123")

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].key_factor, "Latest run")
        self.assertEqual(history[0].recommended_side, "OVER")
        self.assertEqual(history[0].readiness.status, "ready")
        self.assertEqual(history[0].source_prop_captured_at, datetime(2026, 3, 16, 18, 15, 0))


if __name__ == "__main__":
    unittest.main()
