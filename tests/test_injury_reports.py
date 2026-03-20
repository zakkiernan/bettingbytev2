from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import patch

from ingestion.injury_reports import (
    InjuryReportEntry,
    ParsedInjuryReport,
    PlayerLookupIndex,
    PlayerLookupRow,
    _resolve_player_id,
    backfill_injury_entry_player_ids,
    build_injury_report_url,
    default_backfill_report_times,
    normalize_injury_report,
    parse_injury_report_text,
)


SAMPLE_REPORT_TEXT = """
Injury
Report:
03/11/26
12:00
AM
Page
1
of
2
Game
Date
Game
Time
Matchup
Team
Player
Name
Current
Status
Reason
03/11/2026
07:30
(ET)
CLE@ORL
Cleveland
Cavaliers
Allen,
Jarrett
Out
Injury/Illness
-
Right
Knee;
Tendonitis
Ellis,
Keon
Available
Injury/Illness
-
Left
Index
Finger;
Fracture
Orlando
Magic
Isaac,
Jonathan
Questionable
Injury/Illness
-
Left
Knee;
Strain
08:00
(ET)
TOR@NOP
Toronto
Raptors
NOT
YET
SUBMITTED
New
Orleans
Pelicans
Alexander,
Trey
Out
G
League
-
Two-
Way
"""


BARE_MATCHUP_REPORT_TEXT = """
Injury
Report:
03/10/26
01:00
PM
Page
1
of
3
Game
Date
Game
Time
Matchup
Team
Player
Name
Current
Status
Reason
03/10/2026
07:30
(ET)
DAL@ATL
Dallas
Mavericks
Irving,
Kyrie
Out
Injury/Illness
-
Left
Knee;
Surgery
Atlanta
Hawks
Young,
Trae
Out
Injury/Illness
-
Right
Knee;
Injury
Management
DET@BKN
Detroit
Pistons
Thompson,
Ausar
Out
Injury/Illness
-
Right
Ankle;
Sprain
Brooklyn
Nets
NOT
YET
SUBMITTED
WAS@MIA
Washington
Wizards
George,
Kyshawn
Out
Injury/Illness
-
Left
Elbow;
Sprain
Miami
Heat
Herro,
Tyler
Questionable
Injury/Illness
-
Left
Quadriceps;
Soreness
"""

NICKNAME_ONLY_HOME_REPORT_TEXT = """
Injury
Report:
02/20/26
05:00
PM
Page
1
of
1
Game
Date
Game
Time
Matchup
Team
Player
Name
Current
Status
Reason
02/20/2026
07:30
(ET)
DAL@MIN
Dallas
Mavericks
Christie,
Max
Doubtful
Injury/Illness
-
Left
Ankle;
Sprain
Minnesota
Timberwolves
Zikarsky,
Rocco
Out
G
League
-
Two-
Way
"""

PARTIAL_SINGLE_TEAM_REPORT_TEXT = """
Injury
Report:
03/06/26
05:00
PM
Page
1
of
1
Game
Date
Game
Time
Matchup
Team
Player
Name
Current
Status
Reason
03/06/2026
10:00
(ET)
NOP@LAL
New
Orleans
Pelicans
Alexander,
Trey
Out
G
League
-
Two-
Way
Dickinson,
Hunter
Out
G
League
-
Two-
Way
"""



class InjuryReportParsingTests(unittest.TestCase):
    def test_build_injury_report_url(self):
        url = build_injury_report_url(date(2026, 3, 11), datetime.strptime("17:00", "%H:%M").time())
        self.assertEqual(
            url,
            "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-03-11_05_00PM.pdf",
        )

    def test_default_backfill_times_are_coarse_checkpoints(self):
        formatted = [value.strftime("%H:%M") for value in default_backfill_report_times()]
        self.assertEqual(formatted, ["00:00", "13:00", "17:00", "18:00", "19:00", "20:00", "21:00", "22:00"])

    def test_parse_injury_report_text_handles_players_and_not_yet_submitted(self):
        parsed = parse_injury_report_text(
            SAMPLE_REPORT_TEXT,
            pdf_url="https://example.test/report.pdf",
            pdf_sha256="abc123",
        )

        self.assertEqual(parsed.report_date, date(2026, 3, 11))
        self.assertEqual(parsed.report_time_et, "12:00 AM")
        self.assertEqual(len(parsed.entries), 5)

        first = parsed.entries[0]
        self.assertEqual(first.team_abbreviation, "CLE")
        self.assertEqual(first.player_name, "Jarrett Allen")
        self.assertEqual(first.current_status, "OUT")
        self.assertEqual(first.reason, "Injury/Illness - Right Knee; Tendonitis")

        second = parsed.entries[1]
        self.assertEqual(second.player_name, "Keon Ellis")
        self.assertEqual(second.current_status, "AVAILABLE")

        third = parsed.entries[2]
        self.assertEqual(third.team_abbreviation, "ORL")
        self.assertEqual(third.player_name, "Jonathan Isaac")

        fourth = parsed.entries[3]
        self.assertEqual(fourth.team_abbreviation, "TOR")
        self.assertIsNone(fourth.player_name)
        self.assertFalse(fourth.report_submitted)
        self.assertEqual(fourth.current_status, "NOT_YET_SUBMITTED")

        fifth = parsed.entries[4]
        self.assertEqual(fifth.team_abbreviation, "NOP")
        self.assertEqual(fifth.player_name, "Trey Alexander")
        self.assertEqual(fifth.current_status, "OUT")

    def test_parse_injury_report_text_handles_bare_matchup_boundaries(self):
        parsed = parse_injury_report_text(
            BARE_MATCHUP_REPORT_TEXT,
            pdf_url="https://example.test/bare.pdf",
            pdf_sha256="xyz789",
        )

        self.assertEqual(len(parsed.entries), 6)

        by_matchup = {(entry.matchup, entry.team_abbreviation): entry for entry in parsed.entries}
        self.assertEqual(by_matchup[("DAL@ATL", "DAL")].player_name, "Kyrie Irving")
        self.assertEqual(by_matchup[("DAL@ATL", "ATL")].player_name, "Trae Young")
        self.assertEqual(by_matchup[("DET@BKN", "DET")].player_name, "Ausar Thompson")
        self.assertEqual(by_matchup[("DET@BKN", "BKN")].current_status, "NOT_YET_SUBMITTED")
        self.assertEqual(by_matchup[("WAS@MIA", "WAS")].player_name, "Kyshawn George")
        self.assertEqual(by_matchup[("WAS@MIA", "MIA")].player_name, "Tyler Herro")
        self.assertIsNone(by_matchup[("DET@BKN", "DET")].game_time_et)
        self.assertNotIn("Brooklyn Nets", by_matchup[("DET@BKN", "DET")].reason or "")
        self.assertNotIn("Miami Heat", by_matchup[("WAS@MIA", "WAS")].reason or "")

    def test_parse_injury_report_text_handles_nickname_only_home_header(self):
        parsed = parse_injury_report_text(
            NICKNAME_ONLY_HOME_REPORT_TEXT,
            pdf_url="https://example.test/nickname.pdf",
            pdf_sha256="nick123",
        )

        self.assertEqual(len(parsed.entries), 2)
        by_matchup = {(entry.matchup, entry.team_abbreviation): entry for entry in parsed.entries}
        self.assertEqual(by_matchup[("DAL@MIN", "DAL")].player_name, "Max Christie")
        self.assertEqual(by_matchup[("DAL@MIN", "MIN")].player_name, "Rocco Zikarsky")

    def test_parse_injury_report_text_keeps_partial_single_team_segment(self):
        parsed = parse_injury_report_text(
            PARTIAL_SINGLE_TEAM_REPORT_TEXT,
            pdf_url="https://example.test/partial.pdf",
            pdf_sha256="partial123",
        )

        self.assertEqual(len(parsed.entries), 2)
        self.assertTrue(all(entry.team_abbreviation == "NOP" for entry in parsed.entries))
        self.assertEqual(parsed.entries[0].player_name, "Trey Alexander")
        self.assertEqual(parsed.entries[1].player_name, "Hunter Dickinson")

    @patch("ingestion.injury_reports._load_player_lookup")
    @patch("ingestion.injury_reports._load_team_lookup")
    def test_normalize_injury_report_maps_ids_and_payload(self, mock_team_lookup, mock_player_lookup):
        mock_team_lookup.return_value = {
            "CLE": {"team_id": "1610612739", "team_name": "Cleveland Cavaliers"},
            "ORL": {"team_id": "1610612753", "team_name": "Orlando Magic"},
        }
        mock_player_lookup.return_value = PlayerLookupIndex(
            exact_lookup={"jarrett allen": "1628386"},
            player_team_lookup={"1628386": "CLE"},
            player_rows=[
                PlayerLookupRow(
                    player_id="1628386",
                    full_name="Jarrett Allen",
                    team_abbreviation="CLE",
                    normalized_name="jarrett allen",
                    tokens=("jarrett", "allen"),
                )
            ],
        )
        parsed = ParsedInjuryReport(
            report_date=date(2026, 3, 11),
            report_time_et="12:00 AM",
            report_datetime_utc=datetime(2026, 3, 11, 5, 0, 0),
            pdf_url="https://example.test/report.pdf",
            pdf_sha256="abc123",
            raw_text="raw",
            entries=[
                InjuryReportEntry(
                    game_date=date(2026, 3, 11),
                    game_time_et="07:30 (ET)",
                    matchup="CLE@ORL",
                    team_abbreviation="CLE",
                    team_name="Cleveland Cavaliers",
                    player_name="Jarrett Allen",
                    current_status="OUT",
                    reason="Injury/Illness - Right Knee; Tendonitis",
                    report_submitted=True,
                ),
                InjuryReportEntry(
                    game_date=date(2026, 3, 11),
                    game_time_et="07:30 (ET)",
                    matchup="CLE@ORL",
                    team_abbreviation="ORL",
                    team_name="Orlando Magic",
                    player_name=None,
                    current_status="NOT_YET_SUBMITTED",
                    reason=None,
                    report_submitted=False,
                ),
            ],
        )

        report_row, entry_rows, payload = normalize_injury_report(parsed)

        self.assertEqual(report_row["entry_count"], 2)
        self.assertEqual(entry_rows[0]["team_id"], "1610612739")
        self.assertEqual(entry_rows[0]["player_id"], "1628386")
        self.assertEqual(entry_rows[1]["player_id"], None)
        self.assertEqual(payload["payload_type"], "injury_report_pdf")
        self.assertEqual(payload["context"]["entry_count"], 2)

    def test_resolve_player_id_handles_alias_name_order_variant(self):
        lookup = PlayerLookupIndex(
            exact_lookup={"yang hansen": "1642905"},
            player_team_lookup={"1642905": "POR"},
            player_rows=[
                PlayerLookupRow(
                    player_id="1642905",
                    full_name="Yang Hansen",
                    team_abbreviation="POR",
                    normalized_name="yang hansen",
                    tokens=("yang", "hansen"),
                )
            ],
        )

        self.assertEqual(
            _resolve_player_id("Hansen Yang", lookup, team_abbreviation="POR"),
            "1642905",
        )

    def test_resolve_player_id_uses_team_scoped_fuzzy_fallback(self):
        lookup = PlayerLookupIndex(
            exact_lookup={},
            player_team_lookup={"1628983": "OKC"},
            player_rows=[
                PlayerLookupRow(
                    player_id="1628983",
                    full_name="Shai Gilgeous Alexander",
                    team_abbreviation="OKC",
                    normalized_name="shai gilgeous alexander",
                    tokens=("shai", "gilgeous", "alexander"),
                )
            ],
        )

        self.assertEqual(
            _resolve_player_id("Shai Alexander", lookup, team_abbreviation="OKC"),
            "1628983",
        )
        self.assertIsNone(_resolve_player_id("Shai Alexander", lookup, team_abbreviation="BOS"))

    def test_backfill_injury_entry_player_ids_updates_only_named_null_rows(self):
        rows = [
            InjuryReportEntry(
                game_date=date(2026, 3, 11),
                game_time_et="07:30 (ET)",
                matchup="CLE@ORL",
                team_abbreviation="CLE",
                team_name="Cleveland Cavaliers",
                player_name="Jarrett Allen",
                current_status="OUT",
                reason="Injury/Illness - Right Knee; Tendonitis",
                report_submitted=True,
            ),
            InjuryReportEntry(
                game_date=date(2026, 3, 11),
                game_time_et="07:30 (ET)",
                matchup="POR@LAL",
                team_abbreviation="POR",
                team_name="Portland Trail Blazers",
                player_name="Hansen Yang",
                current_status="OUT",
                reason="Injury/Illness - Ankle",
                report_submitted=True,
            ),
        ]
        fake_db_rows = []
        for entry in rows:
            fake_db_rows.append(
                type(
                    "FakeEntryRow",
                    (),
                    {
                        "player_id": None,
                        "player_name": entry.player_name,
                        "team_abbreviation": entry.team_abbreviation,
                    },
                )()
            )

        class FakeQuery:
            def __init__(self, query_rows):
                self.query_rows = query_rows

            def filter(self, *args, **kwargs):
                return self

            def all(self):
                return self.query_rows

        class FakeSession:
            def __init__(self, query_rows):
                self.query_rows = query_rows

            def query(self, model):
                return FakeQuery(self.query_rows)

        @contextmanager
        def fake_session_scope():
            yield FakeSession(fake_db_rows)

        lookup = PlayerLookupIndex(
            exact_lookup={
                "jarrett allen": "1628386",
                "yang hansen": "1642905",
            },
            player_team_lookup={
                "1628386": "CLE",
                "1642905": "POR",
            },
            player_rows=[
                PlayerLookupRow(
                    player_id="1628386",
                    full_name="Jarrett Allen",
                    team_abbreviation="CLE",
                    normalized_name="jarrett allen",
                    tokens=("jarrett", "allen"),
                ),
                PlayerLookupRow(
                    player_id="1642905",
                    full_name="Yang Hansen",
                    team_abbreviation="POR",
                    normalized_name="yang hansen",
                    tokens=("yang", "hansen"),
                ),
            ],
        )

        with patch("ingestion.injury_reports._load_player_lookup", return_value=lookup), patch(
            "ingestion.injury_reports.session_scope",
            fake_session_scope,
        ):
            result = backfill_injury_entry_player_ids()

        self.assertEqual(result, {"total_null": 2, "resolved": 2, "still_null": 0})
        self.assertEqual(fake_db_rows[0].player_id, "1628386")
        self.assertEqual(fake_db_rows[1].player_id, "1642905")


if __name__ == "__main__":
    unittest.main()
