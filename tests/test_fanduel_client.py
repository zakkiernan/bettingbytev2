from __future__ import annotations

import unittest
from datetime import datetime

from ingestion import fanduel_client


class FanDuelPropParsingTests(unittest.TestCase):
    def test_parse_event_props_filters_players_outside_mapped_game(self) -> None:
        event_mapping = {
            "event_id": "35369115",
            "event_name": "Los Angeles Lakers @ Houston Rockets",
            "nba_game_id": "0022500989",
            "away_team_abbreviation": "LAL",
            "home_team_abbreviation": "HOU",
        }
        raw_data = {
            "attachments": {
                "markets": {
                    "1": {
                        "marketName": "LeBron James - Points",
                        "runners": [
                            {
                                "result": {"type": "OVER"},
                                "handicap": 18.5,
                                "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": -102}},
                            },
                            {
                                "result": {"type": "UNDER"},
                                "handicap": 18.5,
                                "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": -118}},
                            },
                        ],
                    },
                    "2": {
                        "marketName": "Kevin Durant - Points",
                        "runners": [
                            {
                                "result": {"type": "OVER"},
                                "handicap": 26.5,
                                "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": -110}},
                            },
                            {
                                "result": {"type": "UNDER"},
                                "handicap": 26.5,
                                "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": -110}},
                            },
                        ],
                    },
                }
            }
        }

        props = fanduel_client.parse_event_props(
            event_mapping,
            raw_data,
            player_id_map={
                "LeBron James": "2544",
                "Kevin Durant": "201142",
            },
            player_team_context={
                "2544": "LAL",
                "201142": "PHX",
            },
            captured_at=datetime(2026, 3, 16, 4, 35, 36),
        )

        self.assertEqual(len(props), 1)
        self.assertEqual(props[0]["player_name"], "LeBron James")
        self.assertEqual(props[0]["team"], "LAL")
        self.assertEqual(props[0]["opponent"], "HOU")


if __name__ == "__main__":
    unittest.main()
