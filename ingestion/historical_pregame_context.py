from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from analytics.features_opportunity import build_pregame_feature_seed
from analytics.injury_report_loader import (
    build_official_injury_report_index,
    load_latest_official_injury_report_rows,
)
from analytics.name_matching import normalize_name
from database.db import session_scope
from database.models import Game, HistoricalAdvancedLog, HistoricalGameLog, PlayerRotationGame, Team
from ingestion.writer import write_pregame_context_snapshots


def backfill_historical_pregame_context(
    *,
    start_date: datetime,
    end_date: datetime,
    limit_games: int | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    with session_scope() as session:
        games = (
            session.query(Game)
            .filter(Game.game_date >= start_date, Game.game_date <= end_date)
            .order_by(Game.game_date.asc(), Game.game_id.asc())
            .all()
        )
        if limit_games is not None:
            games = games[:limit_games]

        if not games:
            return {
                "game_count": 0,
                "row_count": 0,
                "persisted": False,
                "captures": [],
            }

        game_ids = [game.game_id for game in games]
        relevant_dates = sorted({_historical_capture_at(game).date() for game in games if (game.game_time_utc or game.game_date) is not None})

        participant_rows = (
            session.query(HistoricalGameLog)
            .filter(HistoricalGameLog.game_id.in_(game_ids))
            .order_by(HistoricalGameLog.game_id.asc(), HistoricalGameLog.player_id.asc())
            .all()
        )

        injury_index = build_official_injury_report_index(
            load_latest_official_injury_report_rows(
                session,
                report_dates=relevant_dates,
                captured_at=end_date,
            )
        )

        logs = session.query(HistoricalGameLog).filter(HistoricalGameLog.game_date < end_date).all()
        logs_by_player: dict[str, list[HistoricalGameLog]] = {}
        logs_by_team: dict[str, list[HistoricalGameLog]] = {}
        for log in logs:
            logs_by_player.setdefault(str(log.player_id), []).append(log)
            logs_by_team.setdefault(str(log.team), []).append(log)
        for rows in logs_by_player.values():
            rows.sort(key=lambda row: row.game_date, reverse=True)
        for rows in logs_by_team.values():
            rows.sort(key=lambda row: row.game_date, reverse=True)

        advanced_rows = session.query(HistoricalAdvancedLog).all()
        advanced_by_player_game = {(str(row.player_id), str(row.game_id)): row for row in advanced_rows}

        rotation_rows = session.query(PlayerRotationGame).all()
        rotation_by_player_game = {(str(row.player_id), str(row.game_id)): row for row in rotation_rows}
        rotation_by_team_game_player = {(str(row.team_id), str(row.game_id), str(row.player_id)): row for row in rotation_rows if row.team_id is not None}

        games_by_id = {game.game_id: game for game in games}
        team_id_by_abbreviation = {
            str(team.abbreviation): str(team.team_id)
            for team in session.query(Team).all()
            if team.abbreviation and team.team_id is not None
        }

        rows_to_write: list[dict[str, Any]] = []
        captures: set[str] = set()
        skipped_markets = 0

        for participant in participant_rows:
            game = games_by_id.get(participant.game_id)
            if game is None:
                skipped_markets += 1
                continue
            captured_at = _historical_capture_at(game)

            seed = build_pregame_feature_seed(
                session,
                request=_HistoricalFeatureRequest.from_participant(participant, game, captured_at=captured_at),
                games_by_id=games_by_id,
                team_id_by_abbreviation=team_id_by_abbreviation,
                pregame_context_index=None,
                official_injury_index=injury_index,
                logs_by_player=logs_by_player,
                advanced_by_player_game=advanced_by_player_game,
                rotation_by_player_game=rotation_by_player_game,
                logs_by_team=logs_by_team,
                rotation_by_team_game_player=rotation_by_team_game_player,
            )
            if seed is None:
                skipped_markets += 1
                continue

            features = seed.build_opportunity_features()
            row = {
                "game_id": features.game_id,
                "team_id": None,
                "team_abbr": features.team_abbreviation,
                "opponent_team_id": None,
                "player_id": features.player_id,
                "player_key": f"id:{features.player_id}",
                "normalized_player_name": normalize_name(features.player_name),
                "player_name": features.player_name,
                "expected_start": None,
                "starter_confidence": None,
                "official_available": features.official_available,
                "projected_available": features.projected_available,
                "late_scratch_risk": features.late_scratch_risk,
                "teammate_out_count_top7": features.teammate_out_count_top7,
                "teammate_out_count_top9": features.teammate_out_count_top9,
                "missing_high_usage_teammates": features.missing_high_usage_teammates,
                "missing_primary_ballhandler": features.missing_primary_ballhandler,
                "missing_frontcourt_rotation_piece": features.missing_frontcourt_rotation_piece,
                "vacated_minutes_proxy": features.vacated_minutes_proxy,
                "vacated_usage_proxy": features.vacated_usage_proxy,
                "role_replacement_minutes_proxy": features.role_replacement_minutes_proxy,
                "role_replacement_usage_proxy": features.role_replacement_usage_proxy,
                "role_replacement_touches_proxy": features.role_replacement_touches_proxy,
                "role_replacement_passes_proxy": features.role_replacement_passes_proxy,
                "projected_lineup_confirmed": None,
                "official_starter_flag": None,
                "pregame_context_confidence": features.pregame_context_confidence,
                "source_captured_at": captured_at,
                "captured_at": captured_at,
            }
            rows_to_write.append(row)
            captures.add(captured_at.isoformat())

    if persist and rows_to_write:
        write_pregame_context_snapshots(rows_to_write)

    return {
        "game_count": len(games),
        "participant_count": len(participant_rows),
        "row_count": len(rows_to_write),
        "skipped_markets": skipped_markets,
        "persisted": persist and bool(rows_to_write),
        "captures": sorted(captures),
    }


def _historical_capture_at(game: Game) -> datetime:
    base = game.game_time_utc or game.game_date
    if base is None:
        raise ValueError(f"Game {game.game_id} is missing game_date/game_time_utc")
    return base - timedelta(minutes=60)


class _HistoricalFeatureRequest:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)

    @classmethod
    def from_participant(
        cls,
        participant: HistoricalGameLog,
        game: Game,
        *,
        captured_at: datetime,
    ) -> "_HistoricalFeatureRequest":
        return cls(
            game_id=str(game.game_id),
            player_id=str(participant.player_id),
            player_name=str(participant.player_name),
            stat_type="points",
            line=0.0,
            over_odds=0,
            under_odds=0,
            captured_at=captured_at,
            game_date=captured_at,
            team_abbreviation=str(participant.team or "") or None,
            opponent_abbreviation=str(participant.opponent or "") or None,
            is_home=participant.is_home,
            days_rest=None,
            back_to_back=False,
        )
