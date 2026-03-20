import unittest
from datetime import datetime

from analytics.features_threes import PregameThreesFeatures
from analytics.opportunity_model import PregameOpportunityBreakdown, PregameOpportunityProjection
from analytics.threes_model import project_pregame_threes


class PregameThreesModelTests(unittest.TestCase):
    def build_feature(self, **overrides):
        base = PregameThreesFeatures(
            game_id="002TEST",
            player_id="123",
            player_name="Test Player",
            line=2.5,
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
            season_threes_avg=2.4,
            last10_threes_avg=2.8,
            last5_threes_avg=3.1,
            last10_threes_median=3.0,
            last10_threes_std=1.2,
            season_3pa_avg=6.8,
            last10_3pa_avg=7.4,
            last5_3pa_avg=7.8,
            season_3pt_pct=0.36,
            last10_3pt_pct=0.38,
            last5_3pt_pct=0.39,
            season_3pa_rate=0.38,
            last10_3pa_rate=0.40,
            last5_3pa_rate=0.41,
            season_minutes_avg=32.0,
            last10_minutes_avg=33.0,
            last5_minutes_avg=34.0,
            last10_minutes_std=2.0,
            season_usage_pct=0.24,
            last10_usage_pct=0.25,
            last5_usage_pct=0.26,
            season_est_usage_pct=0.235,
            last10_est_usage_pct=0.245,
            last5_est_usage_pct=0.255,
            season_touches=54.0,
            last10_touches=56.0,
            last5_touches=58.0,
            season_passes=34.0,
            last10_passes=35.0,
            last5_passes=36.0,
            team_pace=100.5,
            opponent_def_rating=112.0,
            opponent_pace=99.4,
            opponent_points_allowed=112.2,
            opponent_fg_pct_allowed=0.46,
            opponent_3pt_pct_allowed=0.37,
            league_avg_def_rating=114.5,
            league_avg_pace=99.0,
            league_avg_opponent_points=113.0,
        )
        for key, value in overrides.items():
            setattr(base, key, value)
        return base

    def _opportunity_projection(self, *, minutes: float, usage_pct: float) -> PregameOpportunityProjection:
        return PregameOpportunityProjection(
            features=self.build_feature(),
            breakdown=PregameOpportunityBreakdown(
                expected_minutes=minutes,
                expected_rotation_minutes=minutes,
                expected_usage_pct=usage_pct,
                expected_est_usage_pct=usage_pct - 0.01,
                expected_touches=60.0,
                expected_passes=36.0,
                expected_stint_count=3.0,
                expected_start_rate=0.88,
                expected_close_rate=0.80,
                availability_modifier=1.0,
                vacated_minutes_bonus=0.0,
                vacated_usage_bonus=0.0,
                role_replacement_minutes_bonus=0.0,
                role_replacement_usage_bonus=0.0,
                absence_impact_minutes_bonus=0.0,
                absence_impact_usage_bonus=0.0,
                role_stability=0.77,
                rotation_role_score=0.74,
                offensive_role_score=0.68,
                matchup_environment_score=0.59,
                opportunity_score=0.73,
                confidence=0.70,
            ),
        )

    def test_projection_runs_full_pipeline(self):
        projection = project_pregame_threes(self.build_feature())

        self.assertGreater(projection.projected_value, 0.0)
        self.assertGreaterEqual(projection.confidence, 0.0)
        self.assertLessEqual(projection.confidence, 1.0)
        self.assertAlmostEqual(projection.over_probability + projection.under_probability, 1.0, places=4)

    def test_projection_uses_opportunity_backbone(self):
        low_minutes = project_pregame_threes(
            self.build_feature(),
            opportunity_projection=self._opportunity_projection(minutes=28.0, usage_pct=0.23),
        )
        high_minutes = project_pregame_threes(
            self.build_feature(),
            opportunity_projection=self._opportunity_projection(minutes=36.0, usage_pct=0.27),
        )

        self.assertGreater(high_minutes.breakdown.expected_minutes, low_minutes.breakdown.expected_minutes)
        self.assertGreater(high_minutes.projected_value, low_minutes.projected_value)


if __name__ == "__main__":
    unittest.main()
