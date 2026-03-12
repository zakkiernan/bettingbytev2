from __future__ import annotations

import unittest

from nbarotations_scraper.pregame_feature_view import TeamPriors, build_pregame_feature_rows


class TestPregameFeatureView(unittest.TestCase):
    def test_build_rows_with_priors(self):
        payload = {
            "fetched_at_utc": "2026-03-12T00:00:00Z",
            "games": [
                {
                    "game_id": "G1",
                    "away_team": {"team_abbr": "AAA", "team_id": 1},
                    "home_team": {"team_abbr": "BBB", "team_id": 2},
                    "sources_present": {"nba_live_boxscore": True, "rotowire_lineups": True},
                    "availability": [
                        {
                            "team_abbr": "AAA",
                            "team_id": 1,
                            "player_id": 101,
                            "player_name": "A",
                            "status": "ACTIVE",
                            "starter_flag": True,
                        },
                        {
                            "team_abbr": "AAA",
                            "team_id": 1,
                            "player_id": 102,
                            "player_name": "B",
                            "status": "INACTIVE",
                            "starter_flag": False,
                        },
                    ],
                    "projected_starters": [
                        {
                            "team_abbr": "AAA",
                            "team_id": 1,
                            "player_id": 101,
                            "player_name": "A",
                            "lineup_confirmed": True,
                            "play_probability_hint": 100,
                        }
                    ],
                    "projected_absences": [
                        {
                            "team_abbr": "AAA",
                            "team_id": 1,
                            "player_id": 102,
                            "player_name": "B",
                            "play_probability_hint": 0,
                            "injury_tag": "Out",
                        }
                    ],
                }
            ],
        }

        priors = {
            1: TeamPriors(
                top7_player_ids={101, 102},
                top9_player_ids={101, 102},
                high_usage_player_ids={102},
                primary_ballhandler_ids={101},
                frontcourt_rotation_player_ids={102},
                baseline_minutes_by_player_id={102: 30.0},
                baseline_usage_by_player_id={102: 0.28},
            )
        }

        rows = build_pregame_feature_rows(payload, priors_by_team_id=priors)
        self.assertEqual(len(rows), 2)

        r101 = [r for r in rows if r["player_id"] == 101][0]
        self.assertTrue(r101["expected_start"])
        self.assertEqual(r101["teammate_out_count_top7"], 1)
        self.assertEqual(r101["missing_high_usage_teammates"], 1)
        self.assertAlmostEqual(r101["vacated_minutes_proxy"], 30.0)
        self.assertAlmostEqual(r101["vacated_usage_proxy"], 0.28)
        self.assertAlmostEqual(r101["pregame_context_confidence"], 0.95)



    def test_build_rows_for_projected_only_game_and_projected_absence_context(self):
        payload = {
            "fetched_at_utc": "2026-03-12T00:00:00Z",
            "games": [
                {
                    "game_id": "G2",
                    "away_team": {"team_abbr": "HOU", "team_id": 1610612745},
                    "home_team": {"team_abbr": "DEN", "team_id": 1610612743},
                    "sources_present": {"nba_live_boxscore": False, "rotowire_lineups": True},
                    "availability": [],
                    "projected_starters": [
                        {
                            "team_abbr": "HOU",
                            "team_id": 1610612745,
                            "player_id": None,
                            "player_name": "Amen Thompson",
                            "position": "G",
                            "lineup_confirmed": False,
                            "play_probability_hint": 100,
                        }
                    ],
                    "projected_absences": [
                        {
                            "team_abbr": "HOU",
                            "team_id": 1610612745,
                            "player_id": None,
                            "player_name": "Fred VanVleet",
                            "position": "PG",
                            "play_probability_hint": 0,
                            "injury_tag": "Out",
                            "availability_bucket": "may_not_play",
                        }
                    ],
                }
            ],
        }

        rows = build_pregame_feature_rows(payload, priors_by_team_id={})

        self.assertEqual(len(rows), 2)
        amen = [row for row in rows if row["player_name"] == "Amen Thompson"][0]
        self.assertTrue(amen["expected_start"])
        self.assertTrue(amen["projected_available"])
        self.assertEqual(amen["teammate_out_count_top7"], 1)
        self.assertGreater(amen["vacated_minutes_proxy"], 0.0)
        self.assertGreater(amen["vacated_usage_proxy"], 0.0)
        self.assertAlmostEqual(amen["pregame_context_confidence"], 0.55)

if __name__ == "__main__":
    unittest.main()
