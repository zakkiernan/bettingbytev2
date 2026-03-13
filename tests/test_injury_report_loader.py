from __future__ import annotations

import unittest
from datetime import date, datetime

from analytics.features_opportunity import TeamRolePrior, _build_official_injury_aggregates, _merge_context_aggregates
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


if __name__ == "__main__":
    unittest.main()
