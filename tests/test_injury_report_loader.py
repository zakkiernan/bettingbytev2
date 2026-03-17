from __future__ import annotations

import unittest
from datetime import date, datetime
from types import SimpleNamespace

from analytics.features_opportunity import (
    PregameFeatureSeed,
    TeamPlayerRoleProfile,
    TeamRolePrior,
    _build_absence_impact_index,
    _build_official_injury_aggregates,
    _merge_context_aggregates,
)
from analytics.injury_report_loader import build_official_injury_report_index, get_official_team_summary, match_official_injury_row


class OfficialInjuryReportLoaderTests(unittest.TestCase):
    def test_match_prefers_exact_player_id_and_builds_team_summary(self):
        rows = [
            {
                "game_date": date(2026, 3, 12),
                "team_abbreviation": "BOS",
                "player_id": "1",
                "player_name": "Jaylen Brown",
                "current_status": "Questionable",
                "reason": "Injury/Illness - Right Knee; Soreness",
                "report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0),
                "report_submitted": True,
            },
            {
                "game_date": date(2026, 3, 12),
                "team_abbreviation": "BOS",
                "player_id": "2",
                "player_name": "Jrue Holiday",
                "current_status": "Out",
                "reason": "Injury/Illness - Finger",
                "report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0),
                "report_submitted": True,
            },
        ]

        index = build_official_injury_report_index(rows)
        match = match_official_injury_row(
            index,
            game_date=date(2026, 3, 12),
            player_id="1",
            team_abbreviation="BOS",
            player_name="Jaylen Brown",
        )
        summary = get_official_team_summary(index, game_date=date(2026, 3, 12), team_abbreviation="BOS")

        self.assertIsNotNone(match)
        self.assertEqual(match["player_name"], "Jaylen Brown")
        self.assertIsNotNone(summary)
        self.assertEqual(summary["out_count"], 1)
        self.assertEqual(summary["questionable_count"], 1)
        self.assertEqual(summary["player_entry_count"], 2)

    def test_match_falls_back_to_suffix_variant(self):
        rows = [
            {
                "game_date": date(2026, 3, 12),
                "team_abbreviation": "NOP",
                "player_id": "1630530",
                "player_name": "Trey Murphy III",
                "current_status": "Available",
                "reason": None,
                "report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0),
                "report_submitted": True,
            }
        ]

        index = build_official_injury_report_index(rows)
        match = match_official_injury_row(
            index,
            game_date=date(2026, 3, 12),
            player_id=None,
            team_abbreviation="NOP",
            player_name="Trey Murphy",
        )

        self.assertIsNotNone(match)
        self.assertEqual(match["player_id"], "1630530")

    def test_match_falls_back_to_initials_variant(self):
        rows = [
            {
                "game_date": date(2026, 3, 12),
                "team_abbreviation": "MIL",
                "player_id": "203932",
                "player_name": "A.J. Green",
                "current_status": "Available",
                "reason": None,
                "report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0),
                "report_submitted": True,
            }
        ]

        index = build_official_injury_report_index(rows)
        match = match_official_injury_row(
            index,
            game_date=date(2026, 3, 12),
            player_id=None,
            team_abbreviation="MIL",
            player_name="AJ Green",
        )

        self.assertIsNotNone(match)
        self.assertEqual(match["player_id"], "203932")


class OfficialInjuryOpportunityFeatureTests(unittest.TestCase):
    def test_official_injury_aggregates_map_status_and_team_counts(self):
        aggregates = _build_official_injury_aggregates(
            {
                "current_status": "Questionable",
                "reason": "Injury/Illness - Right Knee; Soreness",
                "report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0),
            },
            {
                "out_count": 2,
                "doubtful_count": 1,
                "questionable_count": 1,
                "report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0),
            },
            captured_at=datetime(2026, 3, 12, 18, 0, 0),
        )

        self.assertEqual(aggregates["official_injury_status"], "QUESTIONABLE")
        self.assertAlmostEqual(aggregates["late_scratch_risk"], 0.65)
        self.assertIsNone(aggregates["official_available"])
        self.assertEqual(aggregates["official_teammate_out_count"], 2.0)
        self.assertEqual(aggregates["official_teammate_doubtful_count"], 1.0)
        self.assertEqual(aggregates["official_teammate_questionable_count"], 1.0)
        self.assertIsNone(aggregates["teammate_out_count_top7"])
        self.assertGreater(aggregates["pregame_context_confidence"], 0.8)

    def test_team_summary_only_is_weak_context_without_fake_top7_counts(self):
        aggregates = _build_official_injury_aggregates(
            None,
            {
                "out_count": 4,
                "doubtful_count": 2,
                "questionable_count": 1,
                "report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0),
            },
            captured_at=datetime(2026, 3, 12, 18, 0, 0),
        )

        self.assertEqual(aggregates["official_teammate_out_count"], 4.0)
        self.assertIsNone(aggregates["teammate_out_count_top7"])
        self.assertLessEqual(aggregates["pregame_context_confidence"], 0.25)


    def test_merge_context_lets_official_out_override_conflicting_pregame_availability(self):
        merged = _merge_context_aggregates(
            {
                "expected_start": True,
                "starter_confidence": 0.9,
                "official_available": True,
                "projected_available": True,
                "official_starter_flag": True,
                "late_scratch_risk": 0.1,
                "teammate_out_count_top7": 1.0,
                "teammate_out_count_top9": 1.0,
                "pregame_context_confidence": 0.8,
            },
            {
                "official_injury_status": "OUT",
                "official_injury_reason": "Injury/Illness - Ankle",
                "official_report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0),
                "official_teammate_out_count": 2.0,
                "official_teammate_doubtful_count": 1.0,
                "official_teammate_questionable_count": 0.0,
                "official_available": False,
                "late_scratch_risk": 1.0,
                "pregame_context_confidence": 0.7,
            },
        )

        self.assertFalse(merged["expected_start"])
        self.assertEqual(merged["starter_confidence"], 0.0)
        self.assertFalse(merged["official_available"])
        self.assertFalse(merged["projected_available"])
        self.assertFalse(merged["official_starter_flag"])
        self.assertEqual(merged["official_injury_status"], "OUT")
        self.assertAlmostEqual(merged["late_scratch_risk"], 1.0)
        self.assertAlmostEqual(merged["teammate_out_count_top7"], 1.0)
        self.assertAlmostEqual(merged["pregame_context_confidence"], 0.8)


    def test_role_based_injury_context_uses_team_priors(self):
        aggregates = _build_official_injury_aggregates(
            None,
            {
                "out_count": 1,
                "doubtful_count": 0,
                "questionable_count": 1,
                "report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0),
            },
            team_rows=[
                {"player_id": "2", "current_status": "OUT", "report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0)},
                {"player_id": "3", "current_status": "QUESTIONABLE", "report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0)},
            ],
            team_role_prior=TeamRolePrior(
                team_id="1610612738",
                team_abbreviation="BOS",
                top7_player_ids={"2", "3"},
                top9_player_ids={"2", "3"},
                high_usage_player_ids={"2"},
                primary_ballhandler_ids={"3"},
                frontcourt_player_ids={"2"},
                player_role_profiles={
                    "1": TeamPlayerRoleProfile(
                        player_id="1",
                        baseline_minutes=30.0,
                        baseline_usage=0.22,
                        baseline_passes=22.0,
                        baseline_touches=40.0,
                        baseline_rebounds=8.0,
                        baseline_blocks=1.2,
                        baseline_threes=1.0,
                        start_rate=0.7,
                        close_rate=0.7,
                        ballhandler_score=0.35,
                        usage_score=0.65,
                        frontcourt_score=0.85,
                    ),
                    "2": TeamPlayerRoleProfile(
                        player_id="2",
                        baseline_minutes=35.0,
                        baseline_usage=0.29,
                        baseline_passes=18.0,
                        baseline_touches=42.0,
                        baseline_rebounds=11.0,
                        baseline_blocks=1.8,
                        baseline_threes=0.8,
                        start_rate=0.9,
                        close_rate=0.8,
                        ballhandler_score=0.20,
                        usage_score=0.90,
                        frontcourt_score=0.95,
                    ),
                    "3": TeamPlayerRoleProfile(
                        player_id="3",
                        baseline_minutes=31.0,
                        baseline_usage=0.22,
                        baseline_passes=55.0,
                        baseline_touches=74.0,
                        baseline_rebounds=4.0,
                        baseline_blocks=0.2,
                        baseline_threes=2.0,
                        start_rate=0.8,
                        close_rate=0.9,
                        ballhandler_score=0.95,
                        usage_score=0.72,
                        frontcourt_score=0.15,
                    ),
                },
                baseline_minutes_by_player_id={"2": 35.0, "3": 31.0},
                baseline_usage_by_player_id={"2": 0.29, "3": 0.22},
            ),
            player_id="1",
            captured_at=datetime(2026, 3, 12, 18, 0, 0),
        )

        self.assertGreater(aggregates["teammate_out_count_top7"], 1.0)
        self.assertGreater(aggregates["missing_high_usage_teammates"], 0.0)
        self.assertTrue(aggregates["missing_primary_ballhandler"])
        self.assertGreater(aggregates["vacated_minutes_proxy"], 40.0)
        self.assertGreater(aggregates["vacated_usage_proxy"], 0.3)


    def test_absence_impact_context_attaches_empirical_bonus_fields(self):
        absence_index = _build_absence_impact_index([
            SimpleNamespace(
                team_abbreviation="BOS",
                beneficiary_player_id="1",
                beneficiary_player_name="Target Player",
                source_player_id="2",
                source_player_name="Source Star",
                window_end_date=date(2026, 3, 10),
                minutes_delta=5.0,
                usage_delta=0.03,
                touches_delta=8.0,
                passes_delta=4.0,
                impact_score=2.4,
                sample_confidence=0.6,
                source_out_game_count=4,
                updated_at=datetime(2026, 3, 10, 12, 0, 0),
                created_at=datetime(2026, 3, 10, 12, 0, 0),
            )
        ])

        aggregates = _build_official_injury_aggregates(
            None,
            {
                "out_count": 1,
                "doubtful_count": 0,
                "questionable_count": 0,
                "report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0),
            },
            team_rows=[
                {
                    "player_id": "2",
                    "player_name": "Source Star",
                    "current_status": "OUT",
                    "report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0),
                }
            ],
            player_id="1",
            team_abbreviation="BOS",
            absence_impact_index=absence_index,
            captured_at=datetime(2026, 3, 12, 18, 0, 0),
        )

        self.assertAlmostEqual(aggregates["absence_impact_minutes_delta"], 3.0)
        self.assertAlmostEqual(aggregates["absence_impact_usage_delta"], 0.018)
        self.assertAlmostEqual(aggregates["absence_impact_touches_delta"], 4.8)
        self.assertAlmostEqual(aggregates["absence_impact_passes_delta"], 2.4)
        self.assertAlmostEqual(aggregates["absence_impact_sample_confidence"], 0.6)
        self.assertEqual(aggregates["absence_impact_source_count"], 1.0)

    def test_build_opportunity_features_labels_player_level_injury_only_fallback(self):
        seed = PregameFeatureSeed(
            game_id="002TEST",
            player_id="123",
            player_name="Test Player",
            stat_type="points",
            line=24.5,
            over_odds=-110,
            under_odds=-110,
            captured_at=datetime(2026, 3, 12, 18, 0, 0),
            game_date=datetime(2026, 3, 12, 19, 0, 0),
            team_abbreviation="BOS",
            opponent_abbreviation="NYK",
            is_home=True,
            days_rest=1,
            back_to_back=False,
            recent_logs=[],
            advanced_rows=[],
            rotation_rows=[],
            team_defense=None,
            opponent_defense=None,
            league_avg_def_rating=None,
            league_avg_pace=None,
            league_avg_opponent_points=None,
            pregame_context_row=None,
            official_injury_row={
                "current_status": "QUESTIONABLE",
                "reason": "Injury/Illness - Ankle",
                "report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0),
            },
            official_injury_team_summary={
                "out_count": 1,
                "doubtful_count": 0,
                "questionable_count": 1,
                "report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0),
            },
        )

        features = seed.build_opportunity_features()

        self.assertFalse(features.pregame_context_attached)
        self.assertTrue(features.official_injury_attached)
        self.assertEqual(features.context_source, "official_injury_player")
        self.assertLessEqual(features.pregame_context_confidence, 0.55)
        self.assertEqual(features.official_injury_status, "QUESTIONABLE")

    def test_build_opportunity_features_labels_team_level_injury_only_fallback(self):
        seed = PregameFeatureSeed(
            game_id="002TEST",
            player_id="123",
            player_name="Test Player",
            stat_type="points",
            line=24.5,
            over_odds=-110,
            under_odds=-110,
            captured_at=datetime(2026, 3, 12, 18, 0, 0),
            game_date=datetime(2026, 3, 12, 19, 0, 0),
            team_abbreviation="BOS",
            opponent_abbreviation="NYK",
            is_home=True,
            days_rest=1,
            back_to_back=False,
            recent_logs=[],
            advanced_rows=[],
            rotation_rows=[],
            team_defense=None,
            opponent_defense=None,
            league_avg_def_rating=None,
            league_avg_pace=None,
            league_avg_opponent_points=None,
            pregame_context_row=None,
            official_injury_row=None,
            official_injury_team_summary={
                "out_count": 3,
                "doubtful_count": 1,
                "questionable_count": 2,
                "report_datetime_utc": datetime(2026, 3, 12, 17, 0, 0),
            },
        )

        features = seed.build_opportunity_features()

        self.assertFalse(features.pregame_context_attached)
        self.assertTrue(features.official_injury_attached)
        self.assertEqual(features.context_source, "official_injury_team")
        self.assertLessEqual(features.pregame_context_confidence, 0.35)
        self.assertIsNone(features.expected_start)


if __name__ == "__main__":
    unittest.main()
