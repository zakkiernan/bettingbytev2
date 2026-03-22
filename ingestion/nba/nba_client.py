from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from json import JSONDecodeError
from typing import Any, Callable

import requests
from nba_api.live.nba.endpoints import boxscore as live_boxscore
from nba_api.live.nba.endpoints import scoreboard as live_scoreboard
from nba_api.stats.endpoints import (
    boxscoreadvancedv3,
    boxscorehustlev2,
    boxscorematchupsv3,
    boxscoreplayertrackv3,
    boxscoresummaryv3,
    boxscoretraditionalv3,
    boxscoreusagev3,
    leaguedashlineups,
    leaguedashplayerclutch,
    leaguedashplayershotlocations,
    leaguedashptdefend,
    leaguedashptstats,
    leaguedashptteamdefend,
    leaguedashteamstats,
    leaguegamelog,
    leaguehustlestatsplayer,
    playbyplayv3,
    scoreboardv3,
    shotchartdetail,
    synergyplaytypes,
    teamplayeronoffdetails,
    winprobabilitypbp,
)
from nba_api.stats.library.http import NBAStatsHTTP
from nba_api.stats.static import players, teams

logger = logging.getLogger(__name__)

NBA_REQUEST_TIMEOUT = int(os.getenv("NBA_REQUEST_TIMEOUT", "30"))
NBA_REQUEST_RETRIES = int(os.getenv("NBA_REQUEST_RETRIES", "3"))
NBA_RETRY_BACKOFF_SECONDS = float(os.getenv("NBA_RETRY_BACKOFF_SECONDS", "1.5"))
RATE_LIMIT_DELAY = float(os.getenv("NBA_RATE_LIMIT_DELAY", "0.6"))
HEAVY_RATE_LIMIT_DELAY = float(os.getenv("NBA_HEAVY_RATE_LIMIT_DELAY", "1.0"))
DEFAULT_SEASON = os.getenv("NBA_DEFAULT_SEASON", "2025-26")
PLAYER_TRACKING_MEASURE_TYPES = ("CatchShoot", "PullUpShot", "Drives")
PLAYER_DEFENSIVE_TRACKING_CATEGORIES = (
    "Overall",
    "3 Pointers",
    "2 Pointers",
    "Less Than 6Ft",
    "Less Than 10Ft",
    "Greater Than 15Ft",
)
SHOT_LOCATION_ZONE_FIELD_PREFIXES = {
    "Restricted Area": "restricted_area",
    "In The Paint (Non-RA)": "in_the_paint",
    "Mid-Range": "mid_range",
    "Left Corner 3": "left_corner_3",
    "Right Corner 3": "right_corner_3",
    "Above the Break 3": "above_the_break_3",
    "Backcourt": "backcourt",
}


def _sleep_for_delay(delay_seconds: float) -> None:
    if delay_seconds > 0:
        time.sleep(delay_seconds)


def _sleep_for_rate_limit() -> None:
    _sleep_for_delay(RATE_LIMIT_DELAY)


def _call_with_retries(
    label: str,
    fetcher: Callable[[], Any],
    *,
    identifier: str | None = None,
    retries: int | None = None,
    retry_predicate: Callable[[Exception], bool] | None = None,
    backoff_seconds: float | None = None,
):
    total_attempts = max(int(retries if retries is not None else NBA_REQUEST_RETRIES), 1)
    sleep_base = NBA_RETRY_BACKOFF_SECONDS if backoff_seconds is None else backoff_seconds
    last_exc: Exception | None = None
    for attempt in range(1, total_attempts + 1):
        try:
            return fetcher()
        except Exception as exc:
            last_exc = exc
            if retry_predicate is not None and not retry_predicate(exc):
                break
            if attempt >= total_attempts:
                break
            sleep_seconds = sleep_base * attempt
            if identifier:
                logger.warning(
                    "Retrying %s for %s after attempt %s/%s failed: %s",
                    label,
                    identifier,
                    attempt,
                    total_attempts,
                    exc,
                )
            else:
                logger.warning(
                    "Retrying %s after attempt %s/%s failed: %s",
                    label,
                    attempt,
                    total_attempts,
                    exc,
                )
            time.sleep(sleep_seconds)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"{label} failed without raising an exception")


def _format_exception_message(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        return exc.__class__.__name__
    return f"{exc.__class__.__name__}: {message}"




def _is_missing(value: Any) -> bool:
    if value in (None, ""):
        return True
    try:
        return value != value
    except Exception:
        return False


def _to_float(value: Any) -> float | None:
    if _is_missing(value):
        return None
    return float(value)


def _to_int(value: Any) -> int | None:
    if _is_missing(value):
        return None
    return int(value)


def _to_str(value: Any) -> str | None:
    if _is_missing(value):
        return None
    return str(value)


def _parse_minutes(value: Any) -> float | None:
    if _is_missing(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        if value.startswith("PT"):
            match = re.fullmatch(r"PT(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", value)
            if match:
                minutes = float(match.group(1) or 0)
                seconds = float(match.group(2) or 0)
                return minutes + (seconds / 60)
        if ":" in value:
            minutes, seconds = value.split(":", 1)
            return float(minutes) + (float(seconds) / 60)
    return _to_float(value)


def _to_bool(value: Any) -> bool | None:
    if _is_missing(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "t", "yes", "y"}:
            return True
        if normalized in {"0", "false", "f", "no", "n"}:
            return False
    raise ValueError(f"Unsupported boolean value: {value!r}")


def _to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def _strip_accents(name: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFD", name) if unicodedata.category(char) != "Mn")


def _payload(source: str, payload_type: str, payload: Any, external_id: str | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "source": source,
        "payload_type": payload_type,
        "external_id": external_id,
        "context": context or {},
        "payload": payload,
        "captured_at": datetime.utcnow(),
    }


def _failure_payload(
    source: str,
    payload_type: str,
    *,
    endpoint: str,
    error: Exception,
    identifier: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error_payload = {
        "status": "error",
        "endpoint": endpoint,
        "identifier": identifier,
        "error_type": error.__class__.__name__,
        "error_message": _format_exception_message(error),
    }
    error_context = dict(context or {})
    error_context.update({
        "status": "error",
        "endpoint": endpoint,
        "identifier": identifier,
        "error_type": error.__class__.__name__,
        "error_message": _format_exception_message(error),
    })
    return _payload(
        source,
        payload_type,
        error_payload,
        external_id=identifier,
        context=error_context,
    )


@lru_cache(maxsize=1)
def _team_lookup() -> dict[str, dict[str, str]]:
    return {
        str(team["id"]): {
            "full_name": team["full_name"],
            "abbreviation": team["abbreviation"],
        }
        for team in teams.get_teams()
    }


@lru_cache(maxsize=1)
def get_static_teams() -> list[dict[str, Any]]:
    static_teams: list[dict[str, Any]] = []
    for team in teams.get_teams():
        static_teams.append(
            {
                "team_id": str(team["id"]),
                "abbreviation": team["abbreviation"],
                "full_name": team["full_name"],
                "city": team.get("city"),
                "nickname": team.get("nickname"),
                "conference": team.get("conference"),
                "division": team.get("division"),
                "is_active": True,
            }
        )
    return static_teams


@lru_cache(maxsize=1)
def get_static_players() -> list[dict[str, Any]]:
    static_players: list[dict[str, Any]] = []
    for player in players.get_players():
        full_name = player["full_name"]
        first_name, _, last_name = full_name.partition(" ")
        static_players.append(
            {
                "player_id": str(player["id"]),
                "full_name": full_name,
                "first_name": player.get("first_name") or first_name,
                "last_name": player.get("last_name") or (last_name or None),
                "is_active": bool(player.get("is_active", True)),
            }
        )
    return static_players


@lru_cache(maxsize=1)
def get_player_id_map() -> dict[str, str]:
    player_map: dict[str, str] = {}
    for player in players.get_players():
        full_name = player["full_name"]
        player_id = str(player["id"])
        player_map[full_name] = player_id

        stripped_name = _strip_accents(full_name)
        if stripped_name != full_name:
            player_map[stripped_name] = player_id

    return player_map


def _normalize_matchup(matchup: str | None) -> tuple[bool, str | None]:
    if not matchup:
        return False, None
    if " vs. " in matchup:
        return True, matchup.split(" vs. ", 1)[1].strip()
    if " @ " in matchup:
        return False, matchup.split(" @ ", 1)[1].strip()
    return False, None


def _result_set_to_dicts(result_set: dict[str, Any]) -> list[dict[str, Any]]:
    headers = result_set.get("headers", [])
    rows = result_set.get("rowSet", [])
    return [dict(zip(headers, row)) for row in rows]


def _extract_result_set_rows(data: dict[str, Any], result_set_name: str | None = None) -> list[dict[str, Any]]:
    result_sets = data.get("resultSets") or data.get("resultSet")

    if isinstance(result_sets, dict):
        if result_set_name and isinstance(result_sets.get(result_set_name), dict):
            return _result_set_to_dicts(result_sets[result_set_name])
        if "headers" in result_sets and "rowSet" in result_sets:
            return _result_set_to_dicts(result_sets)
        for value in result_sets.values():
            if isinstance(value, dict) and value.get("name") == result_set_name:
                return _result_set_to_dicts(value)

    if isinstance(result_sets, list):
        for result_set in result_sets:
            if not isinstance(result_set, dict):
                continue
            if result_set_name is None or result_set.get("name") == result_set_name:
                return _result_set_to_dicts(result_set)

    return []


def _player_name_from_row(
    row: dict[str, Any],
    *,
    full_key: str | None = None,
    first_key: str | None = None,
    last_key: str | None = None,
) -> str | None:
    if full_key and row.get(full_key):
        return str(row[full_key])
    parts = [str(row[key]).strip() for key in (first_key, last_key) if key and row.get(key)]
    if parts:
        return " ".join(parts).strip()
    return None


def _normalize_scoreboard_games(raw_games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    team_lookup = _team_lookup()
    games: list[dict[str, Any]] = []
    for game in raw_games:
        home_id = str(game["homeTeam"]["teamId"])
        away_id = str(game["awayTeam"]["teamId"])
        games.append(
            {
                "game_id": str(game["gameId"]),
                "season": DEFAULT_SEASON,
                "game_date": _to_datetime(game.get("gameEt") or game.get("gameDateEst")),
                "home_team_id": home_id,
                "away_team_id": away_id,
                "home_team_name": team_lookup.get(home_id, {}).get("full_name"),
                "away_team_name": team_lookup.get(away_id, {}).get("full_name"),
                "home_team_abbreviation": team_lookup.get(home_id, {}).get("abbreviation"),
                "away_team_abbreviation": team_lookup.get(away_id, {}).get("abbreviation"),
                "game_status": _to_int(game.get("gameStatus")),
                "status_text": game.get("gameStatusText"),
                "game_time_utc": _to_datetime(game.get("gameEtUTC") or game.get("gameEt")),
                "is_in_season_tournament": _to_bool(game.get("isInSeasonTournament")),
            }
        )
    return games


def get_todays_games_bundle(game_date: date | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if game_date is None:
        game_date = date.today()

    try:
        data = _call_with_retries(
            "NBA schedule scoreboard",
            lambda: scoreboardv3.ScoreboardV3(
                game_date=game_date.strftime("%m/%d/%Y"),
                timeout=NBA_REQUEST_TIMEOUT,
            ).get_dict(),
            identifier=game_date.isoformat(),
        )
        _sleep_for_rate_limit()
        games = _normalize_scoreboard_games(data["scoreboard"]["games"])
        return games, [_payload("nba", "scoreboard_schedule", data, context={"game_date": game_date.isoformat()})]
    except JSONDecodeError as exc:
        # The schedule endpoint occasionally returns empty/non-JSON bodies for future dates.
        if game_date > date.today():
            logger.warning("NBA scoreboard returned malformed schedule data for %s; treating as no future games.", game_date)
            return [], []
        logger.exception("Failed to fetch NBA scoreboard for %s", game_date)
        return [], [_failure_payload("nba", "scoreboard_schedule", endpoint="scoreboard_schedule", error=exc, identifier=game_date.isoformat(), context={"game_date": game_date.isoformat()})]
    except Exception as exc:
        logger.exception("Failed to fetch NBA scoreboard for %s", game_date)
        return [], [_failure_payload("nba", "scoreboard_schedule", endpoint="scoreboard_schedule", error=exc, identifier=game_date.isoformat(), context={"game_date": game_date.isoformat()})]


def get_todays_games(game_date: date | None = None) -> list[dict[str, Any]]:
    games, _ = get_todays_games_bundle(game_date)
    return games


def get_live_scoreboard_bundle() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        data = _call_with_retries(
            "live NBA scoreboard",
            lambda: live_scoreboard.ScoreBoard().get_dict(),
        )
        _sleep_for_rate_limit()

        captured_at = datetime.utcnow()
        games: list[dict[str, Any]] = []
        for game in data["scoreboard"]["games"]:
            games.append(
                {
                    "game_id": str(game["gameId"]),
                    "season": DEFAULT_SEASON,
                    "game_date": _to_datetime(game.get("gameEt")),
                    "home_team_id": str(game["homeTeam"]["teamId"]),
                    "away_team_id": str(game["awayTeam"]["teamId"]),
                    "home_team_score": _to_int(game["homeTeam"].get("score")),
                    "away_team_score": _to_int(game["awayTeam"].get("score")),
                    "period": _to_int(game.get("period")),
                    "game_clock": game.get("gameClock"),
                    "game_status": _to_int(game.get("gameStatus")),
                    "status_text": game.get("gameStatusText"),
                    "game_time_utc": _to_datetime(game.get("gameEt")),
                    "captured_at": captured_at,
                }
            )

        payload = _payload("nba", "live_scoreboard", data)
        return games, [payload]
    except Exception as exc:
        logger.exception("Failed to fetch live NBA scoreboard")
        return [], [_failure_payload("nba", "live_scoreboard", endpoint="live_scoreboard", error=exc)]


def get_live_scoreboard() -> list[dict[str, Any]]:
    games, _ = get_live_scoreboard_bundle()
    return games


def get_live_boxscore_bundle(game_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        data = _call_with_retries(
            "live NBA boxscore",
            lambda: live_boxscore.BoxScore(game_id=game_id).get_dict(),
            identifier=game_id,
        )
        _sleep_for_rate_limit()

        captured_at = datetime.utcnow()
        players_data: list[dict[str, Any]] = []
        for side in ("homeTeam", "awayTeam"):
            team_data = data["game"][side]
            for player in team_data["players"]:
                stats = player.get("statistics", {})
                players_data.append(
                    {
                        "game_id": game_id,
                        "player_id": str(player["personId"]),
                        "player_name": player["name"],
                        "team_id": str(team_data["teamId"]),
                        "minutes": _parse_minutes(stats.get("minutesCalculated")),
                        "points": _to_float(stats.get("points")),
                        "rebounds": _to_float(stats.get("reboundsTotal")),
                        "assists": _to_float(stats.get("assists")),
                        "steals": _to_float(stats.get("steals")),
                        "blocks": _to_float(stats.get("blocks")),
                        "turnovers": _to_float(stats.get("turnovers")),
                        "field_goals_made": _to_float(stats.get("fieldGoalsMade")),
                        "field_goals_attempted": _to_float(stats.get("fieldGoalsAttempted")),
                        "threes_made": _to_float(stats.get("threePointersMade")),
                        "threes_attempted": _to_float(stats.get("threePointersAttempted")),
                        "free_throws_made": _to_float(stats.get("freeThrowsMade")),
                        "free_throws_attempted": _to_float(stats.get("freeThrowsAttempted")),
                        "fouls": _to_float(stats.get("foulsPersonal")),
                        "plus_minus": _to_float(stats.get("plusMinusPoints")),
                        "on_court": _to_bool(player.get("oncourt")),
                        "starter": _to_bool(player.get("starter")),
                        "captured_at": captured_at,
                    }
                )

        payload = _payload("nba", "live_boxscore", data, external_id=game_id)
        return players_data, [payload]
    except Exception as exc:
        logger.exception("Failed to fetch live boxscore for game %s", game_id)
        return [], [_failure_payload("nba", "live_boxscore", endpoint="live_boxscore", error=exc, identifier=game_id)]


def get_live_boxscore(game_id: str) -> list[dict[str, Any]]:
    players_data, _ = get_live_boxscore_bundle(game_id)
    return players_data

def get_historical_player_game_logs_bundle(
    season: str = DEFAULT_SEASON,
    season_type_all_star: str = "Regular Season",
    date_from_nullable: str = "",
    date_to_nullable: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        endpoint = _call_with_retries(
            "historical NBA game logs",
            lambda: leaguegamelog.LeagueGameLog(
                player_or_team_abbreviation="P",
                season=season,
                season_type_all_star=season_type_all_star,
                date_from_nullable=date_from_nullable,
                date_to_nullable=date_to_nullable,
                timeout=NBA_REQUEST_TIMEOUT,
            ),
            identifier=season,
        )
        raw_data = endpoint.get_dict()
        rows = endpoint.get_data_frames()[0].to_dict("records")
        _sleep_for_rate_limit()

        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            is_home, opponent = _normalize_matchup(row.get("MATCHUP"))
            normalized_rows.append(
                {
                    "game_id": str(row["GAME_ID"]),
                    "game_date": _to_datetime(row.get("GAME_DATE")),
                    "player_id": str(row["PLAYER_ID"]),
                    "player_name": row["PLAYER_NAME"],
                    "team": row.get("TEAM_ABBREVIATION") or row.get("TEAM_NAME"),
                    "opponent": opponent,
                    "is_home": is_home,
                    "minutes": _parse_minutes(row.get("MIN")),
                    "points": _to_float(row.get("PTS")),
                    "rebounds": _to_float(row.get("REB")),
                    "assists": _to_float(row.get("AST")),
                    "steals": _to_float(row.get("STL")),
                    "blocks": _to_float(row.get("BLK")),
                    "turnovers": _to_float(row.get("TOV")),
                    "threes_made": _to_float(row.get("FG3M")),
                    "threes_attempted": _to_float(row.get("FG3A")),
                    "field_goals_made": _to_float(row.get("FGM")),
                    "field_goals_attempted": _to_float(row.get("FGA")),
                    "free_throws_made": _to_float(row.get("FTM")),
                    "free_throws_attempted": _to_float(row.get("FTA")),
                    "plus_minus": _to_float(row.get("PLUS_MINUS")),
                    "fantasy_points": _to_float(row.get("FANTASY_PTS")),
                }
            )

        payload = _payload(
            "nba",
            "historical_game_logs",
            raw_data,
            context={
                "season": season,
                "season_type": season_type_all_star,
                "date_from": date_from_nullable,
                "date_to": date_to_nullable,
            },
        )
        return normalized_rows, [payload]
    except Exception as exc:
        logger.exception("Failed to fetch historical NBA game logs for season %s", season)
        return [], [_failure_payload(
            "nba",
            "historical_player_game_logs",
            endpoint="historical_player_game_logs",
            error=exc,
            identifier=season,
            context={
                "season": season,
                "season_type": season_type_all_star,
                "date_from": date_from_nullable,
                "date_to": date_to_nullable,
            },
        )]


def get_historical_player_game_logs(
    season: str = DEFAULT_SEASON,
    season_type_all_star: str = "Regular Season",
    date_from_nullable: str = "",
    date_to_nullable: str = "",
) -> list[dict[str, Any]]:
    rows, _ = get_historical_player_game_logs_bundle(
        season=season,
        season_type_all_star=season_type_all_star,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
    )
    return rows


def get_traditional_boxscore(game_id: str) -> list[dict[str, Any]]:
    try:
        endpoint = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id, timeout=NBA_REQUEST_TIMEOUT)
        data = endpoint.get_dict()["boxScoreTraditional"]
        _sleep_for_rate_limit()

        players_data: list[dict[str, Any]] = []
        for side in ("homeTeam", "awayTeam"):
            team_data = data[side]
            for player in team_data["players"]:
                stats = player.get("statistics", {})
                players_data.append(
                    {
                        "game_id": data["gameId"],
                        "player_id": str(player["personId"]),
                        "player_name": f"{player['firstName']} {player['familyName']}".strip(),
                        "team_id": str(team_data["teamId"]),
                        "team_abbreviation": team_data.get("teamTricode"),
                        "minutes": _parse_minutes(stats.get("minutes")),
                        "points": _to_float(stats.get("points")),
                        "rebounds": _to_float(stats.get("reboundsTotal")),
                        "assists": _to_float(stats.get("assists")),
                        "steals": _to_float(stats.get("steals")),
                        "blocks": _to_float(stats.get("blocks")),
                        "turnovers": _to_float(stats.get("turnovers")),
                        "field_goals_made": _to_float(stats.get("fieldGoalsMade")),
                        "field_goals_attempted": _to_float(stats.get("fieldGoalsAttempted")),
                        "threes_made": _to_float(stats.get("threePointersMade")),
                        "threes_attempted": _to_float(stats.get("threePointersAttempted")),
                        "free_throws_made": _to_float(stats.get("freeThrowsMade")),
                        "free_throws_attempted": _to_float(stats.get("freeThrowsAttempted")),
                        "plus_minus": _to_float(stats.get("plusMinusPoints")),
                    }
                )
        return players_data
    except Exception:
        logger.exception("Failed to fetch traditional boxscore for game %s", game_id)
        return []


def get_boxscore_summary_bundle(game_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    try:
        endpoint = _call_with_retries(
            "NBA boxscore summary",
            lambda: boxscoresummaryv3.BoxScoreSummaryV3(game_id=game_id, timeout=NBA_REQUEST_TIMEOUT),
            identifier=game_id,
        )
        data = endpoint.get_dict()
        _sleep_for_rate_limit()
        return data, [_payload("nba", "boxscore_summary", data, external_id=game_id)]
    except Exception as exc:
        logger.exception("Failed to fetch boxscore summary for game %s", game_id)
        return None, [_failure_payload("nba", "boxscore_summary", endpoint="boxscore_summary", error=exc, identifier=game_id)]


def get_boxscore_summary(game_id: str) -> dict[str, Any] | None:
    data, _ = get_boxscore_summary_bundle(game_id)
    return data


def normalize_game_summary(summary_data: dict[str, Any], season: str = DEFAULT_SEASON) -> dict[str, Any] | None:
    if not summary_data:
        return None

    summary = summary_data.get("boxScoreSummary", {})
    if not summary:
        return None

    home_team = summary.get("homeTeam") or {}
    away_team = summary.get("awayTeam") or {}

    return {
        "game_id": str(summary.get("gameId")),
        "season": season,
        "game_date": _to_datetime(summary.get("gameEt") or summary.get("gameTimeUTC")),
        "home_team_id": str(home_team.get("teamId")) if home_team.get("teamId") is not None else None,
        "away_team_id": str(away_team.get("teamId")) if away_team.get("teamId") is not None else None,
        "home_team_abbreviation": home_team.get("teamTricode"),
        "away_team_abbreviation": away_team.get("teamTricode"),
        "game_status": _to_int(summary.get("gameStatus")),
        "status_text": summary.get("gameStatusText"),
        "game_time_utc": _to_datetime(summary.get("gameTimeUTC") or summary.get("gameEt")),
        "is_in_season_tournament": None,
    }


def get_advanced_boxscore_bundle(game_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        endpoint = _call_with_retries(
            "NBA advanced boxscore",
            lambda: boxscoreadvancedv3.BoxScoreAdvancedV3(game_id=game_id, timeout=NBA_REQUEST_TIMEOUT),
            identifier=game_id,
        )
        data = endpoint.get_dict()["boxScoreAdvanced"]
        _sleep_for_rate_limit()

        players_data: list[dict[str, Any]] = []
        for side in ("homeTeam", "awayTeam"):
            team_data = data[side]
            for player in team_data["players"]:
                stats = player.get("statistics", {})
                players_data.append(
                    {
                        "game_id": data["gameId"],
                        "player_id": str(player["personId"]),
                        "player_name": f"{player['firstName']} {player['familyName']}".strip(),
                        "usage_percentage": _to_float(stats.get("usagePercentage")),
                        "estimated_usage_percentage": _to_float(stats.get("estimatedUsagePercentage")),
                        "pace": _to_float(stats.get("pace")),
                        "pace_per40": _to_float(stats.get("pacePer40")),
                        "possessions": _to_float(stats.get("possessions")),
                        "offensive_rating": _to_float(stats.get("offensiveRating")),
                        "defensive_rating": _to_float(stats.get("defensiveRating")),
                        "net_rating": _to_float(stats.get("netRating")),
                        "true_shooting_percentage": _to_float(stats.get("trueShootingPercentage")),
                        "effective_field_goal_percentage": _to_float(stats.get("effectiveFieldGoalPercentage")),
                        "assist_percentage": _to_float(stats.get("assistPercentage")),
                        "assist_to_turnover": _to_float(stats.get("assistToTurnover")),
                        "offensive_rebound_percentage": _to_float(stats.get("offensiveReboundPercentage")),
                        "defensive_rebound_percentage": _to_float(stats.get("defensiveReboundPercentage")),
                        "pie": _to_float(stats.get("PIE")),
                    }
                )
        return players_data, [_payload("nba", "advanced_boxscore", data, external_id=game_id)]
    except Exception as exc:
        logger.exception("Failed to fetch advanced boxscore for game %s", game_id)
        return [], [_failure_payload("nba", "advanced_boxscore", endpoint="advanced_boxscore", error=exc, identifier=game_id)]


def get_advanced_boxscore(game_id: str) -> list[dict[str, Any]]:
    players_data, _ = get_advanced_boxscore_bundle(game_id)
    return players_data


def get_player_tracking_bundle(game_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        endpoint = _call_with_retries(
            "NBA player tracking",
            lambda: boxscoreplayertrackv3.BoxScorePlayerTrackV3(game_id=game_id, timeout=NBA_REQUEST_TIMEOUT),
            identifier=game_id,
        )
        data = endpoint.get_dict()["boxScorePlayerTrack"]
        _sleep_for_rate_limit()

        players_data: list[dict[str, Any]] = []
        for side in ("homeTeam", "awayTeam"):
            team_data = data[side]
            for player in team_data["players"]:
                stats = player.get("statistics", {})
                players_data.append(
                    {
                        "game_id": data["gameId"],
                        "player_id": str(player["personId"]),
                        "player_name": f"{player['firstName']} {player['familyName']}".strip(),
                        "speed": _to_float(stats.get("speed")),
                        "distance": _to_float(stats.get("distance")),
                        "touches": _to_float(stats.get("touches")),
                        "passes": _to_float(stats.get("passes")),
                        "secondary_assists": _to_float(stats.get("secondaryAssists")),
                        "free_throw_assists": _to_float(stats.get("freeThrowAssists")),
                        "rebound_chances_offensive": _to_float(stats.get("reboundChancesOffensive")),
                        "rebound_chances_defensive": _to_float(stats.get("reboundChancesDefensive")),
                        "rebound_chances_total": _to_float(stats.get("reboundChancesTotal")),
                        "contested_field_goals_made": _to_float(stats.get("contestedFieldGoalsMade")),
                        "contested_field_goals_attempted": _to_float(stats.get("contestedFieldGoalsAttempted")),
                        "uncontested_field_goals_made": _to_float(stats.get("uncontestedFieldGoalsMade")),
                        "uncontested_field_goals_attempted": _to_float(stats.get("uncontestedFieldGoalsAttempted")),
                        "defended_at_rim_field_goals_made": _to_float(stats.get("defendedAtRimFieldGoalsMade")),
                        "defended_at_rim_field_goals_attempted": _to_float(stats.get("defendedAtRimFieldGoalsAttempted")),
                    }
                )
        return players_data, [_payload("nba", "player_tracking", data, external_id=game_id)]
    except Exception as exc:
        logger.exception("Failed to fetch player tracking for game %s", game_id)
        return [], [_failure_payload("nba", "player_tracking", endpoint="player_tracking", error=exc, identifier=game_id)]


def get_player_tracking(game_id: str) -> list[dict[str, Any]]:
    players_data, _ = get_player_tracking_bundle(game_id)
    return players_data

def get_usage_boxscore(game_id: str) -> list[dict[str, Any]]:
    try:
        endpoint = boxscoreusagev3.BoxScoreUsageV3(game_id=game_id, timeout=NBA_REQUEST_TIMEOUT)
        data = endpoint.get_dict()["boxScoreUsage"]
        _sleep_for_rate_limit()

        players_data: list[dict[str, Any]] = []
        for side in ("homeTeam", "awayTeam"):
            team_data = data[side]
            for player in team_data["players"]:
                stats = player.get("statistics", {})
                players_data.append(
                    {
                        "game_id": data["gameId"],
                        "player_id": str(player["personId"]),
                        "player_name": f"{player['firstName']} {player['familyName']}".strip(),
                        "team_id": str(team_data["teamId"]),
                        "usage_percentage": _to_float(stats.get("usagePercentage")),
                        "minutes": _parse_minutes(stats.get("minutes")),
                        "percentage_points": _to_float(stats.get("percentagePoints")),
                        "percentage_assists": _to_float(stats.get("percentageAssists")),
                        "percentage_rebounds_total": _to_float(stats.get("percentageReboundsTotal")),
                        "percentage_turnovers": _to_float(stats.get("percentageTurnovers")),
                    }
                )
        return players_data
    except Exception:
        logger.exception("Failed to fetch usage boxscore for game %s", game_id)
        return []




def get_play_by_play(game_id: str) -> list[dict[str, Any]]:
    try:
        endpoint = playbyplayv3.PlayByPlayV3(game_id=game_id, timeout=NBA_REQUEST_TIMEOUT)
        data = endpoint.get_dict()["game"]
        _sleep_for_rate_limit()
        return data.get("actions", [])
    except Exception:
        logger.exception("Failed to fetch play-by-play for game %s", game_id)
        return []


def get_team_defensive_stats_bundle(
    season: str = DEFAULT_SEASON,
    season_type_all_star: str = "Regular Season",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        advanced_team_stats = _call_with_retries(
            "NBA team defense advanced",
            lambda: leaguedashteamstats.LeagueDashTeamStats(
                season=season,
                season_type_all_star=season_type_all_star,
                measure_type_detailed_defense="Advanced",
                timeout=NBA_REQUEST_TIMEOUT,
            ),
            identifier=season,
        )
        advanced_raw = advanced_team_stats.get_dict()
        advanced_rows = _result_set_to_dicts(advanced_raw["resultSets"][0])
        _sleep_for_rate_limit()

        opponent_team_stats = _call_with_retries(
            "NBA team defense opponent",
            lambda: leaguedashteamstats.LeagueDashTeamStats(
                season=season,
                season_type_all_star=season_type_all_star,
                measure_type_detailed_defense="Opponent",
                timeout=NBA_REQUEST_TIMEOUT,
            ),
            identifier=season,
        )
        opponent_raw = opponent_team_stats.get_dict()
        opponent_rows = _result_set_to_dicts(opponent_raw["resultSets"][0])
        _sleep_for_rate_limit()

        pt_team_defense = _call_with_retries(
            "NBA team defense shot profile",
            lambda: leaguedashptteamdefend.LeagueDashPtTeamDefend(
                season=season,
                season_type_all_star=season_type_all_star,
                defense_category="Overall",
                timeout=NBA_REQUEST_TIMEOUT,
            ),
            identifier=season,
        )
        pt_raw = pt_team_defense.get_dict()
        pt_rows = _result_set_to_dicts(pt_raw["resultSets"][0])
        _sleep_for_rate_limit()

        defensive_data: dict[str, dict[str, Any]] = {}
        for row in advanced_rows:
            team_id = str(row["TEAM_ID"])
            defensive_data[team_id] = {
                "team_id": team_id,
                "team_name": row["TEAM_NAME"],
                "season": season,
                "defensive_rating": _to_float(row.get("DEF_RATING")),
                "estimated_defensive_rating": _to_float(row.get("E_DEF_RATING")),
                "pace": _to_float(row.get("PACE")),
                "estimated_pace": _to_float(row.get("E_PACE")),
            }

        for row in opponent_rows:
            team_id = str(row["TEAM_ID"])
            entry = defensive_data.setdefault(
                team_id,
                {
                    "team_id": team_id,
                    "team_name": row["TEAM_NAME"],
                    "season": season,
                },
            )
            entry.update(
                {
                    "opponent_points_per_game": _to_float(row.get("OPP_PTS")),
                    "opponent_field_goal_percentage": _to_float(row.get("OPP_FG_PCT")),
                    "opponent_three_point_percentage": _to_float(row.get("OPP_FG3_PCT")),
                }
            )

        for row in pt_rows:
            team_id = str(row["TEAM_ID"])
            entry = defensive_data.setdefault(
                team_id,
                {
                    "team_id": team_id,
                    "team_name": row["TEAM_NAME"],
                    "season": season,
                },
            )
            entry.update(
                {
                    "d_fg_pct_overall": _to_float(row.get("D_FG_PCT")),
                    "defended_field_goal_attempts": _to_float(row.get("D_FGA")),
                    "normal_fg_pct_overall": _to_float(row.get("NORMAL_FG_PCT")),
                    "d_pct_plusminus_overall": _to_float(row.get("PCT_PLUSMINUS")),
                }
            )

        payloads = [
            _payload("nba", "team_defense_advanced", advanced_raw, context={"season": season, "season_type": season_type_all_star}),
            _payload("nba", "team_defense_opponent", opponent_raw, context={"season": season, "season_type": season_type_all_star}),
            _payload("nba", "team_defense_pt", pt_raw, context={"season": season, "season_type": season_type_all_star}),
        ]
        return list(defensive_data.values()), payloads
    except Exception as exc:
        logger.exception("Failed to fetch team defensive stats for season %s", season)
        return [], [_failure_payload(
            "nba",
            "team_defense",
            endpoint="team_defense",
            error=exc,
            identifier=season,
            context={"season": season, "season_type": season_type_all_star},
        )]


def get_team_defensive_stats(
    season: str = DEFAULT_SEASON,
    season_type_all_star: str = "Regular Season",
) -> list[dict[str, Any]]:
    rows, _ = get_team_defensive_stats_bundle(season=season, season_type_all_star=season_type_all_star)
    return rows


def get_shot_chart_bundle(game_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        endpoint = _call_with_retries(
            "NBA shot chart detail",
            lambda: shotchartdetail.ShotChartDetail(
                team_id=0,
                player_id=0,
                game_id_nullable=game_id,
                season_nullable=DEFAULT_SEASON,
                context_measure_simple="FGA",
                timeout=NBA_REQUEST_TIMEOUT,
            ),
            identifier=game_id,
        )
        data = endpoint.get_dict()
        rows = _extract_result_set_rows(data, "Shot_Chart_Detail")
        _sleep_for_rate_limit()

        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            player_id = _to_str(row.get("PLAYER_ID"))
            team_id = _to_str(row.get("TEAM_ID"))
            if not player_id or not team_id:
                continue
            normalized_rows.append(
                {
                    "game_id": _to_str(row.get("GAME_ID")) or game_id,
                    "player_id": player_id,
                    "player_name": row.get("PLAYER_NAME"),
                    "team_id": team_id,
                    "event_type": row.get("EVENT_TYPE"),
                    "action_type": row.get("ACTION_TYPE"),
                    "shot_type": row.get("SHOT_TYPE"),
                    "shot_zone_basic": row.get("SHOT_ZONE_BASIC"),
                    "shot_zone_area": row.get("SHOT_ZONE_AREA"),
                    "shot_zone_range": row.get("SHOT_ZONE_RANGE"),
                    "shot_distance": _to_float(row.get("SHOT_DISTANCE")),
                    "loc_x": _to_float(row.get("LOC_X")),
                    "loc_y": _to_float(row.get("LOC_Y")),
                    "shot_made_flag": _to_bool(row.get("SHOT_MADE_FLAG")),
                    "period": _to_int(row.get("PERIOD")),
                    "minutes_remaining": _to_int(row.get("MINUTES_REMAINING")),
                    "seconds_remaining": _to_int(row.get("SECONDS_REMAINING")),
                    "htm": row.get("HTM"),
                    "vtm": row.get("VTM"),
                }
            )

        payload = _payload("nba", "shot_chart_detail", data, external_id=game_id)
        return normalized_rows, [payload]
    except Exception as exc:
        logger.exception("Failed to fetch shot chart detail for game %s", game_id)
        return [], [_failure_payload("nba", "shot_chart_detail", endpoint="shot_chart_detail", error=exc, identifier=game_id)]


def get_hustle_boxscore_bundle(game_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        endpoint = _call_with_retries(
            "NBA hustle boxscore",
            lambda: boxscorehustlev2.BoxScoreHustleV2(game_id=game_id, timeout=NBA_REQUEST_TIMEOUT),
            identifier=game_id,
        )
        data = endpoint.get_dict()
        rows = _extract_result_set_rows(data, "PlayerStats")
        _sleep_for_rate_limit()

        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            player_id = _to_str(row.get("personId"))
            team_id = _to_str(row.get("teamId"))
            player_name = _player_name_from_row(row, first_key="firstName", last_key="familyName")
            if not player_id or not team_id or not player_name:
                continue
            normalized_rows.append(
                {
                    "game_id": _to_str(row.get("gameId")) or game_id,
                    "player_id": player_id,
                    "player_name": player_name,
                    "team_id": team_id,
                    "minutes": _parse_minutes(row.get("minutes")),
                    "contested_shots_2pt": _to_float(row.get("contestedShots2pt")),
                    "contested_shots_3pt": _to_float(row.get("contestedShots3pt")),
                    "contested_shots": _to_float(row.get("contestedShots")),
                    "deflections": _to_float(row.get("deflections")),
                    "charges_drawn": _to_float(row.get("chargesDrawn")),
                    "screen_assists": _to_float(row.get("screenAssists")),
                    "screen_ast_pts": _to_float(row.get("screenAssistPoints")),
                    "loose_balls_recovered_offensive": _to_float(row.get("looseBallsRecoveredOffensive")),
                    "loose_balls_recovered_defensive": _to_float(row.get("looseBallsRecoveredDefensive")),
                    "loose_balls_recovered": _to_float(row.get("looseBallsRecoveredTotal")),
                    "box_outs_offensive": _to_float(row.get("offensiveBoxOuts")),
                    "box_outs_defensive": _to_float(row.get("defensiveBoxOuts")),
                    "box_outs": _to_float(row.get("boxOuts")),
                }
            )

        payload = _payload("nba", "hustle_boxscore", data, external_id=game_id)
        return normalized_rows, [payload]
    except Exception as exc:
        logger.exception("Failed to fetch hustle boxscore for game %s", game_id)
        return [], [_failure_payload("nba", "hustle_boxscore", endpoint="hustle_boxscore", error=exc, identifier=game_id)]


def get_matchup_boxscore_bundle(game_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        endpoint = _call_with_retries(
            "NBA matchup boxscore",
            lambda: boxscorematchupsv3.BoxScoreMatchupsV3(game_id=game_id, timeout=NBA_REQUEST_TIMEOUT),
            identifier=game_id,
        )
        data = endpoint.get_dict()
        rows = _extract_result_set_rows(data, "PlayerStats")
        _sleep_for_rate_limit()

        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            offense_player_id = _to_str(row.get("personIdOff"))
            defense_player_id = _to_str(row.get("personIdDef"))
            offense_player_name = _player_name_from_row(row, first_key="firstNameOff", last_key="familyNameOff")
            defense_player_name = _player_name_from_row(row, first_key="firstNameDef", last_key="familyNameDef")
            if not offense_player_id or not defense_player_id or not offense_player_name or not defense_player_name:
                continue
            normalized_rows.append(
                {
                    "game_id": _to_str(row.get("gameId")) or game_id,
                    "offense_player_id": offense_player_id,
                    "offense_player_name": offense_player_name,
                    "defense_player_id": defense_player_id,
                    "defense_player_name": defense_player_name,
                    "matchup_minutes": _parse_minutes(row.get("matchupMinutes")),
                    "matchup_minutes_sort": _parse_minutes(row.get("matchupMinutesSort")),
                    "partial_possessions": _to_float(row.get("partialPossessions")),
                    "player_points": _to_float(row.get("playerPoints")),
                    "switches_on": _to_float(row.get("switchesOn")),
                    "matchup_field_goals_made": _to_float(row.get("matchupFieldGoalsMade")),
                    "matchup_field_goals_attempted": _to_float(row.get("matchupFieldGoalsAttempted")),
                    "matchup_field_goal_percentage": _to_float(row.get("matchupFieldGoalsPercentage")),
                    "matchup_assists": _to_float(row.get("matchupAssists")),
                    "matchup_turnovers": _to_float(row.get("matchupTurnovers")),
                }
            )

        payload = _payload("nba", "matchup_boxscore", data, external_id=game_id)
        return normalized_rows, [payload]
    except Exception as exc:
        logger.exception("Failed to fetch matchup boxscore for game %s", game_id)
        return [], [_failure_payload("nba", "matchup_boxscore", endpoint="matchup_boxscore", error=exc, identifier=game_id)]


def get_win_probability_bundle(game_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        endpoint = _call_with_retries(
            "NBA win probability",
            lambda: winprobabilitypbp.WinProbabilityPBP(game_id=game_id, timeout=NBA_REQUEST_TIMEOUT),
            identifier=game_id,
        )
        data = endpoint.get_dict()
        rows = _extract_result_set_rows(data, "WinProbPBP")
        _sleep_for_rate_limit()

        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            event_num = _to_int(row.get("EVENT_NUM"))
            if event_num is None:
                continue
            description = row.get("DESCRIPTION")
            location = _to_int(row.get("LOCATION"))
            normalized_rows.append(
                {
                    "game_id": _to_str(row.get("GAME_ID")) or game_id,
                    "event_num": event_num,
                    "home_pct": _to_float(row.get("HOME_PCT")),
                    "visitor_pct": _to_float(row.get("VISITOR_PCT")),
                    "home_pts": _to_int(row.get("HOME_PTS")),
                    "visitor_pts": _to_int(row.get("VISITOR_PTS")),
                    "period": _to_int(row.get("PERIOD")),
                    "seconds_remaining": _to_float(row.get("SECONDS_REMAINING")),
                    "home_description": description if location == 1 else None,
                    "visitor_description": description if location == 2 else None,
                    "neutral_description": description if location not in {1, 2} else None,
                    "location": location,
                }
            )

        payload = _payload("nba", "win_probability_pbp", data, external_id=game_id)
        return normalized_rows, [payload]
    except Exception as exc:
        logger.exception("Failed to fetch win probability for game %s", game_id)
        return [], [_failure_payload("nba", "win_probability_pbp", endpoint="win_probability_pbp", error=exc, identifier=game_id)]


def get_player_clutch_stats_bundle(
    season: str = DEFAULT_SEASON,
    season_type_all_star: str = "Regular Season",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    clutch_time = "Last 5 Minutes"
    point_diff = 5
    try:
        endpoint = _call_with_retries(
            "NBA player clutch stats",
            lambda: leaguedashplayerclutch.LeagueDashPlayerClutch(
                season=season,
                season_type_all_star=season_type_all_star,
                clutch_time=clutch_time,
                ahead_behind="Ahead or Behind",
                point_diff=point_diff,
                timeout=NBA_REQUEST_TIMEOUT,
            ),
            identifier=season,
        )
        data = endpoint.get_dict()
        rows = _extract_result_set_rows(data, "LeagueDashPlayerClutch")
        _sleep_for_rate_limit()

        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            player_id = _to_str(row.get("PLAYER_ID"))
            team_id = _to_str(row.get("TEAM_ID"))
            if not player_id or not team_id:
                continue
            normalized_rows.append(
                {
                    "player_id": player_id,
                    "player_name": row.get("PLAYER_NAME"),
                    "team_id": team_id,
                    "team_abbreviation": row.get("TEAM_ABBREVIATION"),
                    "season": season,
                    "clutch_time": clutch_time,
                    "point_diff": point_diff,
                    "gp": _to_int(row.get("GP")),
                    "w": _to_int(row.get("W")),
                    "l": _to_int(row.get("L")),
                    "min": _parse_minutes(row.get("MIN")),
                    "fgm": _to_float(row.get("FGM")),
                    "fga": _to_float(row.get("FGA")),
                    "fg_pct": _to_float(row.get("FG_PCT")),
                    "fg3m": _to_float(row.get("FG3M")),
                    "fg3a": _to_float(row.get("FG3A")),
                    "fg3_pct": _to_float(row.get("FG3_PCT")),
                    "ftm": _to_float(row.get("FTM")),
                    "fta": _to_float(row.get("FTA")),
                    "ft_pct": _to_float(row.get("FT_PCT")),
                    "oreb": _to_float(row.get("OREB")),
                    "dreb": _to_float(row.get("DREB")),
                    "reb": _to_float(row.get("REB")),
                    "ast": _to_float(row.get("AST")),
                    "tov": _to_float(row.get("TOV")),
                    "stl": _to_float(row.get("STL")),
                    "blk": _to_float(row.get("BLK")),
                    "pf": _to_float(row.get("PF")),
                    "pts": _to_float(row.get("PTS")),
                    "plus_minus": _to_float(row.get("PLUS_MINUS")),
                    "nba_fantasy_pts": _to_float(row.get("NBA_FANTASY_PTS")),
                }
            )

        payload = _payload(
            "nba",
            "player_clutch_stats",
            data,
            context={"season": season, "season_type": season_type_all_star, "clutch_time": clutch_time, "point_diff": point_diff},
        )
        return normalized_rows, [payload]
    except Exception as exc:
        logger.exception("Failed to fetch player clutch stats for season %s", season)
        return [], [_failure_payload(
            "nba",
            "player_clutch_stats",
            endpoint="player_clutch_stats",
            error=exc,
            identifier=season,
            context={"season": season, "season_type": season_type_all_star, "clutch_time": clutch_time, "point_diff": point_diff},
        )]


def get_player_hustle_stats_bundle(
    season: str = DEFAULT_SEASON,
    season_type_all_star: str = "Regular Season",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        endpoint = _call_with_retries(
            "NBA player hustle stats",
            lambda: leaguehustlestatsplayer.LeagueHustleStatsPlayer(
                season=season,
                season_type_all_star=season_type_all_star,
                per_mode_time="PerGame",
                timeout=NBA_REQUEST_TIMEOUT,
            ),
            identifier=season,
        )
        data = endpoint.get_dict()
        rows = _extract_result_set_rows(data, "HustleStatsPlayer")
        _sleep_for_rate_limit()

        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            player_id = _to_str(row.get("PLAYER_ID"))
            team_id = _to_str(row.get("TEAM_ID"))
            if not player_id or not team_id:
                continue
            normalized_rows.append(
                {
                    "player_id": player_id,
                    "player_name": row.get("PLAYER_NAME"),
                    "team_id": team_id,
                    "team_abbreviation": row.get("TEAM_ABBREVIATION"),
                    "season": season,
                    "games_played": _to_int(row.get("G")),
                    "minutes": _parse_minutes(row.get("MIN")),
                    "contested_shots_2pt": _to_float(row.get("CONTESTED_SHOTS_2PT")),
                    "contested_shots_3pt": _to_float(row.get("CONTESTED_SHOTS_3PT")),
                    "contested_shots": _to_float(row.get("CONTESTED_SHOTS")),
                    "deflections": _to_float(row.get("DEFLECTIONS")),
                    "charges_drawn": _to_float(row.get("CHARGES_DRAWN")),
                    "screen_assists": _to_float(row.get("SCREEN_ASSISTS")),
                    "screen_ast_pts": _to_float(row.get("SCREEN_AST_PTS")),
                    "loose_balls_recovered_off": _to_float(row.get("OFF_LOOSE_BALLS_RECOVERED")),
                    "loose_balls_recovered_def": _to_float(row.get("DEF_LOOSE_BALLS_RECOVERED")),
                    "loose_balls_recovered": _to_float(row.get("LOOSE_BALLS_RECOVERED")),
                    "box_outs_off": _to_float(row.get("OFF_BOXOUTS")),
                    "box_outs_def": _to_float(row.get("DEF_BOXOUTS")),
                    "box_outs": _to_float(row.get("BOX_OUTS")),
                }
            )

        payload = _payload("nba", "player_hustle_stats", data, context={"season": season, "season_type": season_type_all_star})
        return normalized_rows, [payload]
    except Exception as exc:
        logger.exception("Failed to fetch player hustle stats for season %s", season)
        return [], [_failure_payload(
            "nba",
            "player_hustle_stats",
            endpoint="player_hustle_stats",
            error=exc,
            identifier=season,
            context={"season": season, "season_type": season_type_all_star},
        )]


def get_player_play_types_bundle(
    season: str = DEFAULT_SEASON,
    season_type_all_star: str = "Regular Season",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        endpoint = _call_with_retries(
            "NBA synergy play types",
            lambda: synergyplaytypes.SynergyPlayTypes(
                season=season,
                season_type_all_star=season_type_all_star,
                play_type_nullable="",
                type_grouping_nullable="offensive",
                player_or_team_abbreviation="P",
                per_mode_simple="PerGame",
                timeout=NBA_REQUEST_TIMEOUT,
            ),
            identifier=season,
        )
        data = endpoint.get_dict()
        rows = _extract_result_set_rows(data, "SynergyPlayType")
        _sleep_for_rate_limit()

        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            player_id = _to_str(row.get("PLAYER_ID"))
            team_id = _to_str(row.get("TEAM_ID"))
            if not player_id or not team_id:
                continue
            normalized_rows.append(
                {
                    "player_id": player_id,
                    "player_name": row.get("PLAYER_NAME"),
                    "team_id": team_id,
                    "team_abbreviation": row.get("TEAM_ABBREVIATION"),
                    "season": season,
                    "play_type": row.get("PLAY_TYPE"),
                    "type_grouping": row.get("TYPE_GROUPING") or "offensive",
                    "gp": _to_int(row.get("GP")),
                    "poss_pct": _to_float(row.get("POSS_PCT")),
                    "ppp": _to_float(row.get("PPP")),
                    "fg_pct": _to_float(row.get("FG_PCT")),
                    "ft_poss_pct": _to_float(row.get("FT_POSS_PCT")),
                    "tov_pct": _to_float(row.get("TOV_POSS_PCT")),
                    "sf_pct": _to_float(row.get("SF_POSS_PCT")),
                    "plusone_pct": _to_float(row.get("PLUSONE_POSS_PCT")),
                    "score_pct": _to_float(row.get("SCORE_POSS_PCT")),
                    "efg_pct": _to_float(row.get("EFG_PCT")),
                    "poss": _to_float(row.get("POSS")),
                    "pts": _to_float(row.get("PTS")),
                    "percentile": _to_float(row.get("PERCENTILE")),
                }
            )

        # An empty PlayType parameter returns all play types in the current nba_api response.
        payload = _payload("nba", "player_play_types", data, context={"season": season, "season_type": season_type_all_star})
        return normalized_rows, [payload]
    except Exception as exc:
        logger.exception("Failed to fetch player play types for season %s", season)
        return [], [_failure_payload(
            "nba",
            "player_play_types",
            endpoint="player_play_types",
            error=exc,
            identifier=season,
            context={"season": season, "season_type": season_type_all_star},
        )]


def get_player_tracking_stats_bundle(
    season: str = DEFAULT_SEASON,
    season_type_all_star: str = "Regular Season",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        normalized_rows: list[dict[str, Any]] = []
        payloads: list[dict[str, Any]] = []

        for measure_type in PLAYER_TRACKING_MEASURE_TYPES:
            endpoint = _call_with_retries(
                "NBA player tracking season stats",
                lambda measure_type=measure_type: leaguedashptstats.LeagueDashPtStats(
                    season=season,
                    season_type_all_star=season_type_all_star,
                    per_mode_simple="PerGame",
                    player_or_team="Player",
                    pt_measure_type=measure_type,
                    timeout=NBA_REQUEST_TIMEOUT,
                ),
                identifier=f"{season}:{measure_type}",
            )
            data = endpoint.get_dict()
            rows = _extract_result_set_rows(data, "LeagueDashPtStats")
            _sleep_for_rate_limit()

            for row in rows:
                player_id = _to_str(row.get("PLAYER_ID"))
                team_id = _to_str(row.get("TEAM_ID"))
                if not player_id or not team_id:
                    continue

                normalized_rows.append(
                    {
                        "player_id": player_id,
                        "player_name": row.get("PLAYER_NAME"),
                        "team_id": team_id,
                        "team_abbreviation": row.get("TEAM_ABBREVIATION"),
                        "season": season,
                        "measure_type": measure_type,
                        "gp": _to_int(row.get("GP")),
                        "g": _to_int(row.get("G")) or _to_int(row.get("GP")),
                        "minutes": _parse_minutes(row.get("MIN")),
                        "fgm": _to_float(row.get("CATCH_SHOOT_FGM"))
                        if measure_type == "CatchShoot"
                        else _to_float(row.get("PULL_UP_FGM")),
                        "fga": _to_float(row.get("CATCH_SHOOT_FGA"))
                        if measure_type == "CatchShoot"
                        else _to_float(row.get("PULL_UP_FGA")),
                        "fg_pct": _to_float(row.get("CATCH_SHOOT_FG_PCT"))
                        if measure_type == "CatchShoot"
                        else _to_float(row.get("PULL_UP_FG_PCT")),
                        "fg3m": _to_float(row.get("CATCH_SHOOT_FG3M"))
                        if measure_type == "CatchShoot"
                        else _to_float(row.get("PULL_UP_FG3M")),
                        "fg3a": _to_float(row.get("CATCH_SHOOT_FG3A"))
                        if measure_type == "CatchShoot"
                        else _to_float(row.get("PULL_UP_FG3A")),
                        "fg3_pct": _to_float(row.get("CATCH_SHOOT_FG3_PCT"))
                        if measure_type == "CatchShoot"
                        else _to_float(row.get("PULL_UP_FG3_PCT")),
                        "efg_pct": _to_float(row.get("CATCH_SHOOT_EFG_PCT"))
                        if measure_type == "CatchShoot"
                        else _to_float(row.get("PULL_UP_EFG_PCT")),
                        "pts": _to_float(row.get("CATCH_SHOOT_PTS"))
                        if measure_type == "CatchShoot"
                        else _to_float(row.get("PULL_UP_PTS")),
                        "drives": _to_float(row.get("DRIVES")) if measure_type == "Drives" else None,
                        "drive_fgm": _to_float(row.get("DRIVE_FGM")) if measure_type == "Drives" else None,
                        "drive_fga": _to_float(row.get("DRIVE_FGA")) if measure_type == "Drives" else None,
                        "drive_fg_pct": _to_float(row.get("DRIVE_FG_PCT")) if measure_type == "Drives" else None,
                        "drive_ftm": _to_float(row.get("DRIVE_FTM")) if measure_type == "Drives" else None,
                        "drive_fta": _to_float(row.get("DRIVE_FTA")) if measure_type == "Drives" else None,
                        "drive_ft_pct": _to_float(row.get("DRIVE_FT_PCT")) if measure_type == "Drives" else None,
                        "drive_pts": _to_float(row.get("DRIVE_PTS")) if measure_type == "Drives" else None,
                        "drive_pts_pct": _to_float(row.get("DRIVE_PTS_PCT")) if measure_type == "Drives" else None,
                        "drive_passes": _to_float(row.get("DRIVE_PASSES")) if measure_type == "Drives" else None,
                        "drive_passes_pct": _to_float(row.get("DRIVE_PASSES_PCT")) if measure_type == "Drives" else None,
                        "drive_ast": _to_float(row.get("DRIVE_AST")) if measure_type == "Drives" else None,
                        "drive_ast_pct": _to_float(row.get("DRIVE_AST_PCT")) if measure_type == "Drives" else None,
                        "drive_tov": _to_float(row.get("DRIVE_TOV")) if measure_type == "Drives" else None,
                        "drive_tov_pct": _to_float(row.get("DRIVE_TOV_PCT")) if measure_type == "Drives" else None,
                        "drive_pf": _to_float(row.get("DRIVE_PF")) if measure_type == "Drives" else None,
                        "drive_pf_pct": _to_float(row.get("DRIVE_PF_PCT")) if measure_type == "Drives" else None,
                    }
                )

            payloads.append(
                _payload(
                    "nba",
                    "player_tracking_stats",
                    data,
                    context={"season": season, "season_type": season_type_all_star, "measure_type": measure_type},
                )
            )

        return normalized_rows, payloads
    except Exception as exc:
        logger.exception("Failed to fetch player tracking season stats for season %s", season)
        return [], [_failure_payload(
            "nba",
            "player_tracking_stats",
            endpoint="player_tracking_stats",
            error=exc,
            identifier=season,
            context={"season": season, "season_type": season_type_all_star},
        )]


def get_player_on_off_stats_bundle(
    season: str = DEFAULT_SEASON,
    season_type_all_star: str = "Regular Season",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        normalized_rows: list[dict[str, Any]] = []
        payloads: list[dict[str, Any]] = []

        # This is the heaviest daily endpoint: 30 team calls at ~1.0s spacing is ~30s minimum.
        for team in teams.get_teams():
            team_id = str(team["id"])
            endpoint = _call_with_retries(
                "NBA player on/off stats",
                lambda team_id=team_id: teamplayeronoffdetails.TeamPlayerOnOffDetails(
                    team_id=team_id,
                    season=season,
                    season_type_all_star=season_type_all_star,
                    measure_type_detailed_defense="Advanced",
                    timeout=NBA_REQUEST_TIMEOUT,
                ),
                identifier=f"{season}:{team_id}",
            )
            data = endpoint.get_dict()
            off_rows = _extract_result_set_rows(data, "PlayersOffCourtTeamPlayerOnOffDetails")
            on_rows = _extract_result_set_rows(data, "PlayersOnCourtTeamPlayerOnOffDetails")
            _sleep_for_delay(max(RATE_LIMIT_DELAY, HEAVY_RATE_LIMIT_DELAY))

            for court_status, rows in (("off", off_rows), ("on", on_rows)):
                for row in rows:
                    player_id = _to_str(row.get("VS_PLAYER_ID"))
                    normalized_team_id = _to_str(row.get("TEAM_ID")) or team_id
                    if not player_id or not normalized_team_id:
                        continue
                    normalized_rows.append(
                        {
                            "player_id": player_id,
                            "player_name": row.get("VS_PLAYER_NAME"),
                            "team_id": normalized_team_id,
                            "season": season,
                            "court_status": str(row.get("COURT_STATUS") or court_status).lower(),
                            "gp": _to_int(row.get("GP")),
                            "min": _parse_minutes(row.get("MIN")),
                            "off_rating": _to_float(row.get("OFF_RATING")),
                            "def_rating": _to_float(row.get("DEF_RATING")),
                            "net_rating": _to_float(row.get("NET_RATING")),
                            "ast_pct": _to_float(row.get("AST_PCT")),
                            "ast_to": _to_float(row.get("AST_TO")),
                            "ast_ratio": _to_float(row.get("AST_RATIO")),
                            "oreb_pct": _to_float(row.get("OREB_PCT")),
                            "dreb_pct": _to_float(row.get("DREB_PCT")),
                            "reb_pct": _to_float(row.get("REB_PCT")),
                            "tov_pct": _to_float(row.get("TM_TOV_PCT")),
                            "efg_pct": _to_float(row.get("EFG_PCT")),
                            "ts_pct": _to_float(row.get("TS_PCT")),
                            "pace": _to_float(row.get("PACE")),
                            "pie": _to_float(row.get("PIE")),
                            "plus_minus": _to_float(row.get("PLUS_MINUS")),
                        }
                    )

            payloads.append(
                _payload(
                    "nba",
                    "player_on_off_stats",
                    data,
                    external_id=team_id,
                    context={"season": season, "season_type": season_type_all_star, "team_id": team_id},
                )
            )

        return normalized_rows, payloads
    except Exception as exc:
        logger.exception("Failed to fetch player on/off stats for season %s", season)
        return [], [_failure_payload(
            "nba",
            "player_on_off_stats",
            endpoint="player_on_off_stats",
            error=exc,
            identifier=season,
            context={"season": season, "season_type": season_type_all_star},
        )]


def get_player_defensive_tracking_bundle(
    season: str = DEFAULT_SEASON,
    season_type_all_star: str = "Regular Season",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        normalized_rows: list[dict[str, Any]] = []
        payloads: list[dict[str, Any]] = []

        for defense_category in PLAYER_DEFENSIVE_TRACKING_CATEGORIES:
            endpoint = _call_with_retries(
                "NBA player defensive tracking",
                lambda defense_category=defense_category: leaguedashptdefend.LeagueDashPtDefend(
                    season=season,
                    season_type_all_star=season_type_all_star,
                    defense_category=defense_category,
                    timeout=NBA_REQUEST_TIMEOUT,
                ),
                identifier=f"{season}:{defense_category}",
            )
            data = endpoint.get_dict()
            rows = _extract_result_set_rows(data, "LeagueDashPTDefend")
            _sleep_for_rate_limit()

            for row in rows:
                player_id = _to_str(row.get("CLOSE_DEF_PERSON_ID"))
                team_id = _to_str(row.get("PLAYER_LAST_TEAM_ID"))
                if not player_id or not team_id:
                    continue
                normalized_rows.append(
                    {
                        "player_id": player_id,
                        "player_name": row.get("PLAYER_NAME"),
                        "team_id": team_id,
                        "team_abbreviation": row.get("PLAYER_LAST_TEAM_ABBREVIATION"),
                        "season": season,
                        "defense_category": defense_category,
                        "gp": _to_int(row.get("GP")),
                        "g": _to_int(row.get("G")),
                        "freq": _to_float(row.get("FREQ")),
                        "d_fgm": _to_float(row.get("D_FGM")),
                        "d_fga": _to_float(row.get("D_FGA")),
                        "d_fg_pct": _to_float(row.get("D_FG_PCT")),
                        "normal_fg_pct": _to_float(row.get("NORMAL_FG_PCT")),
                        "pct_plusminus": _to_float(row.get("PCT_PLUSMINUS")),
                    }
                )

            payloads.append(
                _payload(
                    "nba",
                    "player_defensive_tracking",
                    data,
                    context={"season": season, "season_type": season_type_all_star, "defense_category": defense_category},
                )
            )

        return normalized_rows, payloads
    except Exception as exc:
        logger.exception("Failed to fetch player defensive tracking for season %s", season)
        return [], [_failure_payload(
            "nba",
            "player_defensive_tracking",
            endpoint="player_defensive_tracking",
            error=exc,
            identifier=season,
            context={"season": season, "season_type": season_type_all_star},
        )]


def get_player_shot_locations_bundle(
    season: str = DEFAULT_SEASON,
    season_type_all_star: str = "Regular Season",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        endpoint = _call_with_retries(
            "NBA player shot locations",
            lambda: leaguedashplayershotlocations.LeagueDashPlayerShotLocations(
                season=season,
                season_type_all_star=season_type_all_star,
                per_mode_detailed="PerGame",
                distance_range="By Zone",
                timeout=NBA_REQUEST_TIMEOUT,
            ),
            identifier=season,
        )
        data = endpoint.get_dict()
        result_set = data.get("resultSets") or {}
        headers_meta = result_set.get("headers", [])
        row_set = result_set.get("rowSet", [])
        _sleep_for_rate_limit()

        zone_headers = headers_meta[0].get("columnNames", []) if headers_meta else []
        columns_to_skip = headers_meta[0].get("columnsToSkip", 0) if headers_meta else 0
        zone_index = {zone_name: index for index, zone_name in enumerate(zone_headers)}

        normalized_rows: list[dict[str, Any]] = []
        for row in row_set:
            player_id = _to_str(row[0] if len(row) > 0 else None)
            team_id = _to_str(row[2] if len(row) > 2 else None)
            if not player_id or not team_id:
                continue

            normalized_row: dict[str, Any] = {
                "player_id": player_id,
                "player_name": row[1] if len(row) > 1 else None,
                "team_id": team_id,
                "team_abbreviation": row[3] if len(row) > 3 else None,
                "season": season,
            }
            for zone_name, prefix in SHOT_LOCATION_ZONE_FIELD_PREFIXES.items():
                zone_position = zone_index.get(zone_name)
                start_index = columns_to_skip + (zone_position * 3) if zone_position is not None else None
                stats = row[start_index : start_index + 3] if start_index is not None else []
                normalized_row[f"{prefix}_fgm"] = _to_float(stats[0]) if len(stats) > 0 else None
                normalized_row[f"{prefix}_fga"] = _to_float(stats[1]) if len(stats) > 1 else None
                normalized_row[f"{prefix}_fg_pct"] = _to_float(stats[2]) if len(stats) > 2 else None
            normalized_rows.append(normalized_row)

        payload = _payload("nba", "player_shot_locations", data, context={"season": season, "season_type": season_type_all_star})
        return normalized_rows, [payload]
    except Exception as exc:
        logger.exception("Failed to fetch player shot locations for season %s", season)
        return [], [_failure_payload(
            "nba",
            "player_shot_locations",
            endpoint="player_shot_locations",
            error=exc,
            identifier=season,
            context={"season": season, "season_type": season_type_all_star},
        )]


def get_lineup_stats_bundle(
    season: str = DEFAULT_SEASON,
    season_type_all_star: str = "Regular Season",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        endpoint = _call_with_retries(
            "NBA lineup stats",
            lambda: leaguedashlineups.LeagueDashLineups(
                season=season,
                season_type_all_star=season_type_all_star,
                measure_type_detailed_defense="Advanced",
                group_quantity=5,
                per_mode_detailed="PerGame",
                timeout=NBA_REQUEST_TIMEOUT,
            ),
            identifier=season,
        )
        data = endpoint.get_dict()
        rows = _extract_result_set_rows(data, "Lineups")
        _sleep_for_rate_limit()

        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            group_id = _to_str(row.get("GROUP_ID"))
            team_id = _to_str(row.get("TEAM_ID"))
            if not group_id or not team_id:
                continue
            normalized_rows.append(
                {
                    "group_id": group_id,
                    "group_name": row.get("GROUP_NAME"),
                    "team_id": team_id,
                    "team_abbreviation": row.get("TEAM_ABBREVIATION"),
                    "season": season,
                    "gp": _to_int(row.get("GP")),
                    "min": _parse_minutes(row.get("MIN")),
                    "off_rating": _to_float(row.get("OFF_RATING")),
                    "def_rating": _to_float(row.get("DEF_RATING")),
                    "net_rating": _to_float(row.get("NET_RATING")),
                    "ast_pct": _to_float(row.get("AST_PCT")),
                    "ast_to": _to_float(row.get("AST_TO")),
                    "ast_ratio": _to_float(row.get("AST_RATIO")),
                    "oreb_pct": _to_float(row.get("OREB_PCT")),
                    "dreb_pct": _to_float(row.get("DREB_PCT")),
                    "reb_pct": _to_float(row.get("REB_PCT")),
                    "tov_pct": _to_float(row.get("TM_TOV_PCT")),
                    "efg_pct": _to_float(row.get("EFG_PCT")),
                    "ts_pct": _to_float(row.get("TS_PCT")),
                    "pace": _to_float(row.get("PACE")),
                    "pie": _to_float(row.get("PIE")),
                    "plus_minus": _to_float(row.get("PLUS_MINUS")),
                }
            )

        payload = _payload("nba", "lineup_stats", data, context={"season": season, "season_type": season_type_all_star})
        return normalized_rows, [payload]
    except Exception as exc:
        logger.exception("Failed to fetch lineup stats for season %s", season)
        return [], [_failure_payload(
            "nba",
            "lineup_stats",
            endpoint="lineup_stats",
            error=exc,
            identifier=season,
            context={"season": season, "season_type": season_type_all_star},
        )]
