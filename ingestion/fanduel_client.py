from __future__ import annotations

import logging
import os
import re
import time
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from database.db import session_scope
from database.models import HistoricalGameLog
from ingestion.nba_client import get_player_id_map, get_todays_games_bundle

logger = logging.getLogger(__name__)

FANDUEL_COMPETITION_URL = "https://api.sportsbook.fanduel.com/sbapi/competition-page"
FANDUEL_EVENT_URL = "https://api.sportsbook.fanduel.com/sbapi/event-page"
FANDUEL_AK = os.getenv("FANDUEL_AK", "FhMFpcPWXMeyZxOx")
FANDUEL_COMPETITION_ID = int(os.getenv("FANDUEL_COMPETITION_ID", "10547864"))
FANDUEL_EVENT_TYPE_ID = int(os.getenv("FANDUEL_EVENT_TYPE_ID", "7522"))
FANDUEL_REGION = os.getenv("FANDUEL_REGION", "NY")
FANDUEL_REQUEST_TIMEOUT = int(os.getenv("FANDUEL_REQUEST_TIMEOUT", "20"))
FANDUEL_RATE_LIMIT_DELAY = float(os.getenv("FANDUEL_RATE_LIMIT_DELAY", "0.5"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://sportsbook.fanduel.com",
    "Referer": "https://sportsbook.fanduel.com/",
    "x-sportsbook-region": FANDUEL_REGION,
}

PROP_TABS = {
    "points": "player-points",
    "rebounds": "player-rebounds",
    "assists": "player-assists",
    "threes": "player-threes",
}

STAT_TYPE_MAP = {
    "Points": "points",
    "Rebounds": "rebounds",
    "Assists": "assists",
    "Threes": "threes",
    "3-Pointers": "threes",
    "Three Pointers": "threes",
}

PLAYER_NAME_ALIASES = {
    "carlton carrington": "Bub Carrington",
    "cam johnson": "Cameron Johnson",
}


def _sleep_for_rate_limit() -> None:
    if FANDUEL_RATE_LIMIT_DELAY > 0:
        time.sleep(FANDUEL_RATE_LIMIT_DELAY)


def _normalize_text(value: str) -> str:
    stripped = "".join(
        char for char in unicodedata.normalize("NFD", value) if unicodedata.category(char) != "Mn"
    )
    stripped = stripped.lower().replace("'", "").replace(".", "")
    stripped = re.sub(r"[^a-z0-9]+", " ", stripped)
    return re.sub(r"\s+", " ", stripped).strip()


def _payload(payload_type: str, payload: Any, external_id: str | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "source": "fanduel",
        "payload_type": payload_type,
        "external_id": external_id,
        "context": context or {},
        "payload": payload,
        "captured_at": datetime.utcnow(),
    }


def _team_aliases(game: dict[str, Any], side: str) -> set[str]:
    team_id_key = f"{side}_team_id"
    abbreviation_key = f"{side}_team_abbreviation"
    aliases = {_normalize_text(str(game.get(team_id_key, ""))), _normalize_text(str(game.get(abbreviation_key, "")))}
    if game.get(side + "_team_name"):
        full_name = _normalize_text(game[side + "_team_name"])
        aliases.add(full_name)
        words = full_name.split()
        if words:
            aliases.add(words[-1])
        if len(words) > 1:
            aliases.add(" ".join(words[-2:]))
    return {alias for alias in aliases if alias and not alias.isdigit()}


def _match_event_to_game(event_name: str, game: dict[str, Any]) -> bool:
    normalized_event_name = _normalize_text(event_name)
    home_aliases = _team_aliases(game, "home")
    away_aliases = _team_aliases(game, "away")
    return any(alias in normalized_event_name for alias in home_aliases) and any(alias in normalized_event_name for alias in away_aliases)


def _resolve_player_identity(player_name: str, player_id_map: dict[str, str]) -> tuple[str | None, str]:
    exact_match = player_id_map.get(player_name)
    if exact_match:
        return exact_match, player_name

    normalized_player_name = _normalize_text(player_name)
    alias_name = PLAYER_NAME_ALIASES.get(normalized_player_name)
    if alias_name:
        alias_match = player_id_map.get(alias_name)
        if alias_match:
            return alias_match, alias_name

    for candidate_name, candidate_id in player_id_map.items():
        if _normalize_text(candidate_name) == normalized_player_name:
            return candidate_id, candidate_name

    for candidate_name, candidate_id in player_id_map.items():
        normalized_candidate = _normalize_text(candidate_name)
        if normalized_player_name in normalized_candidate or normalized_candidate in normalized_player_name:
            return candidate_id, candidate_name

    return None, player_name


def _load_recent_player_team_context() -> dict[str, str]:
    with session_scope() as session:
        rows = (
            session.query(
                HistoricalGameLog.player_id,
                HistoricalGameLog.team,
                HistoricalGameLog.game_date,
            )
            .order_by(HistoricalGameLog.player_id, HistoricalGameLog.game_date.desc())
            .all()
        )

    player_team_by_id: dict[str, str] = {}
    for player_id, team, _ in rows:
        normalized_player_id = str(player_id)
        if normalized_player_id in player_team_by_id:
            continue
        if not team:
            continue
        player_team_by_id[normalized_player_id] = str(team)
    return player_team_by_id


def fetch_nba_events(client: httpx.Client) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        response = client.get(
            FANDUEL_COMPETITION_URL,
            params={
                "_ak": FANDUEL_AK,
                "eventTypeId": str(FANDUEL_EVENT_TYPE_ID),
                "competitionId": str(FANDUEL_COMPETITION_ID),
                "tabId": "SCHEDULE",
            },
        )
        response.raise_for_status()
        _sleep_for_rate_limit()
        data = response.json()

        events = data.get("attachments", {}).get("events", {})
        parsed = [
            {
                "event_id": str(event["eventId"]),
                "event_name": event.get("name", ""),
            }
            for event in events.values()
        ]
        payloads = [_payload("competition_schedule", data)]
        return parsed, payloads
    except Exception:
        logger.exception("Failed to fetch FanDuel NBA events")
        return [], []


def fetch_event_props(client: httpx.Client, event_id: str, stat_key: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    tab = PROP_TABS.get(stat_key)
    if not tab:
        return None, []

    try:
        response = client.get(
            FANDUEL_EVENT_URL,
            params={
                "_ak": FANDUEL_AK,
                "eventId": event_id,
                "tab": tab,
            },
        )
        response.raise_for_status()
        _sleep_for_rate_limit()
        data = response.json()
        return data, [_payload("event_page", data, external_id=event_id, context={"tab": tab, "stat_key": stat_key})]
    except Exception:
        logger.exception("Failed to fetch FanDuel props for event %s stat %s", event_id, stat_key)
        return None, []


def build_event_mappings(fd_events: list[dict[str, Any]], captured_at: datetime) -> list[dict[str, Any]]:
    today_games, _ = get_todays_games_bundle()
    tomorrow_games, _ = get_todays_games_bundle(date.today() + timedelta(days=1))
    all_games = today_games + tomorrow_games

    event_mappings: list[dict[str, Any]] = []
    for event in fd_events:
        matched_game = next((game for game in all_games if _match_event_to_game(event["event_name"], game)), None)
        event_mappings.append(
            {
                "sportsbook": "fanduel",
                "event_id": event["event_id"],
                "event_name": event["event_name"],
                "nba_game_id": matched_game["game_id"] if matched_game else None,
                "home_team_abbreviation": matched_game["home_team_abbreviation"] if matched_game else None,
                "away_team_abbreviation": matched_game["away_team_abbreviation"] if matched_game else None,
                "captured_at": captured_at,
            }
        )
    return event_mappings


def parse_event_props(
    event_mapping: dict[str, Any],
    raw_data: dict[str, Any],
    player_id_map: dict[str, str],
    player_team_context: dict[str, str],
    captured_at: datetime,
) -> list[dict[str, Any]]:
    props: list[dict[str, Any]] = []
    markets = raw_data.get("attachments", {}).get("markets", {})
    home_team = event_mapping.get("home_team_abbreviation")
    away_team = event_mapping.get("away_team_abbreviation")
    event_teams = {team for team in (home_team, away_team) if team}

    for market in markets.values():
        if not isinstance(market, dict):
            continue

        market_name = market.get("marketName", "")
        parts = market_name.split(" - ", 1)
        if len(parts) != 2:
            continue

        player_name = parts[0].strip()
        stat_label = parts[1].strip()
        stat_type = STAT_TYPE_MAP.get(stat_label)
        if not stat_type:
            continue

        line = None
        over_odds = None
        under_odds = None
        for runner in market.get("runners") or []:
            result_type = (runner.get("result") or {}).get("type", "").upper()
            handicap = runner.get("handicap")
            american_odds = runner.get("winRunnerOdds", {}).get("americanDisplayOdds", {}).get("americanOddsInt")
            if handicap is not None:
                line = float(handicap)
            if result_type == "OVER":
                over_odds = american_odds
            elif result_type == "UNDER":
                under_odds = american_odds

        if line is None or over_odds is None or under_odds is None:
            continue

        player_id, canonical_player_name = _resolve_player_identity(player_name, player_id_map)
        if not player_id:
            logger.warning("Could not map FanDuel player name '%s'", player_name)
            continue

        player_team = player_team_context.get(str(player_id))
        if event_teams and player_team not in event_teams:
            continue

        opponent = None
        if player_team == home_team:
            opponent = away_team
        elif player_team == away_team:
            opponent = home_team

        if not event_mapping.get("nba_game_id"):
            logger.warning("Skipping FanDuel event %s because it has no NBA game mapping", event_mapping["event_id"])
            continue

        props.append(
            {
                "game_id": event_mapping["nba_game_id"],
                "player_id": player_id,
                "player_name": canonical_player_name,
                "team": player_team,
                "opponent": opponent,
                "stat_type": stat_type,
                "line": line,
                "over_odds": int(over_odds),
                "under_odds": int(under_odds),
                "captured_at": captured_at,
                "sportsbook": "fanduel",
                "event_id": event_mapping["event_id"],
                "event_name": event_mapping["event_name"],
            }
        )

    return props


def fetch_current_prop_board() -> dict[str, Any]:
    player_id_map = get_player_id_map()
    player_team_context = _load_recent_player_team_context()
    payloads: list[dict[str, Any]] = []
    captured_at = datetime.utcnow()

    with httpx.Client(headers=HEADERS, timeout=FANDUEL_REQUEST_TIMEOUT) as client:
        fd_events, schedule_payloads = fetch_nba_events(client)
        payloads.extend(schedule_payloads)
        if not fd_events:
            return {"props": [], "event_mappings": [], "payloads": payloads, "captured_at": captured_at}

        event_mappings = build_event_mappings(fd_events, captured_at=captured_at)
        event_mapping_by_id = {mapping["event_id"]: mapping for mapping in event_mappings}

        all_props: list[dict[str, Any]] = []
        for event in fd_events:
            mapping = event_mapping_by_id[event["event_id"]]
            if not mapping.get("nba_game_id"):
                continue

            for stat_key in PROP_TABS:
                raw_data, event_payloads = fetch_event_props(client, event["event_id"], stat_key)
                payloads.extend(event_payloads)
                if not raw_data:
                    continue
                all_props.extend(
                    parse_event_props(
                        mapping,
                        raw_data,
                        player_id_map,
                        player_team_context,
                        captured_at=captured_at,
                    )
                )

    return {"props": all_props, "event_mappings": event_mappings, "payloads": payloads, "captured_at": captured_at}


def scrape_props() -> list[dict[str, Any]]:
    return fetch_current_prop_board()["props"]
