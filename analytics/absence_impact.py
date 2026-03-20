from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Iterable

from analytics.name_matching import normalize_name
from database.db import session_scope
from database.models import AbsenceImpactSummary, AbsenceSourceOverride, HistoricalAdvancedLog, HistoricalGameLog, OfficialInjuryReportEntry, PlayerRotationGame

BUILD_VERSION = "absence-impact-v1"
OVERRIDE_PRIORITY_BONUS = 100.0


@dataclass(slots=True)
class AbsenceImpactRow:
    source_player_id: str
    source_player_name: str
    beneficiary_player_id: str
    beneficiary_player_name: str
    team_abbreviation: str
    window_start_date: date | None
    window_end_date: date | None
    source_out_game_count: int
    source_active_game_count: int
    beneficiary_out_game_count: int
    beneficiary_active_game_count: int
    minutes_delta: float | None
    points_delta: float | None
    rebounds_delta: float | None
    assists_delta: float | None
    blocks_delta: float | None
    usage_delta: float | None
    touches_delta: float | None
    passes_delta: float | None
    impact_score: float | None
    sample_confidence: float
    build_version: str = BUILD_VERSION


@dataclass(slots=True)
class AbsenceImpactBuildResult:
    source_player_id: str
    source_player_name: str
    team_abbreviation: str
    source_out_game_count: int
    source_active_game_count: int
    summary_count: int
    persisted: bool
    rows: list[AbsenceImpactRow]


@dataclass(slots=True)
class AbsenceImpactSourceSelection:
    source_player_id: str
    source_player_name: str
    team_abbreviation: str
    active_game_count: int
    out_game_count: int
    avg_minutes: float
    avg_usage: float | None
    avg_touches: float | None
    avg_passes: float | None
    start_rate: float | None
    close_rate: float | None
    tenure_start_date: date | None
    tenure_end_date: date | None
    selection_score: float


@dataclass(slots=True)
class AbsenceImpactBatchResult:
    source_count: int
    summary_count: int
    persisted: bool
    selections: list[AbsenceImpactSourceSelection]
    results: list[AbsenceImpactBuildResult]


@dataclass(slots=True)
class _AbsenceSourceOverrideRule:
    team_abbreviation: str
    player_id: str | None
    player_name: str | None
    normalized_player_name: str | None
    include_as_source: bool
    start_date: date | None
    end_date: date | None
    note: str | None


@dataclass(slots=True)
class _AbsenceDataset:
    logs: list[HistoricalGameLog]
    advanced_map: dict[tuple[str, str], HistoricalAdvancedLog]
    rotation_map: dict[tuple[str, str], PlayerRotationGame]
    injury_rows: list[OfficialInjuryReportEntry]
    source_overrides: list[_AbsenceSourceOverrideRule]
    schedule: dict[tuple[str, str, str, int], str]
    window_start_date: date | None
    window_end_date: date | None


def _safe_mean(values: Iterable[float | None]) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    return mean(numeric) if numeric else None


def _delta(active_values: list[dict[str, float | None]], out_values: list[dict[str, float | None]], metric: str) -> float | None:
    active_avg = _safe_mean(row.get(metric) for row in active_values)
    out_avg = _safe_mean(row.get(metric) for row in out_values)
    if active_avg is None or out_avg is None:
        return None
    return round(out_avg - active_avg, 4)


def _parse_matchup(matchup: str | None, team_abbr: str) -> tuple[str, int] | None:
    text = (matchup or "").replace(" ", "").upper()
    if "@" not in text:
        return None
    away, home = text.split("@", 1)
    team = (team_abbr or "").upper()
    if team == away:
        return home, 0
    if team == home:
        return away, 1
    return None


def _build_schedule_key_to_game_id(rows: list[HistoricalGameLog]) -> dict[tuple[str, str, str, int], str]:
    schedule: dict[tuple[str, str, str, int], str] = {}
    for row in rows:
        schedule[(row.game_date.date().isoformat(), str(row.team), str(row.opponent), 1 if row.is_home else 0)] = str(row.game_id)
    return schedule


def _sample_confidence(active_n: int, out_n: int) -> float:
    return round(min(active_n / 12.0, 1.0) * min(out_n / 5.0, 1.0), 4)


def _impact_score(*, minutes_delta: float | None, usage_delta: float | None, points_delta: float | None, touches_delta: float | None, sample_confidence: float) -> float | None:
    if all(value is None for value in (minutes_delta, usage_delta, points_delta, touches_delta)):
        return None
    raw = (
        (minutes_delta or 0.0) * 0.45
        + ((usage_delta or 0.0) * 100.0) * 0.30
        + (points_delta or 0.0) * 0.20
        + ((touches_delta or 0.0) / 10.0) * 0.05
    )
    return round(raw * sample_confidence, 4)


def _selection_score(*, avg_minutes: float | None, avg_usage: float | None, avg_touches: float | None, avg_passes: float | None, start_rate: float | None, close_rate: float | None, out_game_count: int) -> float:
    return round(
        (avg_minutes or 0.0) * 1.0
        + ((avg_usage or 0.0) * 100.0) * 0.75
        + ((avg_touches or 0.0) / 10.0) * 0.30
        + ((avg_passes or 0.0) / 10.0) * 0.20
        + ((start_rate or 0.0) * 12.0)
        + ((close_rate or 0.0) * 6.0)
        + min(out_game_count, 6) * 1.25,
        4,
    )


def _current_team_tenure_rows(dataset: _AbsenceDataset, *, player_id: str, team_abbreviation: str) -> list[HistoricalGameLog]:
    player_logs = [row for row in dataset.logs if str(row.player_id) == str(player_id)]
    team_logs = [row for row in player_logs if str(row.team) == team_abbreviation]
    if not team_logs:
        return []
    latest_team_date = max(row.game_date for row in team_logs)
    latest_other_team_date = max(
        (row.game_date for row in player_logs if str(row.team) != team_abbreviation and row.game_date <= latest_team_date),
        default=None,
    )
    if latest_other_team_date is None:
        return team_logs
    return [row for row in team_logs if row.game_date > latest_other_team_date]



def _source_role_stats(dataset: _AbsenceDataset, rows: list[HistoricalGameLog]) -> tuple[float, float | None, float | None, float | None, float | None, float | None]:
    avg_minutes = _safe_mean(float(row.minutes) if row.minutes is not None else None for row in rows) or 0.0
    avg_usage = _safe_mean(
        float(dataset.advanced_map[(str(row.game_id), str(row.player_id))].usage_percentage)
        if (str(row.game_id), str(row.player_id)) in dataset.advanced_map and dataset.advanced_map[(str(row.game_id), str(row.player_id))].usage_percentage is not None
        else None
        for row in rows
    )
    avg_touches = _safe_mean(
        float(dataset.advanced_map[(str(row.game_id), str(row.player_id))].touches)
        if (str(row.game_id), str(row.player_id)) in dataset.advanced_map and dataset.advanced_map[(str(row.game_id), str(row.player_id))].touches is not None
        else None
        for row in rows
    )
    avg_passes = _safe_mean(
        float(dataset.advanced_map[(str(row.game_id), str(row.player_id))].passes)
        if (str(row.game_id), str(row.player_id)) in dataset.advanced_map and dataset.advanced_map[(str(row.game_id), str(row.player_id))].passes is not None
        else None
        for row in rows
    )
    start_rate = _safe_mean(
        1.0 if dataset.rotation_map.get((str(row.game_id), str(row.player_id))) and dataset.rotation_map[(str(row.game_id), str(row.player_id))].started else 0.0
        if (str(row.game_id), str(row.player_id)) in dataset.rotation_map else None
        for row in rows
    )
    close_rate = _safe_mean(
        1.0 if dataset.rotation_map.get((str(row.game_id), str(row.player_id))) and dataset.rotation_map[(str(row.game_id), str(row.player_id))].closed_game else 0.0
        if (str(row.game_id), str(row.player_id)) in dataset.rotation_map else None
        for row in rows
    )
    return avg_minutes, avg_usage, avg_touches, avg_passes, start_rate, close_rate



def _effective_reference_date(dataset: _AbsenceDataset) -> date | None:
    if dataset.logs:
        return max(row.game_date.date() for row in dataset.logs if row.game_date is not None)
    if dataset.window_end_date is not None:
        return dataset.window_end_date
    return None



def _load_source_overrides(session) -> list[_AbsenceSourceOverrideRule]:
    return [
        _AbsenceSourceOverrideRule(
            team_abbreviation=str(row.team_abbreviation or "").upper(),
            player_id=str(row.player_id) if row.player_id not in (None, "") else None,
            player_name=row.player_name,
            normalized_player_name=(row.normalized_player_name or normalize_name(row.player_name or "") or None),
            include_as_source=bool(row.include_as_source),
            start_date=row.start_date,
            end_date=row.end_date,
            note=row.note,
        )
        for row in session.query(AbsenceSourceOverride).all()
    ]



def _override_is_active(rule: _AbsenceSourceOverrideRule, *, reference_date: date | None) -> bool:
    if reference_date is None:
        return True
    if rule.start_date is not None and reference_date < rule.start_date:
        return False
    if rule.end_date is not None and reference_date > rule.end_date:
        return False
    return True



def _resolve_source_override(
    dataset: _AbsenceDataset,
    *,
    team_abbreviation: str,
    player_id: str,
    player_name: str,
    reference_date: date | None,
) -> _AbsenceSourceOverrideRule | None:
    normalized_player_name = normalize_name(player_name or "") or None
    id_matches: list[_AbsenceSourceOverrideRule] = []
    name_matches: list[_AbsenceSourceOverrideRule] = []

    for rule in dataset.source_overrides:
        if rule.team_abbreviation != str(team_abbreviation or "").upper():
            continue
        if not _override_is_active(rule, reference_date=reference_date):
            continue
        if rule.player_id is not None and str(rule.player_id) == str(player_id):
            id_matches.append(rule)
            continue
        if rule.player_id is None and rule.normalized_player_name is not None and normalized_player_name == rule.normalized_player_name:
            name_matches.append(rule)

    if id_matches:
        return next((rule for rule in reversed(id_matches) if not rule.include_as_source), id_matches[-1])
    if name_matches:
        return next((rule for rule in reversed(name_matches) if not rule.include_as_source), name_matches[-1])
    return None



def _load_absence_dataset(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> _AbsenceDataset:
    with session_scope() as session:
        logs_query = session.query(HistoricalGameLog)
        injury_query = session.query(OfficialInjuryReportEntry).filter(OfficialInjuryReportEntry.current_status == "OUT")

        if start_date is not None:
            logs_query = logs_query.filter(HistoricalGameLog.game_date >= start_date)
            injury_query = injury_query.filter(OfficialInjuryReportEntry.game_date >= start_date.date())
        if end_date is not None:
            logs_query = logs_query.filter(HistoricalGameLog.game_date <= end_date)
            injury_query = injury_query.filter(OfficialInjuryReportEntry.game_date <= end_date.date())

        logs = logs_query.all()
        game_ids = sorted({str(row.game_id) for row in logs})
        advanced_rows = []
        rotation_rows = []
        if game_ids:
            advanced_rows = session.query(HistoricalAdvancedLog).filter(HistoricalAdvancedLog.game_id.in_(game_ids)).all()
            rotation_rows = session.query(PlayerRotationGame).filter(PlayerRotationGame.game_id.in_(game_ids)).all()
        advanced_map = {(str(row.game_id), str(row.player_id)): row for row in advanced_rows}
        rotation_map = {(str(row.game_id), str(row.player_id)): row for row in rotation_rows}
        injury_rows = injury_query.all()
        source_overrides = _load_source_overrides(session)

    return _AbsenceDataset(
        logs=logs,
        advanced_map=advanced_map,
        rotation_map=rotation_map,
        injury_rows=injury_rows,
        source_overrides=source_overrides,
        schedule=_build_schedule_key_to_game_id(logs),
        window_start_date=start_date.date() if start_date is not None else None,
        window_end_date=end_date.date() if end_date is not None else None,
    )


def _resolve_out_game_ids(dataset: _AbsenceDataset, *, source_player_id: str, team_abbreviation: str) -> set[str]:
    out_game_ids: set[str] = set()
    for row in dataset.injury_rows:
        if str(row.team_abbreviation) != team_abbreviation or str(row.player_id) != str(source_player_id):
            continue
        if row.game_date is None:
            continue
        parsed = _parse_matchup(row.matchup, team_abbreviation)
        if not parsed:
            continue
        opponent, is_home = parsed
        game_id = dataset.schedule.get((row.game_date.isoformat(), team_abbreviation, opponent, is_home))
        if game_id is not None:
            out_game_ids.add(game_id)
    return out_game_ids


def _build_absence_impact_rows_from_dataset(
    dataset: _AbsenceDataset,
    *,
    source_player_id: str,
    team_abbreviation: str,
    min_active_games: int,
    min_out_games: int,
) -> AbsenceImpactBuildResult:
    source_rows = _current_team_tenure_rows(dataset, player_id=source_player_id, team_abbreviation=team_abbreviation)
    source_player_name = source_rows[0].player_name if source_rows else str(source_player_id)
    source_active_games = {str(row.game_id) for row in source_rows}
    out_game_ids = _resolve_out_game_ids(dataset, source_player_id=source_player_id, team_abbreviation=team_abbreviation) - source_active_games
    effective_min_active_games = min_active_games
    if source_active_games:
        effective_min_active_games = min(min_active_games, max(2, len(source_active_games)))

    rows_by_teammate: dict[tuple[str, str], list[dict[str, float | str | None]]] = {}
    for row in dataset.logs:
        if str(row.team) != team_abbreviation:
            continue
        teammate_key = (str(row.player_id), str(row.player_name))
        adv = dataset.advanced_map.get((str(row.game_id), str(row.player_id)))
        rows_by_teammate.setdefault(teammate_key, []).append(
            {
                "game_id": str(row.game_id),
                "minutes": float(row.minutes) if row.minutes is not None else None,
                "points": float(row.points) if row.points is not None else None,
                "rebounds": float(row.rebounds) if row.rebounds is not None else None,
                "assists": float(row.assists) if row.assists is not None else None,
                "blocks": float(row.blocks) if row.blocks is not None else None,
                "usage": float(adv.usage_percentage) if adv is not None and adv.usage_percentage is not None else None,
                "touches": float(adv.touches) if adv is not None and adv.touches is not None else None,
                "passes": float(adv.passes) if adv is not None and adv.passes is not None else None,
            }
        )

    summaries: list[AbsenceImpactRow] = []
    for (beneficiary_player_id, beneficiary_player_name), teammate_rows in rows_by_teammate.items():
        if beneficiary_player_id == str(source_player_id):
            continue
        active_rows = [row for row in teammate_rows if str(row["game_id"]) in source_active_games]
        out_rows = [row for row in teammate_rows if str(row["game_id"]) in out_game_ids]
        if len(active_rows) < effective_min_active_games or len(out_rows) < min_out_games:
            continue

        confidence = _sample_confidence(len(active_rows), len(out_rows))
        minutes_delta = _delta(active_rows, out_rows, "minutes")
        points_delta = _delta(active_rows, out_rows, "points")
        rebounds_delta = _delta(active_rows, out_rows, "rebounds")
        assists_delta = _delta(active_rows, out_rows, "assists")
        blocks_delta = _delta(active_rows, out_rows, "blocks")
        usage_delta = _delta(active_rows, out_rows, "usage")
        touches_delta = _delta(active_rows, out_rows, "touches")
        passes_delta = _delta(active_rows, out_rows, "passes")

        summaries.append(
            AbsenceImpactRow(
                source_player_id=str(source_player_id),
                source_player_name=str(source_player_name),
                beneficiary_player_id=str(beneficiary_player_id),
                beneficiary_player_name=str(beneficiary_player_name),
                team_abbreviation=str(team_abbreviation),
                window_start_date=dataset.window_start_date,
                window_end_date=dataset.window_end_date,
                source_out_game_count=len(out_game_ids),
                source_active_game_count=len(source_active_games),
                beneficiary_out_game_count=len(out_rows),
                beneficiary_active_game_count=len(active_rows),
                minutes_delta=minutes_delta,
                points_delta=points_delta,
                rebounds_delta=rebounds_delta,
                assists_delta=assists_delta,
                blocks_delta=blocks_delta,
                usage_delta=usage_delta,
                touches_delta=touches_delta,
                passes_delta=passes_delta,
                impact_score=_impact_score(
                    minutes_delta=minutes_delta,
                    usage_delta=usage_delta,
                    points_delta=points_delta,
                    touches_delta=touches_delta,
                    sample_confidence=confidence,
                ),
                sample_confidence=confidence,
            )
        )

    summaries.sort(key=lambda row: (row.impact_score or 0.0, row.minutes_delta or 0.0), reverse=True)
    return AbsenceImpactBuildResult(
        source_player_id=str(source_player_id),
        source_player_name=str(source_player_name),
        team_abbreviation=str(team_abbreviation),
        source_out_game_count=len(out_game_ids),
        source_active_game_count=len(source_active_games),
        summary_count=len(summaries),
        persisted=False,
        rows=summaries,
    )


def build_absence_impact_rows(
    *,
    source_player_id: str,
    team_abbreviation: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_active_games: int = 5,
    min_out_games: int = 2,
) -> AbsenceImpactBuildResult:
    dataset = _load_absence_dataset(start_date=start_date, end_date=end_date)
    return _build_absence_impact_rows_from_dataset(
        dataset,
        source_player_id=source_player_id,
        team_abbreviation=team_abbreviation,
        min_active_games=min_active_games,
        min_out_games=min_out_games,
    )


def select_starter_pool_absence_sources(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_active_games: int = 8,
    min_out_games: int = 0,
    max_sources_per_team: int = 5,
    min_avg_minutes: float = 24.0,
    min_start_rate: float = 0.35,
    max_days_since_last_team_game: int = 10,
    returning_star_min_active_games: int = 2,
    returning_star_min_avg_minutes: float = 28.0,
    returning_star_min_start_rate: float = 0.8,
    returning_star_min_out_games: int = 20,
) -> list[AbsenceImpactSourceSelection]:
    dataset = _load_absence_dataset(start_date=start_date, end_date=end_date)

    rows_by_source: dict[tuple[str, str, str], list[HistoricalGameLog]] = defaultdict(list)
    for row in dataset.logs:
        rows_by_source[(str(row.team), str(row.player_id), str(row.player_name))].append(row)

    reference_date = _effective_reference_date(dataset)
    selections_by_team: dict[str, list[AbsenceImpactSourceSelection]] = defaultdict(list)
    for (team_abbreviation, source_player_id, source_player_name), _rows in rows_by_source.items():
        rows = _current_team_tenure_rows(dataset, player_id=source_player_id, team_abbreviation=team_abbreviation)
        if not rows:
            continue
        active_games = {str(row.game_id) for row in rows}
        out_game_ids = _resolve_out_game_ids(dataset, source_player_id=source_player_id, team_abbreviation=team_abbreviation) - active_games

        source_override = _resolve_source_override(
            dataset,
            team_abbreviation=team_abbreviation,
            player_id=source_player_id,
            player_name=source_player_name,
            reference_date=reference_date,
        )
        if source_override is not None and not source_override.include_as_source:
            continue
        forced_include = source_override is not None and source_override.include_as_source

        avg_minutes, avg_usage, avg_touches, avg_passes, start_rate, close_rate = _source_role_stats(dataset, rows)
        tenure_end_date = max(row.game_date.date() for row in rows)
        if (
            not forced_include
            and reference_date is not None
            and tenure_end_date < (reference_date - timedelta(days=max_days_since_last_team_game))
        ):
            continue

        qualifies_standard = len(active_games) >= min_active_games and len(out_game_ids) >= min_out_games
        qualifies_returning_star = (
            len(active_games) >= returning_star_min_active_games
            and len(out_game_ids) >= returning_star_min_out_games
            and avg_minutes >= returning_star_min_avg_minutes
            and (start_rate is None or (start_rate or 0.0) >= returning_star_min_start_rate)
        )
        if not forced_include and not qualifies_standard and not qualifies_returning_star:
            continue

        if not forced_include and (start_rate or 0.0) < min_start_rate and avg_minutes < min_avg_minutes:
            continue

        selection_score = _selection_score(
            avg_minutes=avg_minutes,
            avg_usage=avg_usage,
            avg_touches=avg_touches,
            avg_passes=avg_passes,
            start_rate=start_rate,
            close_rate=close_rate,
            out_game_count=len(out_game_ids),
        )
        if qualifies_returning_star:
            selection_score += 25.0
        if forced_include:
            selection_score += OVERRIDE_PRIORITY_BONUS

        candidate = AbsenceImpactSourceSelection(
            source_player_id=source_player_id,
            source_player_name=source_player_name,
            team_abbreviation=team_abbreviation,
            active_game_count=len(active_games),
            out_game_count=len(out_game_ids),
            avg_minutes=round(avg_minutes, 4),
            avg_usage=round(avg_usage, 4) if avg_usage is not None else None,
            avg_touches=round(avg_touches, 4) if avg_touches is not None else None,
            avg_passes=round(avg_passes, 4) if avg_passes is not None else None,
            start_rate=round(start_rate, 4) if start_rate is not None else None,
            close_rate=round(close_rate, 4) if close_rate is not None else None,
            tenure_start_date=min(row.game_date.date() for row in rows) if rows else None,
            tenure_end_date=max(row.game_date.date() for row in rows) if rows else None,
            selection_score=selection_score,
        )
        selections_by_team[team_abbreviation].append(candidate)

    flattened: list[AbsenceImpactSourceSelection] = []
    for team_abbreviation, candidates in selections_by_team.items():
        candidates.sort(key=lambda row: row.selection_score, reverse=True)
        flattened.extend(candidates[:max_sources_per_team])
    return sorted(flattened, key=lambda row: (row.team_abbreviation, -row.selection_score))



def select_first_pass_absence_sources(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_active_games: int = 8,
    min_out_games: int = 2,
) -> list[AbsenceImpactSourceSelection]:
    return select_starter_pool_absence_sources(
        start_date=start_date,
        end_date=end_date,
        min_active_games=min_active_games,
        min_out_games=min_out_games,
        max_sources_per_team=1,
    )


def persist_absence_impact_rows(result: AbsenceImpactBuildResult) -> int:
    if not result.rows:
        return 0
    with session_scope() as session:
        for row in result.rows:
            session.query(AbsenceImpactSummary).filter(
                AbsenceImpactSummary.source_player_id == row.source_player_id,
                AbsenceImpactSummary.beneficiary_player_id == row.beneficiary_player_id,
                AbsenceImpactSummary.team_abbreviation == row.team_abbreviation,
                AbsenceImpactSummary.window_start_date == row.window_start_date,
                AbsenceImpactSummary.window_end_date == row.window_end_date,
            ).delete(synchronize_session=False)
            session.add(AbsenceImpactSummary(**asdict(row)))
    return len(result.rows)


def build_and_persist_absence_impact(
    *,
    source_player_id: str,
    team_abbreviation: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_active_games: int = 5,
    min_out_games: int = 2,
) -> AbsenceImpactBuildResult:
    result = build_absence_impact_rows(
        source_player_id=source_player_id,
        team_abbreviation=team_abbreviation,
        start_date=start_date,
        end_date=end_date,
        min_active_games=min_active_games,
        min_out_games=min_out_games,
    )
    persisted_count = persist_absence_impact_rows(result)
    return AbsenceImpactBuildResult(
        source_player_id=result.source_player_id,
        source_player_name=result.source_player_name,
        team_abbreviation=result.team_abbreviation,
        source_out_game_count=result.source_out_game_count,
        source_active_game_count=result.source_active_game_count,
        summary_count=persisted_count,
        persisted=bool(persisted_count),
        rows=result.rows,
    )


def build_and_persist_first_pass_absence_impact_batch(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_active_games: int = 8,
    min_out_games: int = 2,
) -> AbsenceImpactBatchResult:
    return build_and_persist_starter_pool_absence_impact_batch(
        start_date=start_date,
        end_date=end_date,
        min_active_games=min_active_games,
        min_out_games=min_out_games,
        max_sources_per_team=1,
    )



def build_and_persist_starter_pool_absence_impact_batch(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_active_games: int = 8,
    min_out_games: int = 2,
    selection_min_out_games: int = 0,
    max_sources_per_team: int = 5,
    min_avg_minutes: float = 24.0,
    min_start_rate: float = 0.35,
) -> AbsenceImpactBatchResult:
    dataset = _load_absence_dataset(start_date=start_date, end_date=end_date)
    selections = select_starter_pool_absence_sources(
        start_date=start_date,
        end_date=end_date,
        min_active_games=min_active_games,
        min_out_games=selection_min_out_games,
        max_sources_per_team=max_sources_per_team,
        min_avg_minutes=min_avg_minutes,
        min_start_rate=min_start_rate,
    )

    results: list[AbsenceImpactBuildResult] = []
    summary_count = 0
    for selection in selections:
        build_result = _build_absence_impact_rows_from_dataset(
            dataset,
            source_player_id=selection.source_player_id,
            team_abbreviation=selection.team_abbreviation,
            min_active_games=min_active_games,
            min_out_games=min_out_games,
        )
        persisted_count = persist_absence_impact_rows(build_result)
        summary_count += persisted_count
        results.append(
            AbsenceImpactBuildResult(
                source_player_id=build_result.source_player_id,
                source_player_name=build_result.source_player_name,
                team_abbreviation=build_result.team_abbreviation,
                source_out_game_count=build_result.source_out_game_count,
                source_active_game_count=build_result.source_active_game_count,
                summary_count=persisted_count,
                persisted=bool(persisted_count),
                rows=build_result.rows,
            )
        )

    return AbsenceImpactBatchResult(
        source_count=len(selections),
        summary_count=summary_count,
        persisted=bool(summary_count),
        selections=selections,
        results=results,
    )
