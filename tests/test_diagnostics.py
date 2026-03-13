from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace

from analytics.diagnostics import analyze_pregame_opportunity_misses, analyze_pregame_points_misses


class PregameDiagnosticsTests(unittest.TestCase):
    def test_points_miss_analysis_labels_minutes_shortfall(self):
        row = SimpleNamespace(
            player_name="Test Player",
            game_id="001",
            game_date=datetime(2026, 1, 1, 19, 0, 0),
            projected_points=24.0,
            actual_points=8.0,
            actual_minutes=6.0,
            expected_minutes=28.0,
            error=16.0,
            abs_error=16.0,
            opponent_adjustment=0.2,
            recent_form_adjustment=0.3,
        )

        analysis = analyze_pregame_points_misses(SimpleNamespace(rows=[row]), top_n=10)

        self.assertEqual(analysis.buckets[0].label, "minutes_shortfall")
        self.assertEqual(analysis.examples[0]["category"], "minutes_shortfall")

    def test_points_miss_analysis_tracks_line_availability_splits(self):
        with_line = SimpleNamespace(
            player_name="With Line",
            game_id="010",
            game_date=datetime(2026, 1, 4, 19, 0, 0),
            projected_points=22.0,
            actual_points=10.0,
            actual_minutes=7.0,
            expected_minutes=30.0,
            error=12.0,
            abs_error=12.0,
            opponent_adjustment=0.1,
            recent_form_adjustment=0.2,
            pregame_context_attached=True,
            line_available=True,
        )
        without_line = SimpleNamespace(
            player_name="Without Line",
            game_id="011",
            game_date=datetime(2026, 1, 5, 19, 0, 0),
            projected_points=19.0,
            actual_points=17.0,
            actual_minutes=29.0,
            expected_minutes=28.0,
            error=2.0,
            abs_error=2.0,
            opponent_adjustment=0.1,
            recent_form_adjustment=0.2,
            pregame_context_attached=False,
            line_available=False,
        )

        analysis = analyze_pregame_points_misses(SimpleNamespace(rows=[with_line, without_line]), top_n=10)

        self.assertEqual(analysis.line_available_count, 1)
        self.assertEqual(analysis.line_missing_count, 1)
        self.assertEqual(analysis.with_line_buckets[0].label, "minutes_shortfall")
        self.assertEqual(analysis.without_line_buckets[0].label, "mixed")
        self.assertTrue(analysis.examples[0]["line_available"] )



    def test_opportunity_miss_analysis_labels_role_and_usage_misses(self):
        start_miss = SimpleNamespace(
            player_name="Starter Miss",
            game_id="002",
            game_date=datetime(2026, 1, 2, 19, 0, 0),
            expected_minutes=31.0,
            actual_minutes=30.0,
            abs_minutes_error=1.0,
            expected_usage_pct=0.24,
            actual_usage_pct=0.23,
            abs_usage_error=0.01,
            expected_start_rate=0.92,
            actual_started=False,
            expected_close_rate=0.52,
            actual_closed=True,
            abs_touches_error=4.0,
            actual_touches=52.0,
            abs_passes_error=3.0,
            actual_passes=38.0,
            opportunity_score=0.63,
            confidence=0.58,
        )
        usage_miss = SimpleNamespace(
            player_name="Usage Miss",
            game_id="003",
            game_date=datetime(2026, 1, 3, 19, 0, 0),
            expected_minutes=27.0,
            actual_minutes=27.5,
            abs_minutes_error=0.5,
            expected_usage_pct=0.31,
            actual_usage_pct=0.22,
            abs_usage_error=0.09,
            expected_start_rate=0.41,
            actual_started=False,
            expected_close_rate=0.44,
            actual_closed=False,
            abs_touches_error=6.0,
            actual_touches=41.0,
            abs_passes_error=4.0,
            actual_passes=30.0,
            opportunity_score=0.57,
            confidence=0.49,
        )

        analysis = analyze_pregame_opportunity_misses(SimpleNamespace(rows=[start_miss, usage_miss]), top_n=10)
        labels = [bucket.label for bucket in analysis.buckets]

        self.assertIn("start_role_miss", labels)
        self.assertIn("usage_miss", labels)
        self.assertEqual(analysis.examples[0]["category"], "start_role_miss")


if __name__ == "__main__":
    unittest.main()
