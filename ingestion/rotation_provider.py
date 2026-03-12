from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import requests

from database.db import session_scope
from database.models import Game, HistoricalGameLog, Team
from ingestion.nba_client import get_player_id_map

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - exercised via runtime dependency checks
    BeautifulSoup = None

LOGGER = logging.getLogger(__name__)

ROTATION_SOURCE_BASE_URL = os.getenv("ROTATION_SOURCE_BASE_URL", "https://nbarotations.info")
ROTATION_SOURCE_TIMEOUT = int(os.getenv("ROTATION_SOURCE_TIMEOUT", "25"))
ROTATION_SOURCE_RETRIES = int(os.getenv("ROTATION_SOURCE_RETRIES", "3"))
ROTATION_SOURCE_BACKOFF_SECONDS = float(os.getenv("ROTATION_SOURCE_BACKOFF_SECONDS", "1.5"))
ROTATION_BUCKET_REAL_TIME = 600.0
ROTATION_ACTIVE_THRESHOLD = float(os.getenv("ROTATION_ACTIVE_THRESHOLD", "0.05"))
ROTATION_EXPECTED_MINUTES_FLOOR = float(os.getenv("ROTATION_EXPECTED_MINUTES_FLOOR", "3.0"))
ROTATION_PLAYER_NAME_ALIASES = {
    "carlton carrington": "Bub Carrington",
    "cam johnson": "Cameron Johnson",
    "hansen yang": "Yang Hansen",
}


@dataclass(slots=True)
class RotationFetchError(Exception):
    error_type: str
    error_text: str
    status_code: int | None = None
    url: str | None = None

    def __str__(self) -> str:
        return self.error_text


@dataclass(slots=True)
class RotationBundleResult:
    rotations: list[dict[str, Any]] = field(default_factory=list)
    team_rotation_games: list[dict[str, Any]] = field(default_factory=list)
    player_rotation_games: list[dict[str, Any]] = field(default_factory=list)
    payloads: list[dict[str, Any]] = field(default_factory=list)
    error_type: str | None = None
    error_text: str | None = None
    error_details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class _RotationStintWindow:
    start_index: int
    end_index: int
    duration_real: float


def _payload(payload_type: str, payload: Any, external_id: str | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "source": "nbarotations",
        "payload_type": payload_type,
        "external_id": external_id,
        "context": context or {},
        "payload": payload,
        "captured_at": datetime.utcnow(),
    }


def _rotation_failure_result(
    error_type: str,
    error_text: str,
    *,
    error_details: dict[str, Any] | None = None,
    payloads: list[dict[str, Any]] | None = None,
) -> RotationBundleResult:
    return RotationBundleResult(
        error_type=error_type,
        error_text=error_text,
        error_details=error_details or {},
        payloads=payloads or [],
    )


def _normalize_text(value: str) -> str:
    stripped = "".join(
        char for char in unicodedata.normalize("NFD", value) if unicodedata.category(char) != "Mn"
    )
    stripped = stripped.lower().replace("'", "").replace(".", "")
    stripped = re.sub(r"[^a-z0-9]+", " ", stripped)
    return re.sub(r"\s+", " ", stripped).strip()


def _extract_json_array(text: str, start_index: int) -> str | None:
    if start_index < 0 or start_index >= len(text) or text[start_index] != "[":
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(start_index, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1]

    return None


def _extract_display_sections(html: str) -> tuple[str | None, dict[str, list[dict[str, Any]]]]:
    if BeautifulSoup is None:
        raise RotationFetchError(
            "dependency_missing",
            "beautifulsoup4 is required for scraper-backed rotation ingestion.",
        )

    soup = BeautifulSoup(html, "html.parser")
    header_node = soup.select_one(".gameHeader")
    header_text = " ".join(header_node.get_text(" ", strip=True).split()) if header_node else None
    sections: dict[str, list[dict[str, Any]]] = {}

    for script in soup.find_all("script"):
        script_text = script.string or script.get_text("", strip=False)
        if not script_text or "displayGame(" not in script_text:
            continue

        for side in ("away", "home"):
            match = re.search(rf"displayGame\(\s*[\"']{side}[\"']\s*,", script_text)
            if not match:
                continue

            array_text = _extract_json_array(script_text, script_text.find("[", match.end()))
            if not array_text:
                continue

            try:
                payload = json.loads(array_text)
            except json.JSONDecodeError:
                continue

            if isinstance(payload, list):
                sections[side] = payload

    return header_text, sections


def _is_source_missing_game_page(html: str) -> bool:
    normalized_html = " ".join(html.split()).lower()
    return "page not found" in normalized_html and "displaygame(" not in normalized_html


def _build_team_player_lookup(rows: list[HistoricalGameLog]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in rows:
        name = str(row.player_name or "").strip()
        if not name:
            continue
        lookup[_normalize_text(name)] = str(row.player_id)
    return lookup


def _counts_toward_rotation_expectation(row: HistoricalGameLog) -> bool:
    minutes = row.minutes
    if minutes is None:
        return True
    return float(minutes) >= ROTATION_EXPECTED_MINUTES_FLOOR


def _load_rotation_context(game_id: str) -> dict[str, Any]:
    with session_scope() as session:
        game = session.get(Game, game_id)
        if game is None:
            raise RotationFetchError("unexpected_schema", f"Canonical game {game_id} was not found.")

        team_ids = [team_id for team_id in (game.home_team_id, game.away_team_id) if team_id]
        teams = {
            team.team_id: team
            for team in session.query(Team).filter(Team.team_id.in_(team_ids)).all()
        }
        log_rows = (
            session.query(HistoricalGameLog)
            .filter(HistoricalGameLog.game_id == game_id)
            .order_by(HistoricalGameLog.team, HistoricalGameLog.player_name)
            .all()
        )

    home_rows = [row for row in log_rows if row.team == game.home_team_abbreviation]
    away_rows = [row for row in log_rows if row.team == game.away_team_abbreviation]
    global_player_map = get_player_id_map()

    home_team = teams.get(game.home_team_id or "")
    away_team = teams.get(game.away_team_id or "")
    return {
        "game_id": game_id,
        "home": {
            "team_id": str(game.home_team_id or ""),
            "team_abbreviation": game.home_team_abbreviation,
            "team_name": home_team.full_name if home_team is not None else game.home_team_abbreviation,
            "expected_player_count": len({str(row.player_id) for row in home_rows if _counts_toward_rotation_expectation(row)}),
            "historical_player_count": len({str(row.player_id) for row in home_rows}),
            "player_lookup": _build_team_player_lookup(home_rows),
        },
        "away": {
            "team_id": str(game.away_team_id or ""),
            "team_abbreviation": game.away_team_abbreviation,
            "team_name": away_team.full_name if away_team is not None else game.away_team_abbreviation,
            "expected_player_count": len({str(row.player_id) for row in away_rows if _counts_toward_rotation_expectation(row)}),
            "historical_player_count": len({str(row.player_id) for row in away_rows}),
            "player_lookup": _build_team_player_lookup(away_rows),
        },
        "global_player_map": global_player_map,
    }


def _resolve_player_identity(
    player_name: str,
    team_lookup: dict[str, str],
    global_player_map: dict[str, str],
) -> tuple[str | None, str]:
    exact_match = global_player_map.get(player_name)
    if exact_match:
        return exact_match, player_name

    normalized_player_name = _normalize_text(player_name)
    alias_name = ROTATION_PLAYER_NAME_ALIASES.get(normalized_player_name)
    if alias_name:
        alias_match = global_player_map.get(alias_name)
        if alias_match:
            return alias_match, alias_name

    team_match = team_lookup.get(normalized_player_name)
    if team_match:
        canonical_name = next(
            (candidate_name for candidate_name, candidate_id in global_player_map.items() if candidate_id == team_match),
            player_name,
        )
        return team_match, canonical_name

    for candidate_name, candidate_id in global_player_map.items():
        if _normalize_text(candidate_name) == normalized_player_name:
            return candidate_id, candidate_name

    for normalized_candidate, candidate_id in team_lookup.items():
        if normalized_player_name in normalized_candidate or normalized_candidate in normalized_player_name:
            canonical_name = next(
                (candidate_name for candidate_name, global_candidate_id in global_player_map.items() if global_candidate_id == candidate_id),
                player_name,
            )
            return candidate_id, canonical_name

    return None, player_name


def _build_stint_windows(histogram: list[Any]) -> tuple[list[_RotationStintWindow], float]:
    windows: list[_RotationStintWindow] = []
    start_index: int | None = None
    segment_duration = 0.0
    total_duration = 0.0

    for index, raw_value in enumerate(histogram):
        value = max(float(raw_value), 0.0)
        active = value > ROTATION_ACTIVE_THRESHOLD
        if active:
            total_duration += value * ROTATION_BUCKET_REAL_TIME
            if start_index is None:
                start_index = index
                segment_duration = 0.0
            segment_duration += value * ROTATION_BUCKET_REAL_TIME
            continue

        if start_index is not None:
            windows.append(
                _RotationStintWindow(
                    start_index=start_index,
                    end_index=index - 1,
                    duration_real=round(segment_duration, 3),
                )
            )
            start_index = None
            segment_duration = 0.0

    if start_index is not None:
        windows.append(
            _RotationStintWindow(
                start_index=start_index,
                end_index=len(histogram) - 1,
                duration_real=round(segment_duration, 3),
            )
        )

    return windows, round(total_duration, 3)


def _normalize_scraped_game(game_id: str, raw_payload: dict[str, Any]) -> RotationBundleResult:
    header_text = raw_payload.get("title")
    sections = raw_payload.get("raw_sections") or {}
    payloads = [
        _payload(
            "game_rotation_scrape",
            raw_payload,
            external_id=game_id,
            context={"title": header_text or "", "url": raw_payload.get("url")},
        )
    ]

    try:
        context = _load_rotation_context(game_id)
    except RotationFetchError as exc:
        return _rotation_failure_result(
            exc.error_type,
            exc.error_text,
            error_details={"game_id": game_id},
            payloads=payloads,
        )

    missing_sides = [side for side in ("away", "home") if not isinstance(sections.get(side), list) or not sections.get(side)]
    if missing_sides:
        return _rotation_failure_result(
            "unexpected_schema",
            f"Rotation scraper payload was missing display sections for: {', '.join(missing_sides)}.",
            error_details={"missing_sides": missing_sides},
            payloads=payloads,
        )

    rotations: list[dict[str, Any]] = []
    player_summaries_by_side: dict[str, list[dict[str, Any]]] = {"away": [], "home": []}
    unresolved_players: list[dict[str, str]] = []
    zero_window_players: list[dict[str, str]] = []

    for side in ("away", "home"):
        team_context = context[side]
        for player in sections.get(side, []):
            if not isinstance(player, dict):
                continue

            player_name = str(player.get("name") or "").strip()
            histogram = player.get("histogram")
            if not player_name or not isinstance(histogram, list):
                continue

            player_id, canonical_player_name = _resolve_player_identity(
                player_name,
                team_context["player_lookup"],
                context["global_player_map"],
            )
            if player_id is None:
                unresolved_players.append({"side": side, "player_name": player_name})
                continue

            windows, total_duration_real = _build_stint_windows(histogram)
            if not windows:
                zero_window_players.append({"side": side, "player_name": canonical_player_name, "player_id": player_id})
                continue

            for stint_number, window in enumerate(windows, start=1):
                in_time_real = float(window.start_index) * ROTATION_BUCKET_REAL_TIME
                out_time_real = float(window.end_index + 1) * ROTATION_BUCKET_REAL_TIME
                rotations.append(
                    {
                        "game_id": game_id,
                        "team_id": team_context["team_id"],
                        "team_abbreviation": team_context["team_abbreviation"],
                        "team_name": team_context["team_name"],
                        "player_id": player_id,
                        "player_name": canonical_player_name,
                        "stint_number": stint_number,
                        "in_time_real": round(in_time_real, 3),
                        "out_time_real": round(out_time_real, 3),
                        "shift_duration_real": round(window.duration_real, 3),
                        "player_points": None,
                        "point_differential": None,
                        "usage_percentage": None,
                    }
                )

            player_summaries_by_side[side].append(
                {
                    "game_id": game_id,
                    "team_id": team_context["team_id"],
                    "team_abbreviation": team_context["team_abbreviation"],
                    "team_name": team_context["team_name"],
                    "player_id": player_id,
                    "player_name": canonical_player_name,
                    "stint_count": len(windows),
                    "first_in_time_real": round(float(windows[0].start_index) * ROTATION_BUCKET_REAL_TIME, 3),
                    "last_out_time_real": round(float(windows[-1].end_index + 1) * ROTATION_BUCKET_REAL_TIME, 3),
                    "total_shift_duration_real": round(total_duration_real, 3),
                    "avg_shift_duration_real": round(total_duration_real / len(windows), 3) if windows else None,
                    "started": windows[0].start_index == 0,
                    "played_opening_stint": windows[0].start_index == 0,
                }
            )

    expected_player_count = int(context["away"]["expected_player_count"]) + int(context["home"]["expected_player_count"])
    mapped_player_count = len(player_summaries_by_side["away"]) + len(player_summaries_by_side["home"])
    covered_player_count = mapped_player_count + len(zero_window_players)
    if expected_player_count > 0 and covered_player_count < expected_player_count:
        return _rotation_failure_result(
            "identity_mapping_failure",
            f"Rotation scraper could not map all players for game {game_id}.",
            error_details={
                "expected_player_count": expected_player_count,
                "historical_player_count": int(context["away"]["historical_player_count"]) + int(context["home"]["historical_player_count"]),
                "mapped_player_count": mapped_player_count,
                "covered_player_count": covered_player_count,
                "zero_window_player_count": len(zero_window_players),
                "zero_window_players": zero_window_players[:20],
                "unmapped_player_count": len(unresolved_players),
                "unmapped_players": unresolved_players[:20],
                "expected_minutes_floor": ROTATION_EXPECTED_MINUTES_FLOOR,
            },
            payloads=payloads,
        )

    team_rotation_games: list[dict[str, Any]] = []
    player_rotation_games: list[dict[str, Any]] = []
    for side in ("away", "home"):
        summaries = player_summaries_by_side[side]
        if not summaries:
            continue
        max_out_time_real = max(summary["last_out_time_real"] for summary in summaries if summary["last_out_time_real"] is not None)
        starters = 0
        closers = 0
        total_shift_duration_real = 0.0
        for summary in summaries:
            closed_game = (
                max_out_time_real is not None
                and summary["last_out_time_real"] is not None
                and summary["last_out_time_real"] >= max_out_time_real - 0.1
            )
            summary["closed_game"] = closed_game
            if summary["started"]:
                starters += 1
            if closed_game:
                closers += 1
            total_shift_duration_real += float(summary["total_shift_duration_real"] or 0.0)
            player_rotation_games.append(summary)

        team_rotation_games.append(
            {
                "game_id": game_id,
                "team_id": summaries[0]["team_id"],
                "team_abbreviation": summaries[0]["team_abbreviation"],
                "team_name": summaries[0]["team_name"],
                "rotation_player_count": len(summaries),
                "starter_count": starters,
                "closing_count": closers,
                "total_stints": sum(int(summary["stint_count"] or 0) for summary in summaries),
                "max_out_time_real": round(max_out_time_real, 3) if max_out_time_real is not None else None,
                "total_shift_duration_real": round(total_shift_duration_real, 3),
            }
        )

    if not player_rotation_games:
        return _rotation_failure_result(
            "unexpected_schema",
            f"Rotation scraper produced no mapped player summaries for game {game_id}.",
            error_details={"expected_player_count": expected_player_count},
            payloads=payloads,
        )

    return RotationBundleResult(
        rotations=rotations,
        team_rotation_games=team_rotation_games,
        player_rotation_games=player_rotation_games,
        payloads=payloads,
    )


def _fetch_rotation_page_payload(game_id: str) -> dict[str, Any]:
    url = f"{ROTATION_SOURCE_BASE_URL.rstrip('/')}/game/{game_id}"
    last_error: Exception | None = None

    for attempt in range(1, ROTATION_SOURCE_RETRIES + 1):
        try:
            response = requests.get(url, timeout=ROTATION_SOURCE_TIMEOUT)
            if response.status_code == 429 or response.status_code >= 500:
                raise RotationFetchError(
                    "http_429_or_5xx",
                    f"Rotation scraper HTTP {response.status_code}.",
                    status_code=response.status_code,
                    url=url,
                )
            response.raise_for_status()
            if not response.text or not response.text.strip():
                raise RotationFetchError("empty_response", "Rotation scraper returned an empty response body.", url=url)
            if _is_source_missing_game_page(response.text):
                raise RotationFetchError(
                    "source_missing_game",
                    f"Rotation source is missing game {game_id}.",
                    status_code=response.status_code,
                    url=url,
                )

            header_text, sections = _extract_display_sections(response.text)
            return {
                "game_id": game_id,
                "url": url,
                "title": header_text,
                "raw_sections": sections,
            }
        except RotationFetchError:
            raise
        except requests.Timeout as exc:
            last_error = exc
            if attempt >= ROTATION_SOURCE_RETRIES:
                raise RotationFetchError("timeout", f"Rotation scraper timed out: {exc}", url=url) from exc
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= ROTATION_SOURCE_RETRIES:
                raise RotationFetchError("timeout", f"Rotation scraper request failed: {exc}", url=url) from exc
        except Exception as exc:
            last_error = exc
            if attempt >= ROTATION_SOURCE_RETRIES:
                raise RotationFetchError("unexpected_schema", f"Rotation scraper parse failed: {exc}", url=url) from exc

        backoff_seconds = ROTATION_SOURCE_BACKOFF_SECONDS * (2 ** (attempt - 1))
        LOGGER.warning(
            "Rotation scraper fetch failed (%s/%s) for %s: %s. Retrying in %.1fs",
            attempt,
            ROTATION_SOURCE_RETRIES,
            game_id,
            last_error,
            backoff_seconds,
        )
        import time

        time.sleep(backoff_seconds)

    raise RotationFetchError("unexpected_schema", f"Rotation scraper failed for game {game_id}.", url=url)


def get_rotation_bundle(game_id: str) -> RotationBundleResult:
    try:
        raw_payload = _fetch_rotation_page_payload(game_id)
    except RotationFetchError as exc:
        if exc.error_type == "source_missing_game":
            LOGGER.warning("Rotation source is missing game %s.", game_id)
        else:
            LOGGER.exception("Failed to fetch rotation scrape for game %s: %s", game_id, exc.error_text)
        return _rotation_failure_result(
            exc.error_type,
            exc.error_text,
            error_details={"status_code": exc.status_code, "url": exc.url},
        )

    return _normalize_scraped_game(game_id, raw_payload)


