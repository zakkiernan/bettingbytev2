from __future__ import annotations

import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from nbarotations_scraper.pregame_context import (
    PregameContextIngestor,
    _build_roster_lookup_by_team,
    _extract_team_availability,
    TeamGameRef,
    _lookup_roster_row,
    _normalize_name,
    _parse_rotowire_team_list,
)


class TestPregameContextParsing(unittest.TestCase):
    def test_fetch_uses_supplied_schedule_refs(self):
        ingestor = PregameContextIngestor()
        schedule_refs = [
            TeamGameRef(
                game_id="G1",
                away_abbr="OKC",
                home_abbr="BOS",
                away_team_id=1610612760,
                home_team_id=1610612738,
                game_time_utc="2026-03-12T23:30:00Z",
                game_status=1,
                game_status_text="scheduled",
            )
        ]
        with patch.object(PregameContextIngestor, "_fetch_nba_schedule_refs", side_effect=AssertionError("should not fetch schedule")), patch.object(
            PregameContextIngestor, "_fetch_rotowire_games", return_value=[]
        ), patch.object(PregameContextIngestor, "_build_game_payload", return_value={"game_id": "G1"}):
            payload = ingestor.fetch(schedule_refs=schedule_refs)

        self.assertEqual(payload["games"], [{"game_id": "G1"}])

    def test_parse_rotowire_team_list(self):
        html = """
        <ul class="lineup__list is-visit">
          <li class="lineup__status is-confirmed">Confirmed Lineup</li>
          <li class="lineup__player is-pct-play-100" title="Very Likely To Play">
            <div class="lineup__pos">PG</div>
            <a title="Jalen Brunson">J. Brunson</a>
          </li>
          <li class="lineup__player is-pct-play-75" title="Likely To Play">
            <div class="lineup__pos">SG</div>
            <a title="Josh Hart">J. Hart</a>
            <span class="lineup__inj">Questionable</span>
          </li>
          <li class="lineup__title is-middle">MAY NOT PLAY</li>
          <li class="lineup__player is-pct-play-0 has-injury-status" title="Very Unlikely To Play">
            <div class="lineup__pos">C</div>
            <a title="Mitchell Robinson">M. Robinson</a>
            <span class="lineup__inj">Out</span>
          </li>
        </ul>
        """
        soup = BeautifulSoup(html, "lxml")
        starters, may_not_play = _parse_rotowire_team_list(soup.select_one("ul"))

        self.assertEqual(len(starters), 2)
        self.assertEqual(starters[0].name, "Jalen Brunson")
        self.assertEqual(starters[0].position, "PG")
        self.assertEqual(starters[0].play_probability_hint, 100)

        self.assertEqual(starters[1].injury_tag, "Questionable")
        self.assertEqual(starters[1].play_probability_hint, 75)

        self.assertEqual(len(may_not_play), 1)
        self.assertEqual(may_not_play[0].name, "Mitchell Robinson")
        self.assertEqual(may_not_play[0].injury_tag, "Out")

    def test_extract_team_availability(self):
        team_raw = {
            "teamId": 1610612762,
            "teamTricode": "UTA",
            "players": [
                {
                    "personId": 1,
                    "name": "Starter Guy",
                    "position": "PG",
                    "status": "ACTIVE",
                    "starter": "1",
                },
                {
                    "personId": 2,
                    "name": "Bench Out",
                    "position": "F",
                    "status": "INACTIVE",
                    "starter": "0",
                    "notPlayingReason": "INACTIVE_INJURY",
                    "notPlayingDescription": "Knee",
                },
            ],
        }
        out = _extract_team_availability(team_raw)

        self.assertEqual(len(out["availability"]), 2)
        self.assertEqual(len(out["official_starters"]), 1)
        self.assertEqual(out["official_starters"][0]["player_name"], "Starter Guy")
        self.assertEqual(out["availability"][1]["not_playing_reason"], "INACTIVE_INJURY")


    def test_lookup_roster_row_handles_suffix_variants(self):
        availability = [
            {"team_abbr": "ORL", "team_id": 1610612753, "player_id": 203920, "player_name": "Wendell Carter Jr."},
            {"team_abbr": "NOP", "team_id": 1610612740, "player_id": 1630530, "player_name": "Trey Murphy III"},
        ]

        lookup = _build_roster_lookup_by_team(availability)

        self.assertEqual(_lookup_roster_row("ORL", "Wendell Carter", lookup)["player_id"], 203920)
        self.assertEqual(_lookup_roster_row("NOP", "Trey Murphy", lookup)["player_id"], 1630530)

    def test_normalize_name(self):
        self.assertEqual(_normalize_name("Jrue Holiday"), "jrue holiday")
        self.assertEqual(_normalize_name("Karl-Anthony Towns"), "karl anthony towns")
        self.assertEqual(_normalize_name("Nicolas Claxton Jr."), "nicolas claxton jr")


if __name__ == "__main__":
    unittest.main()
