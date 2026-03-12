from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pregame_context import _normalize_name


@dataclass(slots=True)
class TeamPriors:
    top7_player_ids: set[int]
    top9_player_ids: set[int]
    high_usage_player_ids: set[int]
    primary_ballhandler_ids: set[int]
    frontcourt_rotation_player_ids: set[int]
    baseline_minutes_by_player_id: dict[int, float]
    baseline_usage_by_player_id: dict[int, float]


def load_team_priors(path: str | Path | None) -> dict[int, TeamPriors]:
    if not path:
        return {}

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[int, TeamPriors] = {}

    for team_id_raw, payload in raw.items():
        team_id = int(team_id_raw)
        out[team_id] = TeamPriors(
            top7_player_ids={int(x) for x in payload.get("top7_player_ids", [])},
            top9_player_ids={int(x) for x in payload.get("top9_player_ids", [])},
            high_usage_player_ids={int(x) for x in payload.get("high_usage_player_ids", [])},
            primary_ballhandler_ids={int(x) for x in payload.get("primary_ballhandler_ids", [])},
            frontcourt_rotation_player_ids={int(x) for x in payload.get("frontcourt_rotation_player_ids", [])},
            baseline_minutes_by_player_id={int(k): float(v) for k, v in payload.get("baseline_minutes_by_player_id", {}).items()},
            baseline_usage_by_player_id={int(k): float(v) for k, v in payload.get("baseline_usage_by_player_id", {}).items()},
        )

    return out


def build_pregame_feature_rows(
    normalized_payload: dict[str, Any],
    priors_by_team_id: dict[int, TeamPriors] | None = None,
) -> list[dict[str, Any]]:
    priors_by_team_id = priors_by_team_id or {}

    out: list[dict[str, Any]] = []
    asof_utc = normalized_payload.get("fetched_at_utc") or datetime.now(timezone.utc).isoformat()

    for game in normalized_payload.get("games", []):
        availability = game.get("availability", [])
        projected_starters = game.get("projected_starters", [])
        projected_absences = game.get("projected_absences", [])

        by_player = _index_availability(availability, game)
        projected_by_player = _index_projected(projected_starters, projected_absences, game)
        all_keys = sorted(set(by_player) | set(projected_by_player))

        team_context_by_team = _build_team_context_by_team(game, by_player, projected_by_player)
        game_conf = _game_context_confidence(game)

        for player_key in all_keys:
            base = by_player.get(player_key) or _base_from_projected(projected_by_player[player_key])
            projected = projected_by_player.get(player_key, {})
            team_id = base.get("team_id")
            team_abbr = base.get("team_abbr")
            opp_team_id = _opponent_team_id(game, team_id, team_abbr)
            team_priors = priors_by_team_id.get(team_id) if team_id is not None else None
            team_rows = team_context_by_team.get((team_id, team_abbr or ""), [])

            row = {
                "asof_utc": asof_utc,
                "game_id": game.get("game_id"),
                "team_id": team_id,
                "team_abbr": team_abbr,
                "opponent_team_id": opp_team_id,
                "player_id": base.get("player_id"),
                "player_key": player_key,
                "player_name": base.get("player_name"),
                "expected_start": _expected_start(base, projected),
                "starter_confidence": _starter_confidence(base, projected),
                "official_available": _official_available(base),
                "projected_available": _projected_available(base, projected),
                "late_scratch_risk": _late_scratch_risk(base, projected),
                "teammate_out_count_top7": _teammate_out_count(team_rows, player_key, team_priors, top_n=7),
                "teammate_out_count_top9": _teammate_out_count(team_rows, player_key, team_priors, top_n=9),
                "missing_high_usage_teammates": _missing_from_set(team_rows, player_key, team_priors, "high_usage"),
                "missing_primary_ballhandler": _missing_from_set(team_rows, player_key, team_priors, "ballhandler") > 0,
                "missing_frontcourt_rotation_piece": _missing_from_set(team_rows, player_key, team_priors, "frontcourt") > 0,
                "vacated_minutes_proxy": _vacated_minutes_proxy(team_rows, player_key, team_priors),
                "vacated_usage_proxy": _vacated_usage_proxy(team_rows, player_key, team_priors),
                "projected_lineup_confirmed": bool(projected.get("lineup_confirmed")),
                "official_starter_flag": bool(base.get("starter_flag")),
                "pregame_context_confidence": game_conf,
            }
            out.append(row)

    return out


def save_feature_rows(rows: list[dict[str, Any]], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _index_availability(availability: list[dict[str, Any]], game: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in availability:
        team_abbr = (row.get("team_abbr") or "").upper()
        player_name = row.get("player_name") or ""
        if not team_abbr or not player_name:
            continue
        player_id = _to_int_or_none(row.get("player_id"))
        key = _player_key(player_id, team_abbr, player_name)
        out[key] = {
            **row,
            "player_id": player_id,
            "team_id": _resolve_team_id(game, team_abbr, _to_int_or_none(row.get("team_id"))),
            "team_abbr": team_abbr,
            "player_name": player_name,
            "player_key": key,
        }
    return out


def _index_projected(
    projected_starters: list[dict[str, Any]],
    projected_absences: list[dict[str, Any]],
    game: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in projected_starters:
        _merge_projected_row(out, row, game, projected_starter=True)
    for row in projected_absences:
        _merge_projected_row(out, row, game, projected_starter=False)
    return out


def _merge_projected_row(
    out: dict[str, dict[str, Any]],
    row: dict[str, Any],
    game: dict[str, Any],
    *,
    projected_starter: bool,
) -> None:
    team_abbr = (row.get("team_abbr") or "").upper()
    player_name = row.get("player_name") or ""
    if not team_abbr or not player_name:
        return
    player_id = _to_int_or_none(row.get("player_id"))
    team_id = _resolve_team_id(game, team_abbr, _to_int_or_none(row.get("team_id")))
    key = _player_key(player_id, team_abbr, player_name)
    current = out.get(key, {})
    merged = {
        **current,
        "player_id": player_id,
        "team_id": team_id,
        "team_abbr": team_abbr,
        "player_name": player_name,
        "position": row.get("position") or current.get("position"),
        "projected_starter": current.get("projected_starter") or projected_starter,
        "lineup_confirmed": bool(row.get("lineup_confirmed")) or bool(current.get("lineup_confirmed")),
        "lineup_status": row.get("lineup_status") or current.get("lineup_status"),
        "play_probability_hint": row.get("play_probability_hint") if row.get("play_probability_hint") is not None else current.get("play_probability_hint"),
        "injury_tag": row.get("injury_tag") or current.get("injury_tag"),
        "availability_bucket": row.get("availability_bucket") or current.get("availability_bucket"),
        "player_key": key,
    }
    out[key] = merged


def _build_team_context_by_team(
    game: dict[str, Any],
    by_player: dict[str, dict[str, Any]],
    projected_by_player: dict[str, dict[str, Any]],
) -> dict[tuple[int | None, str], list[dict[str, Any]]]:
    merged: dict[str, dict[str, Any]] = {key: dict(value) for key, value in by_player.items()}
    for key, projected in projected_by_player.items():
        base = merged.get(key, {})
        merged[key] = {
            **projected,
            **base,
            "player_id": base.get("player_id") if base.get("player_id") is not None else projected.get("player_id"),
            "team_id": base.get("team_id") if base.get("team_id") is not None else projected.get("team_id"),
            "team_abbr": base.get("team_abbr") or projected.get("team_abbr"),
            "player_name": base.get("player_name") or projected.get("player_name"),
            "position": base.get("position") or projected.get("position"),
            "projected_starter": bool(base.get("starter_flag")) or bool(projected.get("projected_starter")),
            "lineup_confirmed": bool(projected.get("lineup_confirmed")),
            "play_probability_hint": projected.get("play_probability_hint"),
            "injury_tag": projected.get("injury_tag"),
            "availability_bucket": projected.get("availability_bucket"),
            "player_key": key,
        }
    team_map: dict[tuple[int | None, str], list[dict[str, Any]]] = {}
    for row in merged.values():
        key = (row.get("team_id"), row.get("team_abbr") or "")
        team_map.setdefault(key, []).append(row)
    return team_map


def _base_from_projected(projected: dict[str, Any]) -> dict[str, Any]:
    return {
        "team_id": projected.get("team_id"),
        "team_abbr": projected.get("team_abbr"),
        "player_id": projected.get("player_id"),
        "player_name": projected.get("player_name"),
        "position": projected.get("position"),
        "status": None,
        "starter_flag": False,
        "not_playing_reason": None,
        "not_playing_description": None,
        "player_key": projected.get("player_key"),
    }


def _official_available(base: dict[str, Any]) -> bool | None:
    status = (base.get("status") or "").upper()
    if not status:
        return None
    return status == "ACTIVE" and not (base.get("not_playing_reason") or "").startswith("DNP_")


def _expected_start(base: dict[str, Any], projected: dict[str, Any]) -> bool:
    return bool(base.get("starter_flag") or projected.get("projected_starter"))


def _starter_confidence(base: dict[str, Any], projected: dict[str, Any]) -> float:
    if base.get("starter_flag"):
        return 1.0
    if projected.get("projected_starter"):
        if projected.get("lineup_confirmed"):
            return 0.9
        hint = projected.get("play_probability_hint")
        if hint is None:
            return 0.6
        return max(0.0, min(1.0, float(hint) / 100.0))
    return 0.1


def _projected_available(base: dict[str, Any], projected: dict[str, Any]) -> bool:
    official = _official_available(base)
    if official is not None:
        return official
    hint = projected.get("play_probability_hint")
    if hint is not None:
        return int(hint) >= 50
    injury_tag = (projected.get("injury_tag") or "").lower()
    if "out" in injury_tag or projected.get("availability_bucket") == "may_not_play":
        return False
    return True


def _late_scratch_risk(base: dict[str, Any], projected: dict[str, Any]) -> float:
    official = _official_available(base)
    if official is False:
        return 1.0
    hint = projected.get("play_probability_hint")
    if hint is None:
        return 0.2 if official is True else 0.35
    return round(max(0.0, min(1.0, 1.0 - (float(hint) / 100.0))), 3)


def _teammate_out_count(team_rows: list[dict[str, Any]], player_key: str, priors: TeamPriors | None, top_n: int) -> int:
    if priors is None:
        return sum(1 for row in team_rows if row.get("player_key") != player_key and _rotation_likely(row) and not _context_available(row))

    ids = priors.top7_player_ids if top_n == 7 else priors.top9_player_ids
    count = 0
    for row in team_rows:
        if row.get("player_key") == player_key or _context_available(row):
            continue
        player_id = row.get("player_id")
        if player_id in ids:
            count += 1
        elif player_id is None and _rotation_likely(row):
            count += 1
    return count


def _missing_from_set(team_rows: list[dict[str, Any]], player_key: str, priors: TeamPriors | None, mode: str) -> int:
    if priors is None:
        return 0

    if mode == "high_usage":
        ids = priors.high_usage_player_ids
        fallback_predicate = lambda row: _rotation_likely(row)
    elif mode == "ballhandler":
        ids = priors.primary_ballhandler_ids
        fallback_predicate = lambda row: (row.get("position") or "").upper() in {"PG", "G", "SG"}
    else:
        ids = priors.frontcourt_rotation_player_ids
        fallback_predicate = lambda row: (row.get("position") or "").upper() in {"C", "F", "PF", "SF", "FC"}

    count = 0
    for row in team_rows:
        if row.get("player_key") == player_key or _context_available(row):
            continue
        player_id = row.get("player_id")
        if player_id in ids:
            count += 1
        elif player_id is None and fallback_predicate(row):
            count += 1
    return count


def _vacated_minutes_proxy(team_rows: list[dict[str, Any]], player_key: str, priors: TeamPriors | None) -> float:
    vacated = 0.0
    for row in team_rows:
        if row.get("player_key") == player_key or _context_available(row):
            continue
        player_id = row.get("player_id")
        if priors is not None and player_id is not None:
            vacated += float(priors.baseline_minutes_by_player_id.get(int(player_id), 0.0))
        elif _rotation_likely(row):
            vacated += 28.0 if _starter_like(row) else 18.0
    return round(vacated, 2)


def _vacated_usage_proxy(team_rows: list[dict[str, Any]], player_key: str, priors: TeamPriors | None) -> float:
    vacated = 0.0
    for row in team_rows:
        if row.get("player_key") == player_key or _context_available(row):
            continue
        player_id = row.get("player_id")
        if priors is not None and player_id is not None:
            vacated += float(priors.baseline_usage_by_player_id.get(int(player_id), 0.0))
        elif _rotation_likely(row):
            vacated += 0.18 if _starter_like(row) else 0.10
    return round(vacated, 3)


def _context_available(row: dict[str, Any]) -> bool:
    official = _official_available(row)
    if official is not None:
        return official
    hint = row.get("play_probability_hint")
    if hint is not None:
        return int(hint) >= 50
    injury_tag = (row.get("injury_tag") or "").lower()
    if "out" in injury_tag:
        return False
    if row.get("availability_bucket") == "may_not_play":
        return False
    return True


def _rotation_likely(row: dict[str, Any]) -> bool:
    return bool(
        row.get("starter_flag")
        or row.get("projected_starter")
        or row.get("availability_bucket") == "may_not_play"
    )


def _starter_like(row: dict[str, Any]) -> bool:
    return bool(row.get("starter_flag") or row.get("projected_starter"))


def _game_context_confidence(game: dict[str, Any]) -> float:
    sources = game.get("sources_present", {})
    has_nba = bool(sources.get("nba_live_boxscore"))
    has_rw = bool(sources.get("rotowire_lineups"))
    if has_nba and has_rw:
        return 0.95
    if has_nba:
        return 0.8
    if has_rw:
        return 0.55
    return 0.2


def _opponent_team_id(game: dict[str, Any], team_id: int | None, team_abbr: str | None) -> int | None:
    away = game.get("away_team", {})
    home = game.get("home_team", {})
    away_id = _to_int_or_none(away.get("team_id"))
    home_id = _to_int_or_none(home.get("team_id"))
    away_abbr = (away.get("team_abbr") or "").upper()
    home_abbr = (home.get("team_abbr") or "").upper()
    if team_id is not None:
        if away_id == team_id:
            return home_id
        if home_id == team_id:
            return away_id
    if team_abbr:
        team_abbr = team_abbr.upper()
        if team_abbr == away_abbr:
            return home_id
        if team_abbr == home_abbr:
            return away_id
    return None


def _resolve_team_id(game: dict[str, Any], team_abbr: str, explicit_team_id: int | None) -> int | None:
    if explicit_team_id is not None:
        return explicit_team_id
    away = game.get("away_team", {})
    home = game.get("home_team", {})
    team_abbr = team_abbr.upper()
    if team_abbr == (away.get("team_abbr") or "").upper():
        return _to_int_or_none(away.get("team_id"))
    if team_abbr == (home.get("team_abbr") or "").upper():
        return _to_int_or_none(home.get("team_id"))
    return None


def _player_key(player_id: int | None, team_abbr: str, player_name: str) -> str:
    if player_id is not None:
        return f"id:{int(player_id)}"
    return f"name:{team_abbr.upper()}:{_normalize_name(player_name)}"


def _to_int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None
