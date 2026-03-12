from __future__ import annotations

import unittest
from datetime import date, datetime
from types import SimpleNamespace

from analytics.evaluation import _build_historical_injury_report_indexes, _select_historical_injury_index
from analytics.injury_report_loader import get_official_team_summary, match_official_injury_row


class HistoricalInjuryEvaluationTests(unittest.TestCase):
    def test_select_historical_injury_index_uses_latest_report_before_tip(self):
        rows = [
            SimpleNamespace(
                report_id=10,
                report_datetime_utc=datetime(2026, 1, 5, 18, 0, 0),
                game_date=date(2026, 1, 5),
                matchup='NYK@BOS',
                team_abbreviation='BOS',
                team_name='Boston Celtics',
                player_id='1627759',
                player_name='Jaylen Brown',
                current_status='QUESTIONABLE',
                reason='Knee',
                report_submitted=True,
            ),
            SimpleNamespace(
                report_id=10,
                report_datetime_utc=datetime(2026, 1, 5, 18, 0, 0),
                game_date=date(2026, 1, 5),
                matchup='NYK@BOS',
                team_abbreviation='BOS',
                team_name='Boston Celtics',
                player_id='1',
                player_name='Teammate One',
                current_status='OUT',
                reason='Ankle',
                report_submitted=True,
            ),
            SimpleNamespace(
                report_id=11,
                report_datetime_utc=datetime(2026, 1, 5, 19, 0, 0),
                game_date=date(2026, 1, 5),
                matchup='NYK@BOS',
                team_abbreviation='BOS',
                team_name='Boston Celtics',
                player_id='1627759',
                player_name='Jaylen Brown',
                current_status='AVAILABLE',
                reason=None,
                report_submitted=True,
            ),
            SimpleNamespace(
                report_id=11,
                report_datetime_utc=datetime(2026, 1, 5, 19, 0, 0),
                game_date=date(2026, 1, 5),
                matchup='NYK@BOS',
                team_abbreviation='BOS',
                team_name='Boston Celtics',
                player_id='2',
                player_name='Teammate Two',
                current_status='OUT',
                reason='Hamstring',
                report_submitted=True,
            ),
        ]

        rows_by_report_id, report_refs_by_game_date = _build_historical_injury_report_indexes(rows)
        index_cache = {}

        early_index = _select_historical_injury_index(
            game_date=date(2026, 1, 5),
            captured_at=datetime(2026, 1, 5, 18, 30, 0),
            rows_by_report_id=rows_by_report_id,
            report_refs_by_game_date=report_refs_by_game_date,
            index_cache=index_cache,
        )
        late_index = _select_historical_injury_index(
            game_date=date(2026, 1, 5),
            captured_at=datetime(2026, 1, 5, 19, 30, 0),
            rows_by_report_id=rows_by_report_id,
            report_refs_by_game_date=report_refs_by_game_date,
            index_cache=index_cache,
        )

        early_match = match_official_injury_row(
            early_index,
            game_date=date(2026, 1, 5),
            player_id='1627759',
            team_abbreviation='BOS',
            player_name='Jaylen Brown',
        )
        late_match = match_official_injury_row(
            late_index,
            game_date=date(2026, 1, 5),
            player_id='1627759',
            team_abbreviation='BOS',
            player_name='Jaylen Brown',
        )
        late_summary = get_official_team_summary(
            late_index,
            game_date=date(2026, 1, 5),
            team_abbreviation='BOS',
        )

        self.assertEqual(early_match['current_status'], 'QUESTIONABLE')
        self.assertEqual(late_match['current_status'], 'AVAILABLE')
        self.assertEqual(late_summary['out_count'], 1)


if __name__ == '__main__':
    unittest.main()
