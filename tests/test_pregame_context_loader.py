from __future__ import annotations

import unittest

from analytics.pregame_context_loader import build_pregame_context_index, match_pregame_context_row


class PregameContextLoaderTests(unittest.TestCase):
    def test_match_prefers_exact_player_id(self):
        rows = [
            {"game_id": "G1", "team_abbr": "ORL", "player_id": 1, "player_name": "Wendell Carter Jr."},
            {"game_id": "G1", "team_abbr": "ORL", "player_id": 2, "player_name": "Paolo Banchero"},
        ]

        index = build_pregame_context_index(rows)
        match = match_pregame_context_row(index, game_id="G1", player_id="2", team_abbreviation="ORL", player_name="Paolo Banchero")

        self.assertIsNotNone(match)
        self.assertEqual(match["player_id"], 2)

    def test_match_falls_back_to_team_name_suffix_variant(self):
        rows = [
            {"game_id": "G1", "team_abbr": "NOP", "player_id": 1630530, "player_name": "Trey Murphy III"},
        ]

        index = build_pregame_context_index(rows)
        match = match_pregame_context_row(index, game_id="G1", player_id=None, team_abbreviation="NOP", player_name="Trey Murphy")

        self.assertIsNotNone(match)
        self.assertEqual(match["player_id"], 1630530)


if __name__ == "__main__":
    unittest.main()
