from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from analytics.name_matching import candidate_name_keys
from database.models import OfficialInjuryReport, OfficialInjuryReportEntry


@dataclass(slots=True)
class OfficialInjuryReportIndex:
    by_date_team_player_id: dict[tuple[str, str, str], dict[str, Any]]
    by_date_team_name: dict[tuple[str, str, str], dict[str, Any]]
    team_summaries: dict[tuple[str, str], dict[str, Any]]
    team_rows: dict[tuple[str, str], list[dict[str, Any]]]


def load_latest_official_injury_report_rows(
    session: Session,
    *,
    report_dates: list[date],
    captured_at: datetime,
) -> list[dict[str, Any]]:
    if not report_dates:
        return []

    reports = (
        session.query(OfficialInjuryReport)
        .filter(
            OfficialInjuryReport.report_date.in_(report_dates),
            OfficialInjuryReport.report_datetime_utc <= captured_at,
        )
        .order_by(OfficialInjuryReport.report_date.asc(), OfficialInjuryReport.report_datetime_utc.desc())
        .all()
    )
    latest_report_ids: dict[date, int] = {}
    for report in reports:
        if report.report_date is None or report.id is None:
            continue
        latest_report_ids.setdefault(report.report_date, int(report.id))
    if not latest_report_ids:
        return []

    entries = (
        session.query(OfficialInjuryReportEntry)
        .filter(OfficialInjuryReportEntry.report_id.in_(list(latest_report_ids.values())))
        .all()
    )
    return [_entry_to_row(entry) for entry in entries]


def build_official_injury_report_index(rows: list[dict[str, Any]]) -> OfficialInjuryReportIndex:
    by_date_team_player_id: dict[tuple[str, str, str], dict[str, Any]] = {}
    by_date_team_name: dict[tuple[str, str, str], dict[str, Any]] = {}
    team_summaries: dict[tuple[str, str], dict[str, Any]] = {}
    team_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for row in rows:
        game_date = row.get("game_date")
        team_abbreviation = str(row.get("team_abbreviation") or "").upper()
        if not game_date or not team_abbreviation:
            continue
        date_key = game_date.isoformat() if isinstance(game_date, date) else str(game_date)
        player_id = row.get("player_id")
        player_name = str(row.get("player_name") or "")
        current_status = str(row.get("current_status") or "").upper()

        if player_id not in (None, ""):
            by_date_team_player_id[(date_key, team_abbreviation, str(player_id))] = row
        if player_name:
            for candidate in candidate_name_keys(player_name):
                by_date_team_name.setdefault((date_key, team_abbreviation, candidate), row)

        team_rows.setdefault((date_key, team_abbreviation), []).append(row)
        team_summary = team_summaries.setdefault(
            (date_key, team_abbreviation),
            {
                "game_date": game_date,
                "team_abbreviation": team_abbreviation,
                "report_datetime_utc": row.get("report_datetime_utc"),
                "report_submitted": row.get("report_submitted"),
                "player_entry_count": 0,
                "out_count": 0,
                "doubtful_count": 0,
                "questionable_count": 0,
                "probable_count": 0,
                "available_count": 0,
            },
        )
        report_dt = row.get("report_datetime_utc")
        if team_summary.get("report_datetime_utc") is None or (
            report_dt is not None and report_dt > team_summary["report_datetime_utc"]
        ):
            team_summary["report_datetime_utc"] = report_dt
            team_summary["report_submitted"] = row.get("report_submitted")

        if not player_name:
            continue
        team_summary["player_entry_count"] += 1
        if current_status in {"OUT", "SUSPENDED"}:
            team_summary["out_count"] += 1
        elif current_status == "DOUBTFUL":
            team_summary["doubtful_count"] += 1
        elif current_status == "QUESTIONABLE":
            team_summary["questionable_count"] += 1
        elif current_status == "PROBABLE":
            team_summary["probable_count"] += 1
        elif current_status == "AVAILABLE":
            team_summary["available_count"] += 1

    for rows_for_team in team_rows.values():
        rows_for_team.sort(key=lambda row: (str(row.get("player_name") or ""), str(row.get("player_id") or "")))

    return OfficialInjuryReportIndex(
        by_date_team_player_id=by_date_team_player_id,
        by_date_team_name=by_date_team_name,
        team_summaries=team_summaries,
        team_rows=team_rows,
    )


def match_official_injury_row(
    index: OfficialInjuryReportIndex,
    *,
    game_date: date | None,
    player_id: str | None,
    team_abbreviation: str | None,
    player_name: str,
) -> dict[str, Any] | None:
    if game_date is None:
        return None
    date_key = game_date.isoformat()
    team_abbr = (team_abbreviation or "").upper()
    if not team_abbr:
        return None

    if player_id:
        match = index.by_date_team_player_id.get((date_key, team_abbr, str(player_id)))
        if match is not None:
            return match

    for candidate in candidate_name_keys(player_name):
        match = index.by_date_team_name.get((date_key, team_abbr, candidate))
        if match is not None:
            return match
    return None


def get_official_team_summary(
    index: OfficialInjuryReportIndex,
    *,
    game_date: date | None,
    team_abbreviation: str | None,
) -> dict[str, Any] | None:
    if game_date is None or not team_abbreviation:
        return None
    return index.team_summaries.get((game_date.isoformat(), team_abbreviation.upper()))


def get_official_team_rows(
    index: OfficialInjuryReportIndex,
    *,
    game_date: date | None,
    team_abbreviation: str | None,
) -> list[dict[str, Any]]:
    if game_date is None or not team_abbreviation:
        return []
    return list(index.team_rows.get((game_date.isoformat(), team_abbreviation.upper()), []))


def _entry_to_row(entry: OfficialInjuryReportEntry) -> dict[str, Any]:
    return {
        "report_id": entry.report_id,
        "report_datetime_utc": entry.report_datetime_utc,
        "game_date": entry.game_date,
        "matchup": entry.matchup,
        "team_abbreviation": entry.team_abbreviation,
        "team_name": entry.team_name,
        "player_id": entry.player_id,
        "player_name": entry.player_name,
        "current_status": entry.current_status,
        "reason": entry.reason,
        "report_submitted": entry.report_submitted,
    }

