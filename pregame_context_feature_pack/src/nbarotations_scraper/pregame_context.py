from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

LOGGER = logging.getLogger(__name__)

NBA_SCOREBOARD_URL = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
NBA_BOXSCORE_URL = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"
ROTOWIRE_LINEUPS_URL = "https://www.rotowire.com/basketball/nba-lineups.php"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


@dataclass(slots=True)
class TeamGameRef:
    game_id: str
    away_abbr: str
    home_abbr: str
    away_team_id: int | None
    home_team_id: int | None
    game_time_utc: str | None
    game_status: int
    game_status_text: str


@dataclass(slots=True)
class RotowirePlayer:
    position: str | None
    name: str
    play_probability_hint: int | None
    injury_tag: str | None


@dataclass(slots=True)
class RotowireGame:
    away_abbr: str
    home_abbr: str
    lineup_status: str | None
    lineup_confirmed: bool
    away_starters: list[RotowirePlayer]
    home_starters: list[RotowirePlayer]
    away_may_not_play: list[RotowirePlayer]
    home_may_not_play: list[RotowirePlayer]


class PregameContextIngestor:
    """Collect pregame NBA context from official NBA live JSON + Rotowire lineups.

    Goals:
    - Keep ingestion isolated from analytics/model logic.
    - Normalize to canonical NBA game/team/player ids when available.
    - Make source confidence explicit per record.
    """

    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch(self, schedule_refs: list[TeamGameRef] | None = None) -> dict[str, Any]:
        fetched_at_utc = datetime.now(timezone.utc).isoformat()

        nba_games = list(schedule_refs) if schedule_refs is not None else self._fetch_nba_schedule_refs()
        nba_by_key = {(g.away_abbr, g.home_abbr): g for g in nba_games}

        rotowire_games = self._fetch_rotowire_games()
        rotowire_by_key = {(g.away_abbr, g.home_abbr): g for g in rotowire_games}

        contexts: list[dict[str, Any]] = []
        for key, nba_ref in nba_by_key.items():
            game_payload = self._build_game_payload(nba_ref=nba_ref, rotowire_game=rotowire_by_key.get(key))
            contexts.append(game_payload)

        unmatched_rotowire = [
            {
                "away_abbr": g.away_abbr,
                "home_abbr": g.home_abbr,
                "lineup_status": g.lineup_status,
            }
            for key, g in rotowire_by_key.items()
            if key not in nba_by_key
        ]

        return {
            "source": "pregame_context_prototype",
            "fetched_at_utc": fetched_at_utc,
            "sources": {
                "nba_live_scoreboard": NBA_SCOREBOARD_URL,
                "nba_live_boxscore_template": NBA_BOXSCORE_URL,
                "rotowire_lineups": ROTOWIRE_LINEUPS_URL,
            },
            "games": contexts,
            "unmatched_rotowire_games": unmatched_rotowire,
        }

    def _fetch_json(self, url: str) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = self.session.get(url, timeout=self.timeout_seconds)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                continue
        raise RuntimeError(f"Failed to fetch JSON after retries: {url}: {last_exc}") from last_exc

    def _fetch_nba_schedule_refs(self) -> list[TeamGameRef]:
        data = self._fetch_json(NBA_SCOREBOARD_URL)
        games_raw = data.get("scoreboard", {}).get("games", [])

        refs: list[TeamGameRef] = []
        for g in games_raw:
            away = g.get("awayTeam", {})
            home = g.get("homeTeam", {})
            away_abbr = (away.get("teamTricode") or "").upper()
            home_abbr = (home.get("teamTricode") or "").upper()
            if not away_abbr or not home_abbr:
                continue
            refs.append(
                TeamGameRef(
                    game_id=str(g.get("gameId") or ""),
                    away_abbr=away_abbr,
                    home_abbr=home_abbr,
                    away_team_id=_to_int_or_none(away.get("teamId")),
                    home_team_id=_to_int_or_none(home.get("teamId")),
                    game_time_utc=g.get("gameTimeUTC"),
                    game_status=int(g.get("gameStatus") or 0),
                    game_status_text=g.get("gameStatusText") or "",
                )
            )
        return refs

    def _fetch_rotowire_games(self) -> list[RotowireGame]:
        resp = self.session.get(ROTOWIRE_LINEUPS_URL, timeout=self.timeout_seconds)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, _html_parser())

        games: list[RotowireGame] = []
        for card in soup.select(".lineup.is-nba"):
            abbrs = [x.get_text(" ", strip=True).upper() for x in card.select(".lineup__abbr")]
            if len(abbrs) < 2:
                continue

            away_list = card.select_one(".lineup__list.is-visit")
            home_list = card.select_one(".lineup__list.is-home")
            if away_list is None or home_list is None:
                continue

            lineup_status_node = card.select_one(".lineup__status")
            lineup_status = lineup_status_node.get_text(" ", strip=True) if lineup_status_node else None
            lineup_confirmed = bool(lineup_status_node and "confirmed" in " ".join(lineup_status_node.get("class", [])).lower())

            away_starters, away_mnp = _parse_rotowire_team_list(away_list)
            home_starters, home_mnp = _parse_rotowire_team_list(home_list)

            games.append(
                RotowireGame(
                    away_abbr=abbrs[0],
                    home_abbr=abbrs[1],
                    lineup_status=lineup_status,
                    lineup_confirmed=lineup_confirmed,
                    away_starters=away_starters,
                    home_starters=home_starters,
                    away_may_not_play=away_mnp,
                    home_may_not_play=home_mnp,
                )
            )

        return games

    def _build_game_payload(self, nba_ref: TeamGameRef, rotowire_game: RotowireGame | None) -> dict[str, Any]:
        box_ok = True
        try:
            box = self._fetch_json(NBA_BOXSCORE_URL.format(game_id=nba_ref.game_id)).get("game", {})
        except Exception as exc:
            LOGGER.warning("NBA boxscore fetch failed for game_id=%s: %s", nba_ref.game_id, exc)
            box = {}
            box_ok = False

        away_ctx = _extract_team_availability(box.get("awayTeam", {}))
        home_ctx = _extract_team_availability(box.get("homeTeam", {}))

        availability = away_ctx["availability"] + home_ctx["availability"]
        official_starters = away_ctx["official_starters"] + home_ctx["official_starters"]

        roster_lookup = _build_roster_lookup_by_team(availability)

        projected_starters: list[dict[str, Any]] = []
        projected_absences: list[dict[str, Any]] = []
        if rotowire_game is not None:
            projected_starters.extend(
                _normalize_rotowire_starters(
                    team_abbr=rotowire_game.away_abbr,
                    team_id_hint=nba_ref.away_team_id,
                    rows=rotowire_game.away_starters,
                    lineup_confirmed=rotowire_game.lineup_confirmed,
                    lineup_status=rotowire_game.lineup_status,
                    roster_lookup=roster_lookup,
                )
            )
            projected_starters.extend(
                _normalize_rotowire_starters(
                    team_abbr=rotowire_game.home_abbr,
                    team_id_hint=nba_ref.home_team_id,
                    rows=rotowire_game.home_starters,
                    lineup_confirmed=rotowire_game.lineup_confirmed,
                    lineup_status=rotowire_game.lineup_status,
                    roster_lookup=roster_lookup,
                )
            )

            projected_absences.extend(
                _normalize_rotowire_absences(rotowire_game.away_abbr, nba_ref.away_team_id, rotowire_game.away_may_not_play, roster_lookup)
            )
            projected_absences.extend(
                _normalize_rotowire_absences(rotowire_game.home_abbr, nba_ref.home_team_id, rotowire_game.home_may_not_play, roster_lookup)
            )

        return {
            "game_id": nba_ref.game_id,
            "game_time_utc": nba_ref.game_time_utc,
            "game_status": nba_ref.game_status,
            "game_status_text": nba_ref.game_status_text,
            "away_team": {
                "team_abbr": nba_ref.away_abbr,
                "team_id": nba_ref.away_team_id,
            },
            "home_team": {
                "team_abbr": nba_ref.home_abbr,
                "team_id": nba_ref.home_team_id,
            },
            "sources_present": {
                "nba_live_boxscore": box_ok,
                "rotowire_lineups": rotowire_game is not None,
            },
            "availability": availability,
            "official_starters": official_starters,
            "projected_starters": projected_starters,
            "projected_absences": projected_absences,
        }


def _parse_rotowire_team_list(team_ul: Any) -> tuple[list[RotowirePlayer], list[RotowirePlayer]]:
    starters: list[RotowirePlayer] = []
    may_not_play: list[RotowirePlayer] = []

    section = "starters"
    for li in team_ul.find_all("li", recursive=False):
        classes = li.get("class", []) or []
        text = li.get_text(" ", strip=True)

        if "lineup__title" in classes and "MAY NOT PLAY" in text.upper():
            section = "may_not_play"
            continue

        if "lineup__player" not in classes:
            continue

        pos_node = li.select_one(".lineup__pos")
        anchor = li.find("a")
        inj_node = li.select_one(".lineup__inj")

        if anchor is None:
            continue

        full_name = (anchor.get("title") or anchor.get_text(" ", strip=True) or "").strip()
        if not full_name:
            continue

        prob_hint = _class_play_probability_hint(classes)
        row = RotowirePlayer(
            position=pos_node.get_text(" ", strip=True) if pos_node else None,
            name=full_name,
            play_probability_hint=prob_hint,
            injury_tag=inj_node.get_text(" ", strip=True) if inj_node else None,
        )

        if section == "may_not_play":
            may_not_play.append(row)
        else:
            starters.append(row)

    return starters[:5], may_not_play


def _class_play_probability_hint(classes: list[str]) -> int | None:
    # Rotowire classes typically look like is-pct-play-100 / -75 / -0
    for c in classes:
        m = re.match(r"is-pct-play-(\d+)", c)
        if m:
            return int(m.group(1))
    return None


def _extract_team_availability(team_raw: dict[str, Any]) -> dict[str, Any]:
    team_id = _to_int_or_none(team_raw.get("teamId"))
    team_abbr = (team_raw.get("teamTricode") or "").upper()

    availability: list[dict[str, Any]] = []
    official_starters: list[dict[str, Any]] = []

    for p in team_raw.get("players", []) or []:
        player_id = _to_int_or_none(p.get("personId"))
        player_name = p.get("name") or ""
        status = (p.get("status") or "").upper() or None
        starter = str(p.get("starter") or "0") == "1"

        row = {
            "team_abbr": team_abbr,
            "team_id": team_id,
            "player_id": player_id,
            "player_name": player_name,
            "position": p.get("position"),
            "status": status,
            "starter_flag": starter,
            "not_playing_reason": p.get("notPlayingReason"),
            "not_playing_description": p.get("notPlayingDescription"),
            "source": "nba_live_boxscore",
            "source_confidence": "high",
        }
        availability.append(row)

        if starter:
            official_starters.append(
                {
                    "team_abbr": team_abbr,
                    "team_id": team_id,
                    "player_id": player_id,
                    "player_name": player_name,
                    "position": p.get("position"),
                    "starter_type": "official",
                    "source": "nba_live_boxscore",
                    "source_confidence": "high",
                }
            )

    return {
        "availability": availability,
        "official_starters": official_starters,
    }


def _build_roster_lookup_by_team(availability_rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    by_team: dict[str, dict[str, dict[str, Any]]] = {}
    for row in availability_rows:
        team = (row.get("team_abbr") or "").upper()
        name = row.get("player_name") or ""
        if not team or not name:
            continue
        bucket = by_team.setdefault(team, {})
        for key in _candidate_name_keys(name):
            bucket.setdefault(key, row)
    return by_team


def _lookup_roster_row(team_abbr: str, player_name: str, roster_lookup: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any] | None:
    team_rows = roster_lookup.get((team_abbr or '').upper(), {})
    for key in _candidate_name_keys(player_name):
        mapped = team_rows.get(key)
        if mapped is not None:
            return mapped
    return None


def _normalize_rotowire_starters(
    team_abbr: str,
    team_id_hint: int | None,
    rows: list[RotowirePlayer],
    lineup_confirmed: bool,
    lineup_status: str | None,
    roster_lookup: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for r in rows:
        mapped = _lookup_roster_row(team_abbr, r.name, roster_lookup)
        output.append(
            {
                "team_abbr": team_abbr,
                "team_id": mapped.get("team_id") if mapped and mapped.get("team_id") is not None else team_id_hint,
                "player_id": mapped.get("player_id") if mapped else None,
                "player_name": r.name,
                "position": r.position,
                "lineup_confirmed": lineup_confirmed,
                "lineup_status": lineup_status,
                "play_probability_hint": r.play_probability_hint,
                "injury_tag": r.injury_tag,
                "source": "rotowire_lineups",
                "source_confidence": "medium",
            }
        )
    return output


def _normalize_rotowire_absences(
    team_abbr: str,
    team_id_hint: int | None,
    rows: list[RotowirePlayer],
    roster_lookup: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for r in rows:
        mapped = _lookup_roster_row(team_abbr, r.name, roster_lookup)
        output.append(
            {
                "team_abbr": team_abbr,
                "team_id": mapped.get("team_id") if mapped and mapped.get("team_id") is not None else team_id_hint,
                "player_id": mapped.get("player_id") if mapped else None,
                "player_name": r.name,
                "position": r.position,
                "play_probability_hint": r.play_probability_hint,
                "injury_tag": r.injury_tag,
                "availability_bucket": "may_not_play",
                "source": "rotowire_lineups",
                "source_confidence": "medium",
            }
        )
    return output


def _normalize_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", ascii_name.lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _candidate_name_keys(name: str) -> list[str]:
    normalized = _normalize_name(name)
    if not normalized:
        return []

    tokens = normalized.split()
    keys = [normalized]
    suffixes = {"jr", "sr", "ii", "iii", "iv", "v"}
    while tokens and tokens[-1] in suffixes:
        tokens = tokens[:-1]
        if tokens:
            candidate = " ".join(tokens)
            if candidate not in keys:
                keys.append(candidate)
    return keys


def _html_parser() -> str:
    try:
        import lxml  # noqa: F401

        return "lxml"
    except Exception:
        return "html.parser"


def _to_int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def save_pregame_payload(payload: dict[str, Any], base_dir: Path | str = "data/pregame_context") -> tuple[Path, Path]:
    base = Path(base_dir)
    hist = base / "history"
    hist.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    history_path = hist / f"{ts}.json"
    latest_path = base / "latest.json"

    encoded = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    history_path.write_text(encoded, encoding="utf-8")
    latest_path.write_text(encoded, encoding="utf-8")

    LOGGER.info("Saved pregame context -> %s and %s", latest_path, history_path)
    return latest_path, history_path
