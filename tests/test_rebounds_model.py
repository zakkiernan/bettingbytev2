import unittest
from datetime import datetime

from analytics.features_rebounds import PregameReboundsFeatures
from analytics.opportunity_model import PregameOpportunityBreakdown, PregameOpportunityProjection
from analytics.rebounds_model import project_pregame_rebounds


class PregameReboundsModelTests(unittest.TestCase):
    def build_feature(self, **overrides):
        base = PregameReboundsFeatures(
            game_id="002TEST",
            player_id="123",
            player_name="Test Player",
            line=8.5,
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
            season_rebounds_avg=8.2,
            last10_rebounds_avg=8.8,
            last5_rebounds_avg=9.4,
            last10_rebounds_median=9.0,
            last10_rebounds_std=2.0,
            season_oreb_avg=2.1,
            last10_oreb_avg=2.2,
            last5_oreb_avg=2.4,
            season_dreb_avg=6.1,
            last10_dreb_avg=6.6,
            last5_dreb_avg=7.0,
            season_reb_pct=0.18,
            last10_reb_pct=0.19,
            last5_reb_pct=0.20,
            season_oreb_pct=0.07,
            last10_oreb_pct=0.074,
            last5_oreb_pct=0.078,
            season_dreb_pct=0.11,
            last10_dreb_pct=0.116,
            last5_dreb_pct=0.122,
            season_minutes_avg=31.0,
            last10_minutes_avg=32.0,
            last5_minutes_avg=33.0,
            last10_minutes_std=2.0,
            season_usage_pct=0.22,
            last10_usage_pct=0.225,
            last5_usage_pct=0.23,
            season_est_usage_pct=0.215,
            last10_est_usage_pct=0.22,
            last5_est_usage_pct=0.225,
            season_touches=46.0,
            last10_touches=48.0,
            last5_touches=50.0,
            season_passes=30.0,
            last10_passes=31.0,
            last5_passes=32.0,
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

    def _opportunity_projection(self, *, minutes: float, usage_pct: float) -> PregameOpportunityProjection:
        return PregameOpportunityProjection(
            features=self.build_feature(),
            breakdown=PregameOpportunityBreakdown(
                expected_minutes=minutes,
                expected_rotation_minutes=minutes,
                expected_usage_pct=usage_pct,
                expected_est_usage_pct=usage_pct - 0.01,
                expected_touches=52.0,
                expected_passes=31.0,
                expected_stint_count=3.0,
                expected_start_rate=0.9,
                expected_close_rate=0.8,
                availability_modifier=1.0,
                vacated_minutes_bonus=0.0,
                vacated_usage_bonus=0.0,
                role_replacement_minutes_bonus=0.0,
                role_replacement_usage_bonus=0.0,
                absence_impact_minutes_bonus=0.0,
                absence_impact_usage_bonus=0.0,
                role_stability=0.78,
                rotation_role_score=0.76,
                offensive_role_score=0.62,
                matchup_environment_score=0.58,
                opportunity_score=0.74,
                confidence=0.72,
            ),
        )

    def test_projection_runs_full_pipeline(self):
        projection = project_pregame_rebounds(self.build_feature())

        self.assertGreater(projection.projected_value, 0.0)
        self.assertGreaterEqual(projection.confidence, 0.0)
        self.assertLessEqual(projection.confidence, 1.0)
        self.assertAlmostEqual(projection.over_probability + projection.under_probability, 1.0, places=4)

    def test_projection_uses_opportunity_backbone(self):
        low_minutes = project_pregame_rebounds(
            self.build_feature(),
            opportunity_projection=self._opportunity_projection(minutes=26.0, usage_pct=0.21),
        )
        high_minutes = project_pregame_rebounds(
            self.build_feature(),
            opportunity_projection=self._opportunity_projection(minutes=36.0, usage_pct=0.24),
        )

        self.assertGreater(high_minutes.breakdown.expected_minutes, low_minutes.breakdown.expected_minutes)
        self.assertGreater(high_minutes.projected_value, low_minutes.projected_value)


if __name__ == "__main__":
    unittest.main()
