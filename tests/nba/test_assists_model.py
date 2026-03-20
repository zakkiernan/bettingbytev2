import unittest
from datetime import datetime

from analytics.assists_model import project_pregame_assists
from analytics.features_assists import PregameAssistsFeatures
from analytics.opportunity_model import PregameOpportunityBreakdown, PregameOpportunityProjection


class PregameAssistsModelTests(unittest.TestCase):
    def build_feature(self, **overrides):
        base = PregameAssistsFeatures(
            game_id="002TEST",
            player_id="123",
            player_name="Test Player",
            line=6.5,
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
            season_assists_avg=6.1,
            last10_assists_avg=6.7,
            last5_assists_avg=7.2,
            last10_assists_median=6.5,
            last10_assists_std=1.8,
            season_ast_pct=0.24,
            last10_ast_pct=0.26,
            last5_ast_pct=0.27,
            season_potential_assists=10.0,
            last10_potential_assists=10.8,
            last5_potential_assists=11.2,
            season_minutes_avg=33.0,
            last10_minutes_avg=34.0,
            last5_minutes_avg=35.0,
            last10_minutes_std=2.0,
            season_usage_pct=0.26,
            last10_usage_pct=0.27,
            last5_usage_pct=0.28,
            season_est_usage_pct=0.255,
            last10_est_usage_pct=0.265,
            last5_est_usage_pct=0.275,
            season_touches=68.0,
            last10_touches=71.0,
            last5_touches=73.0,
            season_passes=49.0,
            last10_passes=52.0,
            last5_passes=54.0,
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

    def _opportunity_projection(self, *, minutes: float, usage_pct: float, passes: float) -> PregameOpportunityProjection:
        return PregameOpportunityProjection(
            features=self.build_feature(),
            breakdown=PregameOpportunityBreakdown(
                expected_minutes=minutes,
                expected_rotation_minutes=minutes,
                expected_usage_pct=usage_pct,
                expected_est_usage_pct=usage_pct - 0.01,
                expected_touches=74.0,
                expected_passes=passes,
                expected_stint_count=3.0,
                expected_start_rate=0.95,
                expected_close_rate=0.86,
                availability_modifier=1.0,
                vacated_minutes_bonus=0.0,
                vacated_usage_bonus=0.0,
                role_replacement_minutes_bonus=0.0,
                role_replacement_usage_bonus=0.0,
                absence_impact_minutes_bonus=0.0,
                absence_impact_usage_bonus=0.0,
                role_stability=0.8,
                rotation_role_score=0.78,
                offensive_role_score=0.7,
                matchup_environment_score=0.6,
                opportunity_score=0.77,
                confidence=0.74,
            ),
        )

    def test_projection_runs_full_pipeline(self):
        projection = project_pregame_assists(self.build_feature())

        self.assertGreater(projection.projected_value, 0.0)
        self.assertGreaterEqual(projection.confidence, 0.0)
        self.assertLessEqual(projection.confidence, 1.0)
        self.assertAlmostEqual(projection.over_probability + projection.under_probability, 1.0, places=4)

    def test_projection_uses_opportunity_backbone(self):
        low_playmaking = project_pregame_assists(
            self.build_feature(),
            opportunity_projection=self._opportunity_projection(minutes=30.0, usage_pct=0.24, passes=44.0),
        )
        high_playmaking = project_pregame_assists(
            self.build_feature(),
            opportunity_projection=self._opportunity_projection(minutes=36.0, usage_pct=0.23, passes=58.0),
        )

        self.assertGreater(high_playmaking.breakdown.expected_minutes, low_playmaking.breakdown.expected_minutes)
        self.assertGreater(high_playmaking.projected_value, low_playmaking.projected_value)


if __name__ == "__main__":
    unittest.main()
