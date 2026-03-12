from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace

from analytics.features_opportunity import PregameOpportunityFeatures, _build_rotation_aggregates
from analytics.opportunity_model import PregameOpportunityModelConfig, project_pregame_opportunity


class PregameOpportunityModelTests(unittest.TestCase):
    def build_feature(self, **overrides):
        base = PregameOpportunityFeatures(
            game_id="002TEST",
            player_id="123",
            player_name="Test Player",
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
            season_minutes_avg=33.5,
            last10_minutes_avg=34.8,
            last5_minutes_avg=35.2,
            last10_minutes_std=2.0,
            rotation_sample_size=8,
            season_rotation_minutes_avg=34.0,
            last10_rotation_minutes_avg=35.5,
            last5_rotation_minutes_avg=36.0,
            last10_rotation_minutes_std=1.5,
            season_stint_count_avg=3.1,
            last10_stint_count_avg=3.0,
            last5_stint_count_avg=2.8,
            season_started_rate=0.9,
            last10_started_rate=1.0,
            last5_started_rate=1.0,
            season_closed_rate=0.8,
            last10_closed_rate=0.8,
            last5_closed_rate=0.8,
            season_usage_pct=0.27,
            last10_usage_pct=0.285,
            last5_usage_pct=0.292,
            season_est_usage_pct=0.268,
            last10_est_usage_pct=0.281,
            last5_est_usage_pct=0.289,
            season_touches=61.0,
            last10_touches=64.0,
            last5_touches=66.0,
            season_passes=43.0,
            last10_passes=45.0,
            last5_passes=46.0,
            season_off_rating=116.0,
            last10_off_rating=119.0,
            last5_off_rating=120.0,
            team_pace=100.5,
            opponent_def_rating=112.0,
            opponent_pace=99.4,
            opponent_points_allowed=112.2,
            opponent_fg_pct_allowed=0.46,
            opponent_3pt_pct_allowed=0.36,
            league_avg_def_rating=114.5,
            league_avg_pace=99.0,
            league_avg_opponent_points=113.0,
        )
        for key, value in overrides.items():
            setattr(base, key, value)
        return base

    def test_projection_outputs_are_bounded(self):
        projection = project_pregame_opportunity(self.build_feature())

        self.assertGreaterEqual(projection.breakdown.role_stability, 0.0)
        self.assertLessEqual(projection.breakdown.role_stability, 1.0)
        self.assertGreater(projection.breakdown.expected_minutes, 0.0)
        self.assertGreater(projection.breakdown.offensive_role_score, 0.0)
        self.assertGreaterEqual(projection.breakdown.confidence, 0.0)
        self.assertLessEqual(projection.breakdown.confidence, 1.0)

    def test_rotation_features_raise_expected_minutes_and_opportunity(self):
        without_rotation = project_pregame_opportunity(
            self.build_feature(
                rotation_sample_size=0,
                season_rotation_minutes_avg=None,
                last10_rotation_minutes_avg=None,
                last5_rotation_minutes_avg=None,
                last10_rotation_minutes_std=None,
                season_stint_count_avg=None,
                last10_stint_count_avg=None,
                last5_stint_count_avg=None,
                season_started_rate=None,
                last10_started_rate=None,
                last5_started_rate=None,
                season_closed_rate=None,
                last10_closed_rate=None,
                last5_closed_rate=None,
            )
        )
        with_rotation = project_pregame_opportunity(
            self.build_feature(
                season_rotation_minutes_avg=36.5,
                last10_rotation_minutes_avg=37.5,
                last5_rotation_minutes_avg=38.0,
                season_started_rate=1.0,
                last10_started_rate=1.0,
                last5_started_rate=1.0,
                season_closed_rate=1.0,
                last10_closed_rate=1.0,
                last5_closed_rate=1.0,
            )
        )

        self.assertGreater(with_rotation.breakdown.expected_minutes, without_rotation.breakdown.expected_minutes)
        self.assertGreater(with_rotation.breakdown.rotation_role_score, without_rotation.breakdown.rotation_role_score)
        self.assertGreater(with_rotation.breakdown.opportunity_score, without_rotation.breakdown.opportunity_score)



    def test_pregame_context_boosts_minutes_and_usage_for_open_role(self):
        baseline = project_pregame_opportunity(self.build_feature(
            expected_start=None,
            starter_confidence=None,
            projected_available=None,
            official_available=None,
            late_scratch_risk=None,
            teammate_out_count_top7=None,
            teammate_out_count_top9=None,
            missing_high_usage_teammates=None,
            vacated_minutes_proxy=None,
            vacated_usage_proxy=None,
            projected_lineup_confirmed=None,
            pregame_context_confidence=None,
        ))
        boosted = project_pregame_opportunity(self.build_feature(
            expected_start=True,
            starter_confidence=0.9,
            projected_available=True,
            official_available=True,
            late_scratch_risk=0.05,
            teammate_out_count_top7=2.0,
            teammate_out_count_top9=2.0,
            missing_high_usage_teammates=1.0,
            vacated_minutes_proxy=24.0,
            vacated_usage_proxy=0.06,
            projected_lineup_confirmed=True,
            pregame_context_confidence=0.95,
        ))

        self.assertGreater(boosted.breakdown.expected_minutes, baseline.breakdown.expected_minutes)
        self.assertGreater(boosted.breakdown.expected_usage_pct, baseline.breakdown.expected_usage_pct)
        self.assertGreater(boosted.breakdown.expected_start_rate, baseline.breakdown.expected_start_rate)
        self.assertGreater(boosted.breakdown.opportunity_score, baseline.breakdown.opportunity_score)

    def test_official_team_summary_only_does_not_create_fake_minutes_boost(self):
        baseline = project_pregame_opportunity(self.build_feature(
            official_teammate_out_count=None,
            official_teammate_doubtful_count=None,
            official_teammate_questionable_count=None,
            pregame_context_confidence=None,
            teammate_out_count_top7=None,
            teammate_out_count_top9=None,
            vacated_minutes_proxy=None,
            vacated_usage_proxy=None,
            missing_high_usage_teammates=None,
        ))
        team_summary_only = project_pregame_opportunity(self.build_feature(
            official_teammate_out_count=5.0,
            official_teammate_doubtful_count=1.0,
            official_teammate_questionable_count=2.0,
            pregame_context_confidence=0.25,
            teammate_out_count_top7=None,
            teammate_out_count_top9=None,
            vacated_minutes_proxy=None,
            vacated_usage_proxy=None,
            missing_high_usage_teammates=None,
        ))

        self.assertAlmostEqual(team_summary_only.breakdown.expected_minutes, baseline.breakdown.expected_minutes)
        self.assertAlmostEqual(team_summary_only.breakdown.expected_usage_pct, baseline.breakdown.expected_usage_pct)


    def test_pregame_context_unavailable_player_crushes_minutes_and_confidence(self):
        available = project_pregame_opportunity(self.build_feature(
            projected_available=True,
            official_available=True,
            late_scratch_risk=0.0,
            pregame_context_confidence=0.95,
        ))
        unavailable = project_pregame_opportunity(self.build_feature(
            expected_start=False,
            starter_confidence=0.1,
            projected_available=False,
            official_available=False,
            late_scratch_risk=1.0,
            pregame_context_confidence=0.95,
        ))

        self.assertLess(unavailable.breakdown.expected_minutes, available.breakdown.expected_minutes)
        self.assertLess(unavailable.breakdown.expected_start_rate, available.breakdown.expected_start_rate)
        self.assertLess(unavailable.breakdown.opportunity_score, available.breakdown.opportunity_score)
        self.assertLess(unavailable.breakdown.confidence, available.breakdown.confidence)

    def test_calibration_compresses_minutes_and_close_extremes(self):
        uncalibrated = PregameOpportunityModelConfig(
            minutes_regression_factor=1.0,
            close_rate_regression_factor=1.0,
            start_rate_regression_factor=1.0,
            usage_regression_factor=1.0,
            est_usage_regression_factor=1.0,
            touches_scale_factor=1.0,
            passes_scale_factor=1.0,
        )
        feature = self.build_feature(
            season_minutes_avg=37.0,
            last10_minutes_avg=38.0,
            last5_minutes_avg=39.0,
            season_closed_rate=1.0,
            last10_closed_rate=1.0,
            last5_closed_rate=1.0,
        )

        raw_projection = project_pregame_opportunity(feature, config=uncalibrated)
        calibrated_projection = project_pregame_opportunity(feature)

        self.assertLess(calibrated_projection.breakdown.expected_minutes, raw_projection.breakdown.expected_minutes)
        self.assertLess(calibrated_projection.breakdown.expected_close_rate, raw_projection.breakdown.expected_close_rate)
        self.assertGreater(calibrated_projection.breakdown.expected_close_rate, 0.5)

    def test_unstable_rotation_lowers_role_stability_and_confidence(self):
        stable = project_pregame_opportunity(self.build_feature())
        unstable = project_pregame_opportunity(
            self.build_feature(
                last10_minutes_std=6.5,
                last10_rotation_minutes_std=7.0,
                season_started_rate=0.8,
                last10_started_rate=0.4,
                last5_started_rate=0.2,
                season_closed_rate=0.7,
                last10_closed_rate=0.3,
                last5_closed_rate=0.2,
            )
        )

        self.assertGreater(stable.breakdown.role_stability, unstable.breakdown.role_stability)
        self.assertGreater(stable.breakdown.confidence, unstable.breakdown.confidence)


class RotationOpportunityFeatureTests(unittest.TestCase):
    def test_build_rotation_aggregates_summarizes_minutes_rates_and_stints(self):
        rows = [
            SimpleNamespace(total_shift_duration_real=18000.0, stint_count=2, started=True, closed_game=False),
            SimpleNamespace(total_shift_duration_real=21000.0, stint_count=3, started=True, closed_game=True),
            SimpleNamespace(total_shift_duration_real=15000.0, stint_count=4, started=False, closed_game=True),
        ]

        aggregates = _build_rotation_aggregates(rows)

        self.assertEqual(aggregates["rotation_sample_size"], 3)
        self.assertAlmostEqual(aggregates["season_rotation_minutes_avg"], 30.0)
        self.assertAlmostEqual(aggregates["season_stint_count_avg"], 3.0)
        self.assertAlmostEqual(aggregates["season_started_rate"], 2 / 3)
        self.assertAlmostEqual(aggregates["season_closed_rate"], 2 / 3)


if __name__ == "__main__":
    unittest.main()
