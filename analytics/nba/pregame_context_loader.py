from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from analytics.name_matching import candidate_name_keys, normalize_name
from database.models import PregameContextSnapshot

DEFAULT_PREGAME_CONTEXT_FEATURES_PATH = Path("pregame_context_feature_pack/data/pregame_context/features/latest.json")


@dataclass(slots=True)
class PregameContextIndex:
    by_game_player_id: dict[tuple[str, str], list[dict[str, Any]]]
    by_game_team_name: dict[tuple[str, str, str], list[dict[str, Any]]]
    by_game_name: dict[tuple[str, str], list[dict[str, Any]]]


def load_pregame_context_feature_rows(path: str | Path | None = None) -> list[dict[str, Any]]:
    feature_path = Path(path) if path is not None else DEFAULT_PREGAME_CONTEXT_FEATURES_PATH
    if not feature_path.exists():
        return []

    payload = json.loads(feature_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def load_pregame_context_snapshot_rows(
    session: Session,
    *,
    game_ids: list[str] | None = None,
    captured_at: datetime | None = None,
) -> list[dict[str, Any]]:
    query = session.query(PregameContextSnapshot)
    if game_ids:
        query = query.filter(PregameContextSnapshot.game_id.in_(game_ids))
    if captured_at is not None:
        query = query.filter(PregameContextSnapshot.captured_at <= captured_at)
    return [_snapshot_row_to_dict(row) for row in query.all()]


def build_pregame_context_index(rows: list[dict[str, Any]]) -> PregameContextIndex:
    by_game_player_id: dict[tuple[str, str], list[dict[str, Any]]] = {}
    by_game_team_name: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    by_game_name: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for row in rows:
        game_id = str(row.get("game_id") or "")
        team_abbr = str(row.get("team_abbr") or row.get("team_abbreviation") or "").upper()
        player_name = str(row.get("player_name") or "")
        player_id = row.get("player_id")

        if game_id and player_id not in (None, ""):
            by_game_player_id.setdefault((game_id, str(player_id)), []).append(row)
        if not game_id or not player_name:
            continue
        for candidate in candidate_name_keys(player_name):
            by_game_name.setdefault((game_id, candidate), []).append(row)
            if team_abbr:
                by_game_team_name.setdefault((game_id, team_abbr, candidate), []).append(row)

    for rows_for_key in by_game_player_id.values():
        rows_for_key.sort(key=_captured_sort_key)
    for rows_for_key in by_game_team_name.values():
        rows_for_key.sort(key=_captured_sort_key)
    for rows_for_key in by_game_name.values():
        rows_for_key.sort(key=_captured_sort_key)

    return PregameContextIndex(
        by_game_player_id=by_game_player_id,
        by_game_team_name=by_game_team_name,
        by_game_name=by_game_name,
    )


def match_pregame_context_row(
    index: PregameContextIndex,
    *,
    game_id: str,
    player_id: str | None,
    team_abbreviation: str | None,
    player_name: str,
    captured_at: datetime | None = None,
) -> dict[str, Any] | None:
    game_key = str(game_id)
    if player_id:
        match = _select_asof_row(index.by_game_player_id.get((game_key, str(player_id)), []), captured_at)
        if match is not None:
            return match

    candidate_keys = candidate_name_keys(player_name)
    team_abbr = (team_abbreviation or "").upper()
    if team_abbr:
        for candidate in candidate_keys:
            match = _select_asof_row(index.by_game_team_name.get((game_key, team_abbr, candidate), []), captured_at)
            if match is not None:
                return match

    return _select_unique_asof_row(_candidate_name_rows(index, game_key, candidate_keys), captured_at)


def _snapshot_row_to_dict(row: PregameContextSnapshot) -> dict[str, Any]:
    return {
        "game_id": row.game_id,
        "team_id": row.team_id,
        "team_abbr": row.team_abbreviation,
        "opponent_team_id": row.opponent_team_id,
        "player_id": row.player_id,
        "player_key": row.player_key,
        "normalized_player_name": row.normalized_player_name,
        "player_name": row.player_name,
        "expected_start": row.expected_start,
        "starter_confidence": row.starter_confidence,
        "official_available": row.official_available,
        "projected_available": row.projected_available,
        "late_scratch_risk": row.late_scratch_risk,
        "teammate_out_count_top7": row.teammate_out_count_top7,
        "teammate_out_count_top9": row.teammate_out_count_top9,
        "missing_high_usage_teammates": row.missing_high_usage_teammates,
        "missing_primary_ballhandler": row.missing_primary_ballhandler,
        "missing_frontcourt_rotation_piece": row.missing_frontcourt_rotation_piece,
        "vacated_minutes_proxy": row.vacated_minutes_proxy,
        "vacated_usage_proxy": row.vacated_usage_proxy,
        "projected_lineup_confirmed": row.projected_lineup_confirmed,
        "official_starter_flag": row.official_starter_flag,
        "pregame_context_confidence": row.pregame_context_confidence,
        "source_captured_at": row.source_captured_at,
        "captured_at": row.captured_at,
    }


def _candidate_name_rows(index: PregameContextIndex, game_id: str, candidate_keys: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidate_keys:
        rows.extend(index.by_game_name.get((game_id, candidate), []))
    return rows


def _select_asof_row(rows: list[dict[str, Any]], captured_at: datetime | None) -> dict[str, Any] | None:
    if not rows:
        return None
    if captured_at is None:
        return rows[-1]

    selected: dict[str, Any] | None = None
    for row in rows:
        row_captured_at = row.get("captured_at")
        if row_captured_at is None or row_captured_at <= captured_at:
            selected = row
        else:
            break
    return selected


def _select_unique_asof_row(rows: list[dict[str, Any]], captured_at: datetime | None) -> dict[str, Any] | None:
    latest_by_identity: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        row_captured_at = row.get("captured_at")
        if captured_at is not None and row_captured_at is not None and row_captured_at > captured_at:
            continue
        latest_by_identity[_row_identity(row)] = row
    if len(latest_by_identity) != 1:
        return None
    return next(iter(latest_by_identity.values()))


def _row_identity(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("player_key") or ""),
        str(row.get("player_id") or ""),
        str(row.get("team_abbr") or row.get("team_abbreviation") or "").upper(),
        str(row.get("player_name") or ""),
    )


def _captured_sort_key(row: dict[str, Any]) -> tuple[int, datetime]:
    captured_at = row.get("captured_at")
    if isinstance(captured_at, datetime):
        return (1, captured_at)
    return (0, datetime.min)



def _normalize_name(name: str) -> str:
    return normalize_name(name)
