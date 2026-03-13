from __future__ import annotations

import unittest
from datetime import date, datetime
from types import SimpleNamespace

from analytics.evaluation import (
    _build_historical_injury_report_indexes,
    _build_odds_index,
    _select_historical_injury_index,
    _select_latest_pregame_odds_snapshot,
    _summarize_points_errors,
)
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


class HistoricalOddsEvaluationTests(unittest.TestCase):
    def test_select_latest_odds_snapshot_respects_tip_cutoff_and_lead_windows(self):
        rows = [
            SimpleNamespace(game_id="G1", player_id="7", captured_at=datetime(2026, 1, 5, 17, 45, 0), line=23.5, over_odds=-110, under_odds=-110),
            SimpleNamespace(game_id="G1", player_id="7", captured_at=datetime(2026, 1, 5, 18, 40, 0), line=24.5, over_odds=-110, under_odds=-110),
            SimpleNamespace(game_id="G1", player_id="7", captured_at=datetime(2026, 1, 5, 19, 5, 0), line=25.5, over_odds=-110, under_odds=-110),
        ]
        index = _build_odds_index(rows)

        latest = _select_latest_pregame_odds_snapshot(
            index,
            game_id="G1",
            player_id="7",
            cutoff=datetime(2026, 1, 5, 19, 0, 0),
        )
        with_min_lead = _select_latest_pregame_odds_snapshot(
            index,
            game_id="G1",
            player_id="7",
            cutoff=datetime(2026, 1, 5, 19, 0, 0),
            min_minutes_before_tip=30,
        )

        self.assertEqual(latest.line, 24.5)
        self.assertEqual(with_min_lead.line, 23.5)


    def test_summarize_points_errors_returns_zeroed_empty_slice(self):
        empty = _summarize_points_errors([])
        populated = _summarize_points_errors([
            SimpleNamespace(error=2.0, abs_error=2.0),
            SimpleNamespace(error=-1.0, abs_error=1.0),
        ])

        self.assertEqual(empty.sample_size, 0)
        self.assertEqual(empty.mae, 0.0)
        self.assertEqual(populated.sample_size, 2)
        self.assertEqual(populated.mae, 1.5)
        self.assertEqual(populated.rmse, 1.5811)
        self.assertEqual(populated.bias, 0.5)
        self.assertEqual(populated.within_two_points_pct, 1.0)
        self.assertEqual(populated.within_four_points_pct, 1.0)


if __name__ == '__main__':
    unittest.main()
