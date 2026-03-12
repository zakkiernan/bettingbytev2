from __future__ import annotations

import unittest
from datetime import datetime

from analytics.features_pregame import PregamePointsFeatures
from analytics.pregame_model import project_pregame_points


class PregamePointsModelTests(unittest.TestCase):
    def build_feature(self, **overrides):
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
            last10_points_avg=25.2,
            last5_points_avg=27.0,
            last10_points_median=25.0,
            last10_points_std=4.2,
            season_minutes_avg=34.0,
            last10_minutes_avg=35.0,
            last5_minutes_avg=35.5,
            last10_minutes_std=2.1,
            season_fga_avg=17.5,
            last10_fga_avg=18.6,
            last5_fga_avg=19.1,
            season_3pa_avg=6.5,
            last10_3pa_avg=7.1,
            last5_3pa_avg=7.4,
            season_fta_avg=5.1,
            last10_fta_avg=5.8,
            last5_fta_avg=6.0,
            season_fg_pct=0.47,
            last10_fg_pct=0.49,
            last5_fg_pct=0.50,
            season_3pt_pct=0.37,
            last10_3pt_pct=0.39,
            last5_3pt_pct=0.40,
            season_ft_pct=0.84,
            last10_ft_pct=0.85,
            last5_ft_pct=0.86,
            season_ts_pct=0.58,
            last10_ts_pct=0.61,
            last5_ts_pct=0.62,
            season_efg_pct=0.54,
            last10_efg_pct=0.56,
            last5_efg_pct=0.57,
            season_usage_pct=0.28,
            last10_usage_pct=0.295,
            last5_usage_pct=0.302,
            season_est_usage_pct=0.275,
            last10_est_usage_pct=0.288,
            last5_est_usage_pct=0.296,
            season_touches=58.0,
            last10_touches=61.0,
            last5_touches=62.5,
            season_passes=42.0,
            last10_passes=43.5,
            last5_passes=44.0,
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
        )
        for key, value in overrides.items():
            setattr(base, key, value)
        return base

    def test_projection_recommends_over_for_strong_profile(self):
        projection = project_pregame_points(self.build_feature())

        self.assertGreater(projection.projected_value, 24.5)
        self.assertEqual(projection.recommended_side, "OVER")
        self.assertGreater(projection.over_probability, 0.54)
        self.assertGreater(projection.confidence, 0.4)


    def test_projection_uses_opportunity_backbone_for_role_lift(self):
        low_role = project_pregame_points(
            self.build_feature(
                rotation_sample_size=8,
                season_rotation_minutes_avg=24.0,
                last10_rotation_minutes_avg=23.5,
                last5_rotation_minutes_avg=23.0,
                last10_rotation_minutes_std=3.5,
                season_stint_count_avg=4.2,
                last10_stint_count_avg=4.0,
                last5_stint_count_avg=4.0,
                season_started_rate=0.2,
                last10_started_rate=0.2,
                last5_started_rate=0.2,
                season_closed_rate=0.2,
                last10_closed_rate=0.2,
                last5_closed_rate=0.2,
                season_usage_pct=0.24,
                last10_usage_pct=0.24,
                last5_usage_pct=0.24,
            )
        )
        high_role = project_pregame_points(
            self.build_feature(
                season_rotation_minutes_avg=36.0,
                last10_rotation_minutes_avg=37.0,
                last5_rotation_minutes_avg=37.5,
                season_started_rate=1.0,
                last10_started_rate=1.0,
                last5_started_rate=1.0,
                season_closed_rate=0.9,
                last10_closed_rate=0.9,
                last5_closed_rate=0.9,
                season_usage_pct=0.30,
                last10_usage_pct=0.31,
                last5_usage_pct=0.315,
                season_est_usage_pct=0.29,
                last10_est_usage_pct=0.30,
                last5_est_usage_pct=0.305,
                season_touches=64.0,
                last10_touches=67.0,
                last5_touches=68.5,
            )
        )

        self.assertGreater(high_role.breakdown.expected_minutes, low_role.breakdown.expected_minutes)
        self.assertGreater(high_role.breakdown.opportunity_score, low_role.breakdown.opportunity_score)
        self.assertGreater(high_role.projected_value, low_role.projected_value)
        self.assertGreater(high_role.confidence, low_role.confidence)

    def test_projection_bounds_outputs(self):
        projection = project_pregame_points(
            self.build_feature(
                line=31.5,
                last5_points_avg=20.0,
                last10_points_avg=21.0,
                last10_points_std=8.0,
                season_usage_pct=0.24,
                last10_usage_pct=0.225,
                season_fga_avg=16.0,
                last10_fga_avg=13.5,
                season_fta_avg=5.0,
                last10_fta_avg=3.0,
                is_home=False,
                days_rest=1,
                back_to_back=True,
            )
        )

        self.assertGreaterEqual(projection.confidence, 0.0)
        self.assertLessEqual(projection.confidence, 1.0)
        self.assertGreaterEqual(projection.over_probability, 0.0)
        self.assertLessEqual(projection.over_probability, 1.0)
        self.assertGreaterEqual(projection.under_probability, 0.0)
        self.assertLessEqual(projection.under_probability, 1.0)
        self.assertAlmostEqual(projection.over_probability + projection.under_probability, 1.0, places=4)


if __name__ == "__main__":
    unittest.main()
