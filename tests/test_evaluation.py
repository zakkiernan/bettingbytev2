from __future__ import annotations

import unittest
from datetime import date, datetime
from types import SimpleNamespace

from analytics.evaluation import (
    _build_historical_injury_report_indexes,
    _build_odds_index,
    _grade_recommended_pick,
    _select_historical_injury_index,
    _select_latest_pregame_odds_snapshot,
    _summarize_context_attachment,
    _summarize_points_decisions,
    _summarize_points_errors,
    summarize_opportunity_absence_impact,
    summarize_points_absence_impact,
)
from analytics.injury_report_loader import get_official_team_summary, match_official_injury_row
from analytics.stats_signal_evaluation import (
    StatsSignalBacktestRow,
    summarize_stats_signal_decisions,
    summarize_stats_signal_profile_buckets,
)


class HistoricalInjuryEvaluationTests(unittest.TestCase):
    def test_select_historical_injury_index_uses_latest_report_before_tip(self):
        rows = [
            SimpleNamespace(
                report_id=10,
                report_datetime_utc=datetime(2026, 1, 5, 18, 0, 0),
                game_date=date(2026, 1, 5),
                matchup='NYK@BOS',
                team_abbreviation='BOS',
                team_name='Boston Celtics',
                player_id='1627759',
                player_name='Jaylen Brown',
                current_status='QUESTIONABLE',
                reason='Knee',
                report_submitted=True,
            ),
            SimpleNamespace(
                report_id=10,
                report_datetime_utc=datetime(2026, 1, 5, 18, 0, 0),
                game_date=date(2026, 1, 5),
                matchup='NYK@BOS',
                team_abbreviation='BOS',
                team_name='Boston Celtics',
                player_id='1',
                player_name='Teammate One',
                current_status='OUT',
                reason='Ankle',
                report_submitted=True,
            ),
            SimpleNamespace(
                report_id=11,
                report_datetime_utc=datetime(2026, 1, 5, 19, 0, 0),
                game_date=date(2026, 1, 5),
                matchup='NYK@BOS',
                team_abbreviation='BOS',
                team_name='Boston Celtics',
                player_id='1627759',
                player_name='Jaylen Brown',
                current_status='AVAILABLE',
                reason=None,
                report_submitted=True,
            ),
            SimpleNamespace(
                report_id=11,
                report_datetime_utc=datetime(2026, 1, 5, 19, 0, 0),
                game_date=date(2026, 1, 5),
                matchup='NYK@BOS',
                team_abbreviation='BOS',
                team_name='Boston Celtics',
                player_id='2',
                player_name='Teammate Two',
                current_status='OUT',
                reason='Hamstring',
                report_submitted=True,
            ),
        ]

        rows_by_report_id, report_refs_by_game_date = _build_historical_injury_report_indexes(rows)
        index_cache = {}

        early_index = _select_historical_injury_index(
            game_date=date(2026, 1, 5),
            captured_at=datetime(2026, 1, 5, 18, 30, 0),
            rows_by_report_id=rows_by_report_id,
            report_refs_by_game_date=report_refs_by_game_date,
            index_cache=index_cache,
        )
        late_index = _select_historical_injury_index(
            game_date=date(2026, 1, 5),
            captured_at=datetime(2026, 1, 5, 19, 30, 0),
            rows_by_report_id=rows_by_report_id,
            report_refs_by_game_date=report_refs_by_game_date,
            index_cache=index_cache,
        )

        early_match = match_official_injury_row(
            early_index,
            game_date=date(2026, 1, 5),
            player_id='1627759',
            team_abbreviation='BOS',
            player_name='Jaylen Brown',
        )
        late_match = match_official_injury_row(
            late_index,
            game_date=date(2026, 1, 5),
            player_id='1627759',
            team_abbreviation='BOS',
            player_name='Jaylen Brown',
        )
        late_summary = get_official_team_summary(
            late_index,
            game_date=date(2026, 1, 5),
            team_abbreviation='BOS',
        )

        self.assertEqual(early_match['current_status'], 'QUESTIONABLE')
        self.assertEqual(late_match['current_status'], 'AVAILABLE')
        self.assertEqual(late_summary['out_count'], 1)


class HistoricalOddsEvaluationTests(unittest.TestCase):
    def test_select_latest_odds_snapshot_respects_tip_cutoff_and_lead_windows(self):
        rows = [
            SimpleNamespace(game_id="G1", player_id="7", captured_at=datetime(2026, 1, 5, 17, 45, 0), line=23.5, over_odds=-110, under_odds=-110),
            SimpleNamespace(game_id="G1", player_id="7", captured_at=datetime(2026, 1, 5, 18, 40, 0), line=24.5, over_odds=-110, under_odds=-110),
            SimpleNamespace(game_id="G1", player_id="7", captured_at=datetime(2026, 1, 5, 19, 5, 0), line=25.5, over_odds=-110, under_odds=-110),
        ]
        index = _build_odds_index(rows)

        latest = _select_latest_pregame_odds_snapshot(
            index,
            game_id="G1",
            player_id="7",
            cutoff=datetime(2026, 1, 5, 19, 0, 0),
        )
        with_min_lead = _select_latest_pregame_odds_snapshot(
            index,
            game_id="G1",
            player_id="7",
            cutoff=datetime(2026, 1, 5, 19, 0, 0),
            min_minutes_before_tip=30,
        )

        self.assertEqual(latest.line, 24.5)
        self.assertEqual(with_min_lead.line, 23.5)


    def test_summarize_points_errors_returns_zeroed_empty_slice(self):
        empty = _summarize_points_errors([])
        populated = _summarize_points_errors([
            SimpleNamespace(error=2.0, abs_error=2.0),
            SimpleNamespace(error=-1.0, abs_error=1.0),
        ])

        self.assertEqual(empty.sample_size, 0)
        self.assertEqual(empty.mae, 0.0)
        self.assertEqual(populated.sample_size, 2)
        self.assertEqual(populated.mae, 1.5)
        self.assertEqual(populated.rmse, 1.5811)
        self.assertEqual(populated.bias, 0.5)
        self.assertEqual(populated.within_two_points_pct, 1.0)
        self.assertEqual(populated.within_four_points_pct, 1.0)

    def test_summarize_context_attachment_tracks_injury_only_rows(self):
        coverage = _summarize_context_attachment([
            SimpleNamespace(pregame_context_attached=True, official_injury_attached=True),
            SimpleNamespace(pregame_context_attached=False, official_injury_attached=True),
            SimpleNamespace(pregame_context_attached=False, official_injury_attached=False),
        ])

        self.assertEqual(coverage.pregame_context_attached_count, 1)
        self.assertEqual(coverage.official_injury_attached_count, 2)
        self.assertEqual(coverage.injury_only_context_count, 1)

    def test_grade_recommended_pick_handles_win_loss_push(self):
        win = SimpleNamespace(line_available=True, recommended_side='OVER', line=24.5, actual_points=28.0)
        loss = SimpleNamespace(line_available=True, recommended_side='UNDER', line=24.5, actual_points=27.0)
        push = SimpleNamespace(line_available=True, recommended_side='OVER', line=24.0, actual_points=24.0)
        missing = SimpleNamespace(line_available=False, recommended_side='OVER', line=None, actual_points=24.0)

        self.assertEqual(_grade_recommended_pick(win), 'win')
        self.assertEqual(_grade_recommended_pick(loss), 'loss')
        self.assertEqual(_grade_recommended_pick(push), 'push')
        self.assertIsNone(_grade_recommended_pick(missing))

    def test_summarize_points_decisions_buckets_recommendations(self):
        rows = [
            SimpleNamespace(line_available=True, recommended_side='OVER', recommended_outcome='win', edge_over=1.4, confidence=0.61),
            SimpleNamespace(line_available=True, recommended_side='UNDER', recommended_outcome='loss', edge_over=-2.2, confidence=0.73),
            SimpleNamespace(line_available=True, recommended_side='OVER', recommended_outcome='push', edge_over=3.3, confidence=0.82),
            SimpleNamespace(line_available=False, recommended_side='OVER', recommended_outcome=None, edge_over=4.0, confidence=0.90),
            SimpleNamespace(line_available=True, recommended_side=None, recommended_outcome=None, edge_over=0.8, confidence=0.55),
        ]

        summary = _summarize_points_decisions(rows)

        self.assertEqual(summary.recommendation_count, 3)
        self.assertEqual(summary.win_count, 1)
        self.assertEqual(summary.loss_count, 1)
        self.assertEqual(summary.push_count, 1)
        self.assertEqual(summary.graded_count, 2)
        self.assertEqual(summary.over_recommendation_count, 2)
        self.assertEqual(summary.under_recommendation_count, 1)
        self.assertAlmostEqual(summary.hit_rate, 0.5)
        self.assertTrue(any(bucket.label == '60-70%' for bucket in summary.confidence_buckets))
        self.assertTrue(any(bucket.label == '1.0-2.0' for bucket in summary.edge_buckets))

    def test_summarize_points_absence_impact_splits_usage_only_vs_minutes(self):
        summary = summarize_points_absence_impact([
            SimpleNamespace(
                game_id='1',
                game_date=datetime(2026, 1, 1),
                player_name='A',
                team_abbreviation='BOS',
                opponent_abbreviation='NYK',
                projected_points=22.0,
                actual_points=18.0,
                error=4.0,
                abs_error=4.0,
                absence_impact_sample_confidence=0.42,
                absence_impact_source_count=1.0,
                absence_impact_minutes_bonus=0.0,
                absence_impact_usage_bonus=0.01,
            ),
            SimpleNamespace(
                game_id='2',
                game_date=datetime(2026, 1, 2),
                player_name='B',
                team_abbreviation='BOS',
                opponent_abbreviation='MIA',
                projected_points=24.0,
                actual_points=15.0,
                error=9.0,
                abs_error=9.0,
                absence_impact_sample_confidence=0.68,
                absence_impact_source_count=2.0,
                absence_impact_minutes_bonus=1.2,
                absence_impact_usage_bonus=0.012,
            ),
            SimpleNamespace(
                game_id='3',
                game_date=datetime(2026, 1, 3),
                player_name='C',
                team_abbreviation='BOS',
                opponent_abbreviation='PHI',
                projected_points=20.0,
                actual_points=19.0,
                error=1.0,
                abs_error=1.0,
                absence_impact_sample_confidence=None,
                absence_impact_source_count=None,
                absence_impact_minutes_bonus=0.0,
                absence_impact_usage_bonus=0.0,
            ),
        ])

        self.assertEqual(summary['affected_count'], 2)
        self.assertEqual(summary['minutes_affected_count'], 1)
        self.assertEqual(summary['usage_only_count'], 1)
        self.assertEqual(summary['usage_only_mae'], 4.0)
        self.assertEqual(summary['minutes_affected_mae'], 9.0)
        self.assertEqual(summary['unaffected_mae'], 1.0)
        self.assertTrue(any(bucket.label == '0.35-0.49' for bucket in summary['confidence_buckets']))

    def test_summarize_opportunity_absence_impact_splits_usage_only_vs_minutes(self):
        summary = summarize_opportunity_absence_impact([
            SimpleNamespace(
                game_id='1',
                game_date=datetime(2026, 1, 1),
                player_name='A',
                team_abbreviation='BOS',
                opponent_abbreviation='NYK',
                expected_minutes=28.0,
                actual_minutes=24.0,
                minutes_error=4.0,
                abs_minutes_error=4.0,
                context_source='pregame_context',
                absence_impact_sample_confidence=0.42,
                absence_impact_source_count=1.0,
                absence_impact_minutes_bonus=0.0,
                absence_impact_usage_bonus=0.01,
            ),
            SimpleNamespace(
                game_id='2',
                game_date=datetime(2026, 1, 2),
                player_name='B',
                team_abbreviation='BOS',
                opponent_abbreviation='MIA',
                expected_minutes=34.0,
                actual_minutes=20.0,
                minutes_error=14.0,
                abs_minutes_error=14.0,
                context_source='pregame_context',
                absence_impact_sample_confidence=0.68,
                absence_impact_source_count=2.0,
                absence_impact_minutes_bonus=1.2,
                absence_impact_usage_bonus=0.012,
            ),
            SimpleNamespace(
                game_id='3',
                game_date=datetime(2026, 1, 3),
                player_name='C',
                team_abbreviation='BOS',
                opponent_abbreviation='PHI',
                expected_minutes=22.0,
                actual_minutes=21.0,
                minutes_error=1.0,
                abs_minutes_error=1.0,
                context_source='none',
                absence_impact_sample_confidence=None,
                absence_impact_source_count=None,
                absence_impact_minutes_bonus=0.0,
                absence_impact_usage_bonus=0.0,
            ),
        ])

        self.assertEqual(summary['affected_count'], 2)
        self.assertEqual(summary['minutes_affected_count'], 1)
        self.assertEqual(summary['usage_only_count'], 1)
        self.assertEqual(summary['usage_only_minutes_mae'], 4.0)
        self.assertEqual(summary['minutes_affected_minutes_mae'], 14.0)
        self.assertEqual(summary['unaffected_minutes_mae'], 1.0)
        self.assertTrue(any(bucket.label == '0.65+' for bucket in summary['confidence_buckets']))

    def test_summarize_stats_signal_decisions_tracks_calibration_gap(self):
        rows = [
            StatsSignalBacktestRow(
                game_id="G1",
                game_date=datetime(2026, 1, 1),
                player_id="1",
                player_name="A",
                team_abbreviation="BOS",
                opponent_abbreviation="NYK",
                projected_points=26.0,
                actual_points=29.0,
                actual_minutes=35.0,
                expected_minutes=34.0,
                error=-3.0,
                abs_error=3.0,
                line=24.5,
                line_available=True,
                over_probability=0.64,
                under_probability=0.36,
                recommended_probability=0.64,
                edge_over=1.5,
                edge_under=-1.5,
                confidence=0.61,
                recommended_side="OVER",
                line_delta=4.5,
                recommended_outcome="win",
                recent_hit_rate=0.7,
                recent_games_count=10,
                key_factor=None,
                pregame_context_attached=True,
                official_injury_attached=True,
                context_source="pregame_context",
                readiness_status="ready",
                readiness_blocker_count=0,
                readiness_warning_count=0,
                using_fallback=False,
                breakdown={"expected_minutes": 34.0},
            ),
            StatsSignalBacktestRow(
                game_id="G2",
                game_date=datetime(2026, 1, 2),
                player_id="2",
                player_name="B",
                team_abbreviation="BOS",
                opponent_abbreviation="MIA",
                projected_points=22.0,
                actual_points=25.0,
                actual_minutes=31.0,
                expected_minutes=30.0,
                error=-3.0,
                abs_error=3.0,
                line=23.5,
                line_available=True,
                over_probability=0.43,
                under_probability=0.57,
                recommended_probability=0.57,
                edge_over=-1.5,
                edge_under=1.5,
                confidence=0.72,
                recommended_side="UNDER",
                line_delta=1.5,
                recommended_outcome="loss",
                recent_hit_rate=0.4,
                recent_games_count=10,
                key_factor=None,
                pregame_context_attached=False,
                official_injury_attached=True,
                context_source="official_injury_team",
                readiness_status="limited",
                readiness_blocker_count=0,
                readiness_warning_count=1,
                using_fallback=False,
                breakdown={"expected_minutes": 30.0},
            ),
        ]

        summary = summarize_stats_signal_decisions(rows)

        self.assertEqual(summary.recommendation_count, 2)
        self.assertEqual(summary.win_count, 1)
        self.assertEqual(summary.loss_count, 1)
        self.assertAlmostEqual(summary.hit_rate, 0.5)
        self.assertAlmostEqual(summary.implied_hit_rate, 0.605)
        self.assertAlmostEqual(summary.calibration_gap, -0.105)
        self.assertTrue(any(bucket.label == "60-70%" for bucket in summary.confidence_buckets))

    def test_summarize_stats_signal_profile_buckets_groups_by_expected_minutes(self):
        rows = [
            StatsSignalBacktestRow(
                game_id="G1",
                game_date=datetime(2026, 1, 1),
                player_id="1",
                player_name="A",
                team_abbreviation="BOS",
                opponent_abbreviation="NYK",
                projected_points=14.0,
                actual_points=13.0,
                actual_minutes=20.0,
                expected_minutes=22.0,
                error=1.0,
                abs_error=1.0,
                line=12.5,
                line_available=True,
                over_probability=0.58,
                under_probability=0.42,
                recommended_probability=0.58,
                edge_over=1.5,
                edge_under=-1.5,
                confidence=0.59,
                recommended_side="OVER",
                line_delta=0.5,
                recommended_outcome="win",
                recent_hit_rate=0.6,
                recent_games_count=8,
                key_factor=None,
                pregame_context_attached=True,
                official_injury_attached=False,
                context_source="pregame_context",
                readiness_status="ready",
                readiness_blocker_count=0,
                readiness_warning_count=0,
                using_fallback=False,
                breakdown={"expected_minutes": 22.0},
            ),
            StatsSignalBacktestRow(
                game_id="G2",
                game_date=datetime(2026, 1, 2),
                player_id="2",
                player_name="B",
                team_abbreviation="BOS",
                opponent_abbreviation="MIA",
                projected_points=25.0,
                actual_points=23.0,
                actual_minutes=31.0,
                expected_minutes=30.0,
                error=2.0,
                abs_error=2.0,
                line=24.5,
                line_available=True,
                over_probability=0.55,
                under_probability=0.45,
                recommended_probability=0.55,
                edge_over=0.5,
                edge_under=-0.5,
                confidence=0.6,
                recommended_side="OVER",
                line_delta=-1.5,
                recommended_outcome="loss",
                recent_hit_rate=0.5,
                recent_games_count=10,
                key_factor=None,
                pregame_context_attached=True,
                official_injury_attached=True,
                context_source="pregame_context",
                readiness_status="ready",
                readiness_blocker_count=0,
                readiness_warning_count=0,
                using_fallback=False,
                breakdown={"expected_minutes": 30.0},
            ),
            StatsSignalBacktestRow(
                game_id="G3",
                game_date=datetime(2026, 1, 3),
                player_id="3",
                player_name="C",
                team_abbreviation="BOS",
                opponent_abbreviation="PHI",
                projected_points=29.0,
                actual_points=28.0,
                actual_minutes=36.0,
                expected_minutes=34.0,
                error=1.0,
                abs_error=1.0,
                line=27.5,
                line_available=True,
                over_probability=0.57,
                under_probability=0.43,
                recommended_probability=None,
                edge_over=1.5,
                edge_under=-1.5,
                confidence=0.62,
                recommended_side=None,
                line_delta=0.5,
                recommended_outcome=None,
                recent_hit_rate=0.6,
                recent_games_count=10,
                key_factor=None,
                pregame_context_attached=False,
                official_injury_attached=False,
                context_source="none",
                readiness_status="blocked",
                readiness_blocker_count=1,
                readiness_warning_count=0,
                using_fallback=True,
                breakdown={"expected_minutes": 34.0},
            ),
        ]

        buckets = summarize_stats_signal_profile_buckets(rows)

        by_label = {bucket.label: bucket for bucket in buckets}
        self.assertEqual(by_label["under_24m"].sample_size, 1)
        self.assertEqual(by_label["24_to_32m"].recommendation_count, 1)
        self.assertEqual(by_label["32m_plus"].sample_size, 1)
        self.assertEqual(by_label["32m_plus"].recommendation_count, 0)


if __name__ == '__main__':
    unittest.main()
