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
    boxscoresummaryv3,
    boxscoreplayertrackv3,
    boxscoretraditionalv3,
    boxscoreusagev3,
    leaguegamelog,
    leaguedashptteamdefend,
    leaguedashteamstats,
    playbyplayv3,
    scoreboardv3,
)
from nba_api.stats.library.http import NBAStatsHTTP
from nba_api.stats.static import players, teams

logger = logging.getLogger(__name__)

NBA_REQUEST_TIMEOUT = int(os.getenv("NBA_REQUEST_TIMEOUT", "30"))
NBA_REQUEST_RETRIES = int(os.getenv("NBA_REQUEST_RETRIES", "3"))
NBA_RETRY_BACKOFF_SECONDS = float(os.getenv("NBA_RETRY_BACKOFF_SECONDS", "1.5"))
RATE_LIMIT_DELAY = float(os.getenv("NBA_RATE_LIMIT_DELAY", "0.6"))
DEFAULT_SEASON = os.getenv("NBA_DEFAULT_SEASON", "2025-26")


def _sleep_for_rate_limit() -> None:
    if RATE_LIMIT_DELAY > 0:
        time.sleep(RATE_LIMIT_DELAY)


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
    except JSONDecodeError:
        # The schedule endpoint occasionally returns empty/non-JSON bodies for future dates.
        if game_date > date.today():
            logger.warning("NBA scoreboard returned malformed schedule data for %s; treating as no future games.", game_date)
            return [], []
        logger.exception("Failed to fetch NBA scoreboard for %s", game_date)
        return [], []
    except Exception:
        logger.exception("Failed to fetch NBA scoreboard for %s", game_date)
        return [], []


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
    except Exception:
        logger.exception("Failed to fetch live NBA scoreboard")
        return [], []


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
    except Exception:
        logger.exception("Failed to fetch live boxscore for game %s", game_id)
        return [], []


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
    except Exception:
        logger.exception("Failed to fetch historical NBA game logs for season %s", season)
        return [], []


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
    except Exception:
        logger.exception("Failed to fetch boxscore summary for game %s", game_id)
        return None, []


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
    except Exception:
        logger.exception("Failed to fetch advanced boxscore for game %s", game_id)
        return [], []


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
    except Exception:
        logger.exception("Failed to fetch player tracking for game %s", game_id)
        return [], []


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
    except Exception:
        logger.exception("Failed to fetch team defensive stats for season %s", season)
        return [], []


def get_team_defensive_stats(
    season: str = DEFAULT_SEASON,
    season_type_all_star: str = "Regular Season",
) -> list[dict[str, Any]]:
    rows, _ = get_team_defensive_stats_bundle(season=season, season_type_all_star=season_type_all_star)
    return rows
