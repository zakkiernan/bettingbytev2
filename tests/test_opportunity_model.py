from __future__ import annotations

import unittest
from datetime import datetime

from analytics.features_opportunity import PregameOpportunityFeatures
from analytics.opportunity_model import project_pregame_opportunity


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


if __name__ == "__main__":
    unittest.main()
