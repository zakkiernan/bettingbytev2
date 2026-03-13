from __future__ import annotations

import unittest
from datetime import datetime

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

    def test_match_falls_back_to_initials_variant(self):
        rows = [
            {"game_id": "G1", "team_abbr": "MIL", "player_id": 203932, "player_name": "A.J. Green"},
        ]

        index = build_pregame_context_index(rows)
        match = match_pregame_context_row(index, game_id="G1", player_id=None, team_abbreviation="MIL", player_name="AJ Green")

        self.assertIsNotNone(match)
        self.assertEqual(match["player_id"], 203932)

    def test_match_falls_back_to_unique_game_name_when_team_missing(self):
        rows = [
            {"game_id": "G1", "team_abbr": "HOU", "player_id": 1631095, "player_name": "Jabari Smith Jr."},
        ]

        index = build_pregame_context_index(rows)
        match = match_pregame_context_row(index, game_id="G1", player_id=None, team_abbreviation=None, player_name="Jabari Smith")

        self.assertIsNotNone(match)
        self.assertEqual(match["player_id"], 1631095)

    def test_match_does_not_guess_when_game_name_fallback_is_ambiguous(self):
        rows = [
            {"game_id": "G1", "team_abbr": "AAA", "player_id": 1, "player_name": "Marcus Williams"},
            {"game_id": "G1", "team_abbr": "BBB", "player_id": 2, "player_name": "Marcus Williams"},
        ]

        index = build_pregame_context_index(rows)
        match = match_pregame_context_row(index, game_id="G1", player_id=None, team_abbreviation=None, player_name="Marcus Williams")

        self.assertIsNone(match)

    def test_match_selects_latest_row_at_or_before_cutoff(self):
        rows = [
            {"game_id": "G1", "team_abbr": "BOS", "player_id": "7", "player_name": "Jaylen Brown", "captured_at": datetime(2026, 3, 12, 17, 0, 0), "expected_start": False},
            {"game_id": "G1", "team_abbr": "BOS", "player_id": "7", "player_name": "Jaylen Brown", "captured_at": datetime(2026, 3, 12, 18, 0, 0), "expected_start": True},
        ]

        index = build_pregame_context_index(rows)
        early_match = match_pregame_context_row(
            index,
            game_id="G1",
            player_id="7",
            team_abbreviation="BOS",
            player_name="Jaylen Brown",
            captured_at=datetime(2026, 3, 12, 17, 30, 0),
        )
        late_match = match_pregame_context_row(
            index,
            game_id="G1",
            player_id="7",
            team_abbreviation="BOS",
            player_name="Jaylen Brown",
            captured_at=datetime(2026, 3, 12, 18, 30, 0),
        )

        self.assertFalse(early_match["expected_start"])
        self.assertTrue(late_match["expected_start"])


if __name__ == "__main__":
    unittest.main()
