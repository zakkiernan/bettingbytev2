from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_PREGAME_CONTEXT_FEATURES_PATH = Path("pregame_context_feature_pack/data/pregame_context/features/latest.json")


@dataclass(slots=True)
class PregameContextIndex:
    by_game_player_id: dict[tuple[str, str], dict[str, Any]]
    by_game_team_name: dict[tuple[str, str, str], dict[str, Any]]


def load_pregame_context_feature_rows(path: str | Path | None = None) -> list[dict[str, Any]]:
    feature_path = Path(path) if path is not None else DEFAULT_PREGAME_CONTEXT_FEATURES_PATH
    if not feature_path.exists():
        return []

    payload = json.loads(feature_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def build_pregame_context_index(rows: list[dict[str, Any]]) -> PregameContextIndex:
    by_game_player_id: dict[tuple[str, str], dict[str, Any]] = {}
    by_game_team_name: dict[tuple[str, str, str], dict[str, Any]] = {}

    for row in rows:
        game_id = str(row.get("game_id") or "")
        team_abbr = str(row.get("team_abbr") or "").upper()
        player_name = str(row.get("player_name") or "")
        player_id = row.get("player_id")

        if game_id and player_id not in (None, ""):
            by_game_player_id[(game_id, str(player_id))] = row
        if not game_id or not team_abbr or not player_name:
            continue
        for candidate in _candidate_name_keys(player_name):
            by_game_team_name.setdefault((game_id, team_abbr, candidate), row)

    return PregameContextIndex(by_game_player_id=by_game_player_id, by_game_team_name=by_game_team_name)


def match_pregame_context_row(
    index: PregameContextIndex,
    *,
    game_id: str,
    player_id: str | None,
    team_abbreviation: str | None,
    player_name: str,
) -> dict[str, Any] | None:
    if player_id:
        match = index.by_game_player_id.get((str(game_id), str(player_id)))
        if match is not None:
            return match

    team_abbr = (team_abbreviation or "").upper()
    if not team_abbr:
        return None

    for candidate in _candidate_name_keys(player_name):
        match = index.by_game_team_name.get((str(game_id), team_abbr, candidate))
        if match is not None:
            return match
    return None


def _normalize_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", ascii_name.lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _candidate_name_keys(name: str) -> list[str]:
    normalized = _normalize_name(name)
    if not normalized:
        return []

    keys = [normalized]
    tokens = normalized.split()
    suffixes = {"jr", "sr", "ii", "iii", "iv", "v"}
    while tokens and tokens[-1] in suffixes:
        tokens = tokens[:-1]
        if tokens:
            candidate = " ".join(tokens)
            if candidate not in keys:
                keys.append(candidate)
    return keys
