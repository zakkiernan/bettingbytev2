from __future__ import annotations

import hashlib
import io
import logging
import re
import time as time_module
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests
from pypdf import PdfReader

from database.db import session_scope
from database.models import OfficialInjuryReport, Player, Team
from ingestion.writer import write_official_injury_report, write_source_payloads

LOGGER = logging.getLogger(__name__)

NBA_ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
REPORT_SOURCE = "official_nba_pdf"
BASE_REPORT_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_{report_date}_{report_time}.pdf"
KNOWN_STATUSES = ("Questionable", "Probable", "Available", "Doubtful", "Suspended", "Out")
TEAM_NAME_BY_ABBREVIATION = {
    "ATL": "Atlanta Hawks",
    "BKN": "Brooklyn Nets",
    "BOS": "Boston Celtics",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "LA Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}
TEAM_ALIASES = {
    "Los Angeles Clippers": "LAC",
    "LA Clippers": "LAC",
}
GAME_DATE_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4}$")
MATCHUP_PATTERN = re.compile(r"^[A-Z]{2,3}@[A-Z]{2,3}$")
NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
PLAYER_LOOKUP_CACHE: dict[str, str] | None = None


@dataclass(slots=True)
class InjuryReportEntry:
    game_date: date
    game_time_et: str | None
    matchup: str
    team_abbreviation: str
    team_name: str
    player_name: str | None
    current_status: str
    reason: str | None
    report_submitted: bool


@dataclass(slots=True)
class ParsedInjuryReport:
    report_date: date
    report_time_et: str
    report_datetime_utc: datetime
    pdf_url: str
    pdf_sha256: str
    raw_text: str
    entries: list[InjuryReportEntry]


@dataclass(slots=True)
class GameSegment:
    game_date: date
    game_time_et: str | None
    matchup: str
    start_index: int
    end_index: int


def build_injury_report_url(report_date: date, report_time_et: time) -> str:
    return BASE_REPORT_URL.format(
        report_date=report_date.isoformat(),
        report_time=report_time_et.strftime("%I_%M%p"),
    )


def default_report_times(interval_minutes: int = 15) -> list[time]:
    times: list[time] = []
    total_minutes = 24 * 60
    for minutes_since_midnight in range(0, total_minutes, interval_minutes):
        hour, minute = divmod(minutes_since_midnight, 60)
        times.append(time(hour=hour, minute=minute))
    return times



def default_backfill_report_times() -> list[time]:
    return [
        time(hour=0, minute=0),
        time(hour=13, minute=0),
        time(hour=17, minute=0),
        time(hour=18, minute=0),
        time(hour=19, minute=0),
        time(hour=20, minute=0),
        time(hour=21, minute=0),
        time(hour=22, minute=0),
    ]


def fetch_official_injury_report(url: str, timeout_seconds: int = 30) -> ParsedInjuryReport:
    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    pdf_bytes = response.content
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    text = extract_pdf_text(pdf_bytes)
    return parse_injury_report_text(text, pdf_url=url, pdf_sha256=pdf_sha256)


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(pages)


def parse_injury_report_text(text: str, *, pdf_url: str, pdf_sha256: str) -> ParsedInjuryReport:
    lines = _clean_report_lines(text)
    report_date, report_time_et, report_datetime_utc = _parse_report_header(text, pdf_url)

    entries: list[InjuryReportEntry] = []
    for segment in _collect_game_segments(lines):
        entries.extend(_parse_game_segment(lines, segment))

    return ParsedInjuryReport(
        report_date=report_date,
        report_time_et=report_time_et,
        report_datetime_utc=report_datetime_utc,
        pdf_url=pdf_url,
        pdf_sha256=pdf_sha256,
        raw_text=text,
        entries=entries,
    )


def _clean_report_lines(text: str) -> list[str]:
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned: list[str] = []
    cursor = 0
    while cursor < len(raw_lines):
        if _is_report_header(raw_lines, cursor):
            cursor += 9
            continue
        if _is_column_header(raw_lines, cursor):
            cursor += 11
            continue
        cleaned.append(raw_lines[cursor])
        cursor += 1
    return cleaned


def _is_report_header(lines: list[str], cursor: int) -> bool:
    window = lines[cursor : cursor + 9]
    if len(window) < 9:
        return False
    return (
        window[0] == "Injury"
        and window[1] == "Report:"
        and re.fullmatch(r"\d{2}/\d{2}/\d{2}", window[2]) is not None
        and re.fullmatch(r"\d{2}:\d{2}", window[3]) is not None
        and window[4] in {"AM", "PM"}
        and window[5] == "Page"
        and window[7] == "of"
    )


def _is_column_header(lines: list[str], cursor: int) -> bool:
    return lines[cursor : cursor + 11] == [
        "Game",
        "Date",
        "Game",
        "Time",
        "Matchup",
        "Team",
        "Player",
        "Name",
        "Current",
        "Status",
        "Reason",
    ]


def _consume_game_start(
    lines: list[str],
    cursor: int,
    current_game_date: date | None,
) -> tuple[date, str | None, str, int] | None:
    if _is_full_game_start(lines, cursor):
        game_date = datetime.strptime(lines[cursor], "%m/%d/%Y").date()
        return game_date, f"{lines[cursor + 1]} {lines[cursor + 2]}", lines[cursor + 3], cursor + 4
    if current_game_date is not None and _is_time_only_game_start(lines, cursor):
        return current_game_date, f"{lines[cursor]} {lines[cursor + 1]}", lines[cursor + 2], cursor + 3
    if current_game_date is not None and _is_bare_matchup_start(lines, cursor):
        return current_game_date, None, lines[cursor], cursor + 1
    return None


def _is_full_game_start(lines: list[str], cursor: int) -> bool:
    window = lines[cursor : cursor + 4]
    return (
        len(window) >= 4
        and GAME_DATE_PATTERN.fullmatch(window[0]) is not None
        and re.fullmatch(r"\d{2}:\d{2}", window[1]) is not None
        and window[2] == "(ET)"
        and MATCHUP_PATTERN.fullmatch(window[3]) is not None
    )


def _is_time_only_game_start(lines: list[str], cursor: int) -> bool:
    window = lines[cursor : cursor + 3]
    return (
        len(window) >= 3
        and re.fullmatch(r"\d{2}:\d{2}", window[0]) is not None
        and window[1] == "(ET)"
        and MATCHUP_PATTERN.fullmatch(window[2]) is not None
    )


def _is_bare_matchup_start(lines: list[str], cursor: int) -> bool:
    return cursor < len(lines) and MATCHUP_PATTERN.fullmatch(lines[cursor]) is not None


def _collect_game_segments(lines: list[str]) -> list[GameSegment]:
    segments: list[GameSegment] = []
    cursor = 0
    current_game_date: date | None = None
    while cursor < len(lines):
        game_start = _consume_game_start(lines, cursor, current_game_date)
        if game_start is None:
            cursor += 1
            continue

        game_date, game_time_et, matchup, body_start = game_start
        current_game_date = game_date
        next_cursor = body_start
        while next_cursor < len(lines):
            if _consume_game_start(lines, next_cursor, current_game_date) is not None:
                break
            next_cursor += 1

        segments.append(
            GameSegment(
                game_date=game_date,
                game_time_et=game_time_et,
                matchup=matchup,
                start_index=body_start,
                end_index=next_cursor,
            )
        )
        cursor = next_cursor
    return segments


def _parse_game_segment(lines: list[str], segment: GameSegment) -> list[InjuryReportEntry]:
    away_abbr, home_abbr = segment.matchup.split("@", 1)
    body_tokens = lines[segment.start_index : segment.end_index]
    away_start, away_name = _find_team_header(body_tokens, away_abbr)
    home_start, home_name = _find_team_header(body_tokens, home_abbr)

    entries: list[InjuryReportEntry] = []
    if away_start is not None and away_name is not None and home_start is not None and home_name is not None:
        away_tokens = body_tokens[away_start + len(away_name.split()) : home_start]
        home_tokens = body_tokens[home_start + len(home_name.split()) :]
        entries.extend(
            _parse_team_tokens(
                team_tokens=away_tokens,
                game_date=segment.game_date,
                game_time_et=segment.game_time_et,
                matchup=segment.matchup,
                team_abbr=away_abbr,
            )
        )
        entries.extend(
            _parse_team_tokens(
                team_tokens=home_tokens,
                game_date=segment.game_date,
                game_time_et=segment.game_time_et,
                matchup=segment.matchup,
                team_abbr=home_abbr,
            )
        )
        return entries

    if away_start is None and home_start is not None and home_name is not None:
        away_tokens = body_tokens[:home_start]
        home_tokens = body_tokens[home_start + len(home_name.split()) :]
        entries.extend(
            _parse_team_tokens(
                team_tokens=away_tokens,
                game_date=segment.game_date,
                game_time_et=segment.game_time_et,
                matchup=segment.matchup,
                team_abbr=away_abbr,
            )
        )
        entries.extend(
            _parse_team_tokens(
                team_tokens=home_tokens,
                game_date=segment.game_date,
                game_time_et=segment.game_time_et,
                matchup=segment.matchup,
                team_abbr=home_abbr,
            )
        )
    elif away_start is not None and away_name is not None and home_start is None:
        away_tokens = body_tokens[away_start + len(away_name.split()) :]
        entries.extend(
            _parse_team_tokens(
                team_tokens=away_tokens,
                game_date=segment.game_date,
                game_time_et=segment.game_time_et,
                matchup=segment.matchup,
                team_abbr=away_abbr,
            )
        )
    elif away_start is None and home_start is not None and home_name is not None:
        home_tokens = body_tokens[home_start + len(home_name.split()) :]
        entries.extend(
            _parse_team_tokens(
                team_tokens=home_tokens,
                game_date=segment.game_date,
                game_time_et=segment.game_time_et,
                matchup=segment.matchup,
                team_abbr=home_abbr,
            )
        )

    LOGGER.warning(
        "Could not split game segment %s cleanly. away=%s home=%s tokens=%s parsed_entries=%s",
        segment.matchup,
        away_start,
        home_start,
        body_tokens[:24],
        len(entries),
    )
    return entries


def _find_team_header(tokens: list[str], team_abbr: str) -> tuple[int | None, str | None]:
    for team_name in _team_name_candidates(team_abbr):
        name_tokens = team_name.split()
        for idx in range(len(tokens) - len(name_tokens) + 1):
            if _matches_sequence(tokens, idx, name_tokens):
                return idx, team_name
    return None, None


def _parse_team_tokens(
    *,
    team_tokens: list[str],
    game_date: date,
    game_time_et: str | None,
    matchup: str,
    team_abbr: str,
) -> list[InjuryReportEntry]:
    if not team_tokens:
        return []

    if team_tokens[:3] == ["NOT", "YET", "SUBMITTED"]:
        return [
            InjuryReportEntry(
                game_date=game_date,
                game_time_et=game_time_et,
                matchup=matchup,
                team_abbreviation=team_abbr,
                team_name=TEAM_NAME_BY_ABBREVIATION[team_abbr],
                player_name=None,
                current_status="NOT_YET_SUBMITTED",
                reason=None,
                report_submitted=False,
            )
        ]

    entries: list[InjuryReportEntry] = []
    position = 0
    while position < len(team_tokens):
        status_index, status = _find_status(team_tokens, position)
        if status_index is None or status is None:
            break

        player_start = _derive_player_start(team_tokens, position, status_index)
        if player_start is None:
            position = status_index + 1
            continue

        reason_start = status_index + 1
        next_player_start = len(team_tokens)
        search_position = reason_start
        while search_position < len(team_tokens):
            next_status_index, _ = _find_status(team_tokens, search_position)
            if next_status_index is None:
                break
            candidate_start = _derive_player_start(team_tokens, search_position, next_status_index)
            if candidate_start is not None:
                next_player_start = candidate_start
                break
            search_position = next_status_index + 1

        entries.append(
            InjuryReportEntry(
                game_date=game_date,
                game_time_et=game_time_et,
                matchup=matchup,
                team_abbreviation=team_abbr,
                team_name=TEAM_NAME_BY_ABBREVIATION[team_abbr],
                player_name=_canonical_player_name(team_tokens[player_start:status_index]),
                current_status=status.upper(),
                reason=" ".join(team_tokens[reason_start:next_player_start]).strip() or None,
                report_submitted=True,
            )
        )
        position = next_player_start

    return entries


def _derive_player_start(tokens: list[str], lower_bound: int, status_index: int) -> int | None:
    search_start = max(lower_bound, status_index - 6)
    comma_indices = [idx for idx in range(search_start, status_index) if "," in tokens[idx]]
    if not comma_indices:
        return None

    comma_index = comma_indices[-1]
    start = comma_index
    normalized = _normalize_name(tokens[start].replace(",", ""))
    if normalized in NAME_SUFFIXES and start > lower_bound:
        start -= 1

    player_lookup = _get_player_lookup_cache()
    if player_lookup:
        candidate_starts = []
        for candidate in range(max(lower_bound, start - 2), start + 1):
            if not any("," in token for token in tokens[candidate:status_index]):
                continue
            candidate_name = _canonical_player_name(tokens[candidate:status_index])
            if _resolve_player_id(candidate_name, player_lookup):
                candidate_starts.append(candidate)
        if candidate_starts:
            return min(candidate_starts)

    return start


def _matches_sequence(tokens: list[str], cursor: int, expected: list[str]) -> bool:
    return tokens[cursor : cursor + len(expected)] == expected


def _team_name_candidates(team_abbr: str | None) -> list[str]:
    if not team_abbr:
        return []
    candidates: list[str] = []
    team_name = TEAM_NAME_BY_ABBREVIATION.get(team_abbr)
    if team_name:
        candidates.append(team_name)
        parts = team_name.split()
        if len(parts) >= 2:
            trailing_two = " ".join(parts[-2:])
            if trailing_two not in candidates:
                candidates.append(trailing_two)
            trailing_one = parts[-1]
            if trailing_one not in candidates:
                candidates.append(trailing_one)
    for alias_name, alias_abbr in TEAM_ALIASES.items():
        if alias_abbr == team_abbr and alias_name not in candidates:
            candidates.append(alias_name)
            alias_parts = alias_name.split()
            if len(alias_parts) >= 2:
                trailing_two = " ".join(alias_parts[-2:])
                if trailing_two not in candidates:
                    candidates.append(trailing_two)
                trailing_one = alias_parts[-1]
                if trailing_one not in candidates:
                    candidates.append(trailing_one)
    return candidates


def sync_official_injury_report(url: str) -> dict[str, Any]:
    if _report_exists(url):
        return {"status": "skipped_existing", "url": url, "entries": 0}

    parsed = fetch_official_injury_report(url)
    report_row, entry_rows, payload = normalize_injury_report(parsed)
    write_source_payloads([payload])
    report_id = write_official_injury_report(report_row, entry_rows)
    return {
        "status": "success",
        "report_id": report_id,
        "url": url,
        "entries": len(entry_rows),
        "game_count": len({entry.matchup for entry in parsed.entries}),
    }


def backfill_official_injury_reports(
    *,
    start_date: date,
    end_date: date,
    report_times: list[time] | None = None,
    delay_seconds: float = 0.0,
) -> dict[str, Any]:
    candidate_times = report_times or default_backfill_report_times()
    total_candidates = 0
    fetched_reports = 0
    skipped_existing = 0
    not_found = 0
    other_failures = 0
    total_entries = 0

    current_date = start_date
    while current_date <= end_date:
        for report_time in candidate_times:
            total_candidates += 1
            url = build_injury_report_url(current_date, report_time)
            if _report_exists(url):
                skipped_existing += 1
                continue
            try:
                result = sync_official_injury_report(url)
            except requests.HTTPError as exc:
                status_code = getattr(exc.response, "status_code", None)
                if status_code == 404:
                    not_found += 1
                else:
                    other_failures += 1
                    LOGGER.warning("Failed to fetch injury report %s: %s", url, exc)
            except Exception as exc:
                other_failures += 1
                LOGGER.warning("Failed to fetch injury report %s: %s", url, exc)
            else:
                if result.get("status") == "skipped_existing":
                    skipped_existing += 1
                else:
                    fetched_reports += 1
                    total_entries += int(result.get("entries", 0))
            if delay_seconds > 0:
                time_module.sleep(delay_seconds)
        current_date += timedelta(days=1)

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "candidate_reports": total_candidates,
        "fetched_reports": fetched_reports,
        "skipped_existing": skipped_existing,
        "not_found": not_found,
        "other_failures": other_failures,
        "entries": total_entries,
    }


def normalize_injury_report(parsed: ParsedInjuryReport) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    team_lookup = _load_team_lookup()
    player_lookup = _load_player_lookup()

    report_row = {
        "season": _season_for_game_date(parsed.report_date),
        "report_date": parsed.report_date,
        "report_time_et": parsed.report_time_et,
        "report_datetime_utc": parsed.report_datetime_utc,
        "pdf_url": parsed.pdf_url,
        "pdf_sha256": parsed.pdf_sha256,
        "game_count": len({entry.matchup for entry in parsed.entries}),
        "entry_count": len(parsed.entries),
    }

    entry_rows: list[dict[str, Any]] = []
    for entry in parsed.entries:
        team_info = team_lookup.get(entry.team_abbreviation, {})
        player_id = _resolve_player_id(entry.player_name, player_lookup)
        entry_rows.append(
            {
                "season": _season_for_game_date(entry.game_date),
                "report_datetime_utc": parsed.report_datetime_utc,
                "game_date": entry.game_date,
                "game_time_et": entry.game_time_et,
                "matchup": entry.matchup,
                "team_id": team_info.get("team_id"),
                "team_abbreviation": entry.team_abbreviation,
                "team_name": team_info.get("team_name") or entry.team_name,
                "player_id": player_id,
                "player_name": entry.player_name,
                "current_status": entry.current_status,
                "reason": entry.reason,
                "report_submitted": entry.report_submitted,
                "source": REPORT_SOURCE,
            }
        )

    payload = {
        "source": REPORT_SOURCE,
        "payload_type": "injury_report_pdf",
        "external_id": parsed.pdf_url,
        "context": {
            "report_date": parsed.report_date.isoformat(),
            "report_time_et": parsed.report_time_et,
            "report_datetime_utc": parsed.report_datetime_utc.isoformat(),
            "pdf_sha256": parsed.pdf_sha256,
            "game_count": report_row["game_count"],
            "entry_count": report_row["entry_count"],
        },
        "payload": {
            "pdf_url": parsed.pdf_url,
            "raw_text": parsed.raw_text,
        },
        "captured_at": parsed.report_datetime_utc,
    }
    return report_row, entry_rows, payload



def _parse_report_header(text: str, pdf_url: str) -> tuple[date, str, datetime]:
    match = re.search(r"Injury\s+Report:\s+(?P<date>\d{2}/\d{2}/\d{2})\s+(?P<time>\d{2}:\d{2})\s+(?P<period>[AP]M)", text)
    if match is None:
        raise ValueError(f"Could not parse report header for {pdf_url}")

    report_date = datetime.strptime(match.group("date"), "%m/%d/%y").date()
    report_time_et = f"{match.group('time')} {match.group('period')}"
    report_dt_local = datetime.strptime(f"{report_date.isoformat()} {report_time_et}", "%Y-%m-%d %I:%M %p").replace(tzinfo=NBA_ET)
    return report_date, report_time_et, report_dt_local.astimezone(UTC)


def _find_status(tokens: list[str], start: int) -> tuple[int | None, str | None]:
    for idx in range(start, len(tokens)):
        for status in KNOWN_STATUSES:
            status_tokens = status.split()
            if tokens[idx : idx + len(status_tokens)] == status_tokens:
                return idx, status
    return None, None


def _canonical_player_name(name_tokens: list[str]) -> str:
    if not name_tokens:
        return ""
    comma_index = next((idx for idx, token in enumerate(name_tokens) if "," in token), None)
    if comma_index is None:
        return " ".join(name_tokens).strip()
    last_tokens = [token.replace(",", "") for token in name_tokens[: comma_index + 1]]
    first_tokens = [token.replace(",", "") for token in name_tokens[comma_index + 1 :]]
    ordered = first_tokens + last_tokens
    return " ".join(token for token in ordered if token).strip()


def _load_team_lookup() -> dict[str, dict[str, str]]:
    lookup = {abbr: {"team_id": None, "team_name": name} for abbr, name in TEAM_NAME_BY_ABBREVIATION.items()}
    with session_scope() as session:
        teams = session.query(Team).all()
    for team in teams:
        if team.abbreviation:
            lookup[team.abbreviation] = {"team_id": team.team_id, "team_name": team.full_name}
    for alias_name, abbr in TEAM_ALIASES.items():
        lookup.setdefault(abbr, {"team_id": None, "team_name": alias_name})
    return lookup


def _load_player_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    with session_scope() as session:
        players = session.query(Player.player_id, Player.full_name).all()
    for player_id, full_name in players:
        for candidate in _candidate_name_keys(full_name):
            lookup.setdefault(candidate, player_id)
    return lookup


def _get_player_lookup_cache() -> dict[str, str]:
    global PLAYER_LOOKUP_CACHE
    if PLAYER_LOOKUP_CACHE is None:
        try:
            PLAYER_LOOKUP_CACHE = _load_player_lookup()
        except Exception as exc:
            LOGGER.warning("Could not load player lookup cache for injury parser: %s", exc)
            PLAYER_LOOKUP_CACHE = {}
    return PLAYER_LOOKUP_CACHE


def _resolve_player_id(player_name: str | None, lookup: dict[str, str]) -> str | None:
    if not player_name:
        return None
    for candidate in _candidate_name_keys(player_name):
        player_id = lookup.get(candidate)
        if player_id is not None:
            return player_id
    return None


def _candidate_name_keys(name: str) -> list[str]:
    normalized = _normalize_name(name)
    if not normalized:
        return []
    keys = [normalized]
    tokens = normalized.split()
    while tokens and tokens[-1] in NAME_SUFFIXES:
        tokens = tokens[:-1]
        if tokens:
            candidate = " ".join(tokens)
            if candidate not in keys:
                keys.append(candidate)
    return keys


def _normalize_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", ascii_name.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _season_for_game_date(game_date: date) -> str:
    start_year = game_date.year if game_date.month >= 7 else game_date.year - 1
    end_year = (start_year + 1) % 100
    return f"{start_year}-{end_year:02d}"


def _report_exists(url: str) -> bool:
    with session_scope() as session:
        return session.query(OfficialInjuryReport.id).filter(OfficialInjuryReport.pdf_url == url).first() is not None
