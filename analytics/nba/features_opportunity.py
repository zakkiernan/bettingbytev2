from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime
from statistics import mean, median, pstdev
from typing import Any

from sqlalchemy.orm import Session

from analytics.injury_report_loader import (
    OfficialInjuryReportIndex,
    build_official_injury_report_index,
    get_official_team_rows,
    get_official_team_summary,
    load_latest_official_injury_report_rows,
    match_official_injury_row,
)
from analytics.name_matching import normalize_name
from analytics.pregame_context_loader import (
    PregameContextIndex,
    build_pregame_context_index,
    load_pregame_context_feature_rows,
    load_pregame_context_snapshot_rows,
    match_pregame_context_row,
)
from database.db import session_scope
from database.models import (
    AbsenceImpactSummary,
    Game,
    HistoricalAdvancedLog,
    HistoricalGameLog,
    PlayerPropSnapshot,
    PlayerRotationGame,
    Team,
    TeamDefensiveStat,
)


@dataclass(slots=True)
class TeamPlayerRoleProfile:
    player_id: str
    baseline_minutes: float
    baseline_usage: float
    baseline_passes: float
    baseline_touches: float
    baseline_rebounds: float
    baseline_blocks: float
    baseline_threes: float
    start_rate: float
    close_rate: float
    ballhandler_score: float
    usage_score: float
    frontcourt_score: float


@dataclass(slots=True)
class TeamRolePrior:
    team_id: str
    team_abbreviation: str
    top7_player_ids: set[str]
    top9_player_ids: set[str]
    high_usage_player_ids: set[str]
    primary_ballhandler_ids: set[str]
    frontcourt_player_ids: set[str]
    player_role_profiles: dict[str, TeamPlayerRoleProfile]
    baseline_minutes_by_player_id: dict[str, float]
    baseline_usage_by_player_id: dict[str, float]


@dataclass(slots=True)
class AbsenceImpactIndex:
    by_team_beneficiary_source_id: dict[tuple[str, str, str], AbsenceImpactSummary]
    by_team_beneficiary_source_name: dict[tuple[str, str, str], AbsenceImpactSummary]


@dataclass(slots=True)
class PregameFeatureRequest:
    game_id: str
    player_id: str
    player_name: str
    stat_type: str
    captured_at: datetime
    line: float = 0.0
    over_odds: int = 0
    under_odds: int = 0
    game_date: datetime | None = None
    team_abbreviation: str | None = None
    opponent_abbreviation: str | None = None
    is_home: bool | None = None


@dataclass(slots=True)
class PregameOpportunityFeatures:
    game_id: str
    player_id: str
    player_name: str
    captured_at: datetime
    game_date: datetime | None = None
    team_abbreviation: str | None = None
    opponent_abbreviation: str | None = None
    is_home: bool | None = None
    days_rest: int | None = None
    back_to_back: bool | None = None
    sample_size: int = 0
    last5_count: int = 0
    last10_count: int = 0
    season_minutes_avg: float | None = None
    last10_minutes_avg: float | None = None
    last5_minutes_avg: float | None = None
    last10_minutes_std: float | None = None
    rotation_sample_size: int = 0
    season_rotation_minutes_avg: float | None = None
    last10_rotation_minutes_avg: float | None = None
    last5_rotation_minutes_avg: float | None = None
    last10_rotation_minutes_std: float | None = None
    season_stint_count_avg: float | None = None
    last10_stint_count_avg: float | None = None
    last5_stint_count_avg: float | None = None
    season_started_rate: float | None = None
    last10_started_rate: float | None = None
    last5_started_rate: float | None = None
    season_closed_rate: float | None = None
    last10_closed_rate: float | None = None
    last5_closed_rate: float | None = None
    season_usage_pct: float | None = None
    last10_usage_pct: float | None = None
    last5_usage_pct: float | None = None
    season_est_usage_pct: float | None = None
    last10_est_usage_pct: float | None = None
    last5_est_usage_pct: float | None = None
    season_touches: float | None = None
    last10_touches: float | None = None
    last5_touches: float | None = None
    season_passes: float | None = None
    last10_passes: float | None = None
    last5_passes: float | None = None
    season_off_rating: float | None = None
    last10_off_rating: float | None = None
    last5_off_rating: float | None = None
    team_pace: float | None = None
    opponent_def_rating: float | None = None
    opponent_pace: float | None = None
    opponent_points_allowed: float | None = None
    opponent_fg_pct_allowed: float | None = None
    opponent_3pt_pct_allowed: float | None = None
    league_avg_def_rating: float | None = None
    league_avg_pace: float | None = None
    league_avg_opponent_points: float | None = None
    official_injury_status: str | None = None
    official_injury_reason: str | None = None
    official_report_datetime_utc: datetime | None = None
    official_teammate_out_count: float | None = None
    official_teammate_doubtful_count: float | None = None
    official_teammate_questionable_count: float | None = None
    expected_start: bool | None = None
    starter_confidence: float | None = None
    official_available: bool | None = None
    projected_available: bool | None = None
    late_scratch_risk: float | None = None
    teammate_out_count_top7: float | None = None
    teammate_out_count_top9: float | None = None
    missing_high_usage_teammates: float | None = None
    missing_primary_ballhandler: bool | None = None
    missing_frontcourt_rotation_piece: bool | None = None
    vacated_minutes_proxy: float | None = None
    vacated_usage_proxy: float | None = None
    role_replacement_minutes_proxy: float | None = None
    role_replacement_usage_proxy: float | None = None
    role_replacement_touches_proxy: float | None = None
    role_replacement_passes_proxy: float | None = None
    absence_impact_minutes_delta: float | None = None
    absence_impact_usage_delta: float | None = None
    absence_impact_touches_delta: float | None = None
    absence_impact_passes_delta: float | None = None
    absence_impact_sample_confidence: float | None = None
    absence_impact_source_count: float | None = None
    projected_lineup_confirmed: bool | None = None
    official_starter_flag: bool | None = None
    pregame_context_confidence: float | None = None
    pregame_context_attached: bool | None = None
    official_injury_attached: bool | None = None
    context_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PregameFeatureSeed:
    game_id: str
    player_id: str
    player_name: str
    stat_type: str
    line: float
    over_odds: int
    under_odds: int
    captured_at: datetime
    game_date: datetime | None
    team_abbreviation: str | None
    opponent_abbreviation: str | None
    is_home: bool | None
    days_rest: int | None
    back_to_back: bool | None
    recent_logs: list[HistoricalGameLog]
    advanced_rows: list[HistoricalAdvancedLog]
    rotation_rows: list[PlayerRotationGame]
    team_defense: TeamDefensiveStat | None
    opponent_defense: TeamDefensiveStat | None
    league_avg_def_rating: float | None
    league_avg_pace: float | None
    league_avg_opponent_points: float | None
    pregame_context_row: dict[str, Any] | None = None
    official_injury_row: dict[str, Any] | None = None
    official_injury_team_summary: dict[str, Any] | None = None
    official_injury_team_rows: list[dict[str, Any]] | None = None
    absence_impact_index: AbsenceImpactIndex | None = None
    team_role_prior: TeamRolePrior | None = None

    def build_opportunity_features(self) -> PregameOpportunityFeatures:
        official_injury_attached = _has_official_injury_context(
            official_injury_row=self.official_injury_row,
            official_injury_team_summary=self.official_injury_team_summary,
            official_injury_team_rows=self.official_injury_team_rows,
        )
        context_source = _resolve_context_source(
            pregame_context_row=self.pregame_context_row,
            official_injury_attached=official_injury_attached,
            official_injury_row=self.official_injury_row,
        )
        context_aggregates = _merge_context_aggregates(
            _build_pregame_context_aggregates(self.pregame_context_row),
            _build_official_injury_aggregates(
                self.official_injury_row,
                self.official_injury_team_summary,
                team_rows=self.official_injury_team_rows,
                team_role_prior=self.team_role_prior,
                player_id=self.player_id,
                team_abbreviation=self.team_abbreviation,
                absence_impact_index=self.absence_impact_index,
                captured_at=self.captured_at,
            ),
        )
        context_aggregates = _apply_context_source_confidence_cap(context_aggregates, context_source=context_source)
        return PregameOpportunityFeatures(
            game_id=self.game_id,
            player_id=self.player_id,
            player_name=self.player_name,
            captured_at=self.captured_at,
            game_date=self.game_date,
            team_abbreviation=self.team_abbreviation,
            opponent_abbreviation=self.opponent_abbreviation,
            is_home=self.is_home,
            days_rest=self.days_rest,
            back_to_back=self.back_to_back,
            team_pace=self.team_defense.pace if self.team_defense else None,
            opponent_def_rating=self.opponent_defense.defensive_rating if self.opponent_defense else None,
            opponent_pace=self.opponent_defense.pace if self.opponent_defense else None,
            opponent_points_allowed=self.opponent_defense.opponent_points_per_game if self.opponent_defense else None,
            opponent_fg_pct_allowed=self.opponent_defense.opponent_field_goal_percentage if self.opponent_defense else None,
            opponent_3pt_pct_allowed=self.opponent_defense.opponent_three_point_percentage if self.opponent_defense else None,
            league_avg_def_rating=self.league_avg_def_rating,
            league_avg_pace=self.league_avg_pace,
            league_avg_opponent_points=self.league_avg_opponent_points,
            pregame_context_attached=self.pregame_context_row is not None,
            official_injury_attached=official_injury_attached,
            context_source=context_source,
            **_build_shared_log_aggregates(self.recent_logs),
            **_build_rotation_aggregates(self.rotation_rows),
            **_build_shared_advanced_aggregates(self.advanced_rows),
            **context_aggregates,
        )


def _values(rows: list[Any], attr: str) -> list[float]:
    collected: list[float] = []
    for row in rows:
        value = getattr(row, attr, None)
        if value is not None:
            collected.append(float(value))
    return collected


def _mean(values: list[float]) -> float | None:
    return mean(values) if values else None


def _median(values: list[float]) -> float | None:
    return median(values) if values else None


def _std(values: list[float]) -> float | None:
    return pstdev(values) if len(values) > 1 else 0.0 if values else None


def _safe_pct(makes: list[float], attempts: list[float]) -> float | None:
    total_attempts = sum(attempts)
    if total_attempts <= 0:
        return None
    return sum(makes) / total_attempts


def _weighted_average(weighted_values: list[tuple[float, float | None]]) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for weight, value in weighted_values:
        if value is None:
            continue
        numerator += weight * float(value)
        denominator += weight
    if denominator == 0:
        return None
    return numerator / denominator


def _season_from_game_date(game_date: datetime | None) -> str | None:
    if game_date is None:
        return None
    if game_date.month >= 10:
        return f"{game_date.year}-{str(game_date.year + 1)[-2:]}"
    return f"{game_date.year - 1}-{str(game_date.year)[-2:]}"


def _sort_logs_desc(rows: list[HistoricalGameLog]) -> list[HistoricalGameLog]:
    return sorted(
        [row for row in rows if row.game_date is not None],
        key=lambda row: (row.game_date, row.game_id),
        reverse=True,
    )


def _resolve_team_context(
    candidate_team: str | None,
    candidate_opponent: str | None,
    game: Game | None,
    latest_log: HistoricalGameLog | None,
    request_is_home: bool | None = None,
) -> tuple[str | None, str | None, bool | None]:
    if game is None:
        if request_is_home is not None:
            return candidate_team, candidate_opponent, request_is_home
        return candidate_team, candidate_opponent, latest_log.is_home if latest_log else None

    home = game.home_team_abbreviation
    away = game.away_team_abbreviation
    teams = {home, away}

    if candidate_team in teams:
        opponent = away if candidate_team == home else home
        return candidate_team, opponent, candidate_team == home

    if candidate_opponent in teams:
        team = away if candidate_opponent == home else home
        return team, candidate_opponent, team == home

    if latest_log and latest_log.team in teams:
        opponent = away if latest_log.team == home else home
        return latest_log.team, opponent, latest_log.team == home

    return candidate_team, candidate_opponent, request_is_home if request_is_home is not None else latest_log.is_home if latest_log else None


def _build_defense_context(
    team_defense_rows: list[TeamDefensiveStat],
) -> tuple[
    dict[tuple[str, str], TeamDefensiveStat],
    dict[str, float | None],
    dict[str, float | None],
    dict[str, float | None],
]:
    defense_by_season_team: dict[tuple[str, str], TeamDefensiveStat] = {}
    def_rating_by_season: dict[str, list[float]] = defaultdict(list)
    pace_by_season: dict[str, list[float]] = defaultdict(list)
    opp_points_by_season: dict[str, list[float]] = defaultdict(list)

    for row in team_defense_rows:
        defense_by_season_team[(row.season, row.team_id)] = row
        if row.defensive_rating is not None:
            def_rating_by_season[row.season].append(float(row.defensive_rating))
        if row.pace is not None:
            pace_by_season[row.season].append(float(row.pace))
        if row.opponent_points_per_game is not None:
            opp_points_by_season[row.season].append(float(row.opponent_points_per_game))

    league_avg_def_rating = {season: _mean(values) for season, values in def_rating_by_season.items()}
    league_avg_pace = {season: _mean(values) for season, values in pace_by_season.items()}
    league_avg_opponent_points = {season: _mean(values) for season, values in opp_points_by_season.items()}
    return defense_by_season_team, league_avg_def_rating, league_avg_pace, league_avg_opponent_points


def _build_shared_log_aggregates(logs: list[HistoricalGameLog]) -> dict[str, float | int | None]:
    last10 = logs[:10]
    last5 = logs[:5]
    return {
        "sample_size": len(logs),
        "last10_count": len(last10),
        "last5_count": len(last5),
        "season_minutes_avg": _mean(_values(logs, "minutes")),
        "last10_minutes_avg": _mean(_values(last10, "minutes")),
        "last5_minutes_avg": _mean(_values(last5, "minutes")),
        "last10_minutes_std": _std(_values(last10, "minutes")),
    }


def _build_rotation_aggregates(rows: list[PlayerRotationGame]) -> dict[str, float | int | None]:
    last10 = rows[:10]
    last5 = rows[:5]

    def rotation_minutes(sample: list[PlayerRotationGame]) -> list[float]:
        values: list[float] = []
        for row in sample:
            if row.total_shift_duration_real is None:
                continue
            values.append(float(row.total_shift_duration_real) / 600.0)
        return values

    def flag_rate(sample: list[PlayerRotationGame], attr: str) -> float | None:
        values = [1.0 if getattr(row, attr) else 0.0 for row in sample if getattr(row, attr) is not None]
        return _mean(values)

    return {
        "rotation_sample_size": len(rows),
        "season_rotation_minutes_avg": _mean(rotation_minutes(rows)),
        "last10_rotation_minutes_avg": _mean(rotation_minutes(last10)),
        "last5_rotation_minutes_avg": _mean(rotation_minutes(last5)),
        "last10_rotation_minutes_std": _std(rotation_minutes(last10)),
        "season_stint_count_avg": _mean(_values(rows, "stint_count")),
        "last10_stint_count_avg": _mean(_values(last10, "stint_count")),
        "last5_stint_count_avg": _mean(_values(last5, "stint_count")),
        "season_started_rate": flag_rate(rows, "started"),
        "last10_started_rate": flag_rate(last10, "started"),
        "last5_started_rate": flag_rate(last5, "started"),
        "season_closed_rate": flag_rate(rows, "closed_game"),
        "last10_closed_rate": flag_rate(last10, "closed_game"),
        "last5_closed_rate": flag_rate(last5, "closed_game"),
    }


def _build_shared_advanced_aggregates(rows: list[HistoricalAdvancedLog]) -> dict[str, float | None]:
    last10 = rows[:10]
    last5 = rows[:5]
    return {
        "season_usage_pct": _mean(_values(rows, "usage_percentage")),
        "last10_usage_pct": _mean(_values(last10, "usage_percentage")),
        "last5_usage_pct": _mean(_values(last5, "usage_percentage")),
        "season_est_usage_pct": _mean(_values(rows, "estimated_usage_percentage")),
        "last10_est_usage_pct": _mean(_values(last10, "estimated_usage_percentage")),
        "last5_est_usage_pct": _mean(_values(last5, "estimated_usage_percentage")),
        "season_touches": _mean(_values(rows, "touches")),
        "last10_touches": _mean(_values(last10, "touches")),
        "last5_touches": _mean(_values(last5, "touches")),
        "season_passes": _mean(_values(rows, "passes")),
        "last10_passes": _mean(_values(last10, "passes")),
        "last5_passes": _mean(_values(last5, "passes")),
        "season_off_rating": _mean(_values(rows, "offensive_rating")),
        "last10_off_rating": _mean(_values(last10, "offensive_rating")),
        "last5_off_rating": _mean(_values(last5, "offensive_rating")),
    }


def _player_role_similarity(target: TeamPlayerRoleProfile, missing: TeamPlayerRoleProfile) -> float:
    ballhandler_similarity = 1.0 - min(abs(target.ballhandler_score - missing.ballhandler_score), 1.0)
    usage_similarity = 1.0 - min(abs(target.usage_score - missing.usage_score), 1.0)
    frontcourt_similarity = 1.0 - min(abs(target.frontcourt_score - missing.frontcourt_score), 1.0)
    start_similarity = 1.0 - min(abs(target.start_rate - missing.start_rate), 1.0)
    close_similarity = 1.0 - min(abs(target.close_rate - missing.close_rate), 1.0)
    return max(
        0.0,
        min(
            1.0,
            0.34 * frontcourt_similarity
            + 0.26 * ballhandler_similarity
            + 0.18 * usage_similarity
            + 0.12 * start_similarity
            + 0.10 * close_similarity,
        ),
    )


def _build_team_role_prior_from_rows(
    *,
    team_id: str,
    team_abbreviation: str,
    logs: list[HistoricalGameLog],
    advanced_rows: list[HistoricalAdvancedLog],
    rotation_rows: list[PlayerRotationGame],
) -> TeamRolePrior | None:
    if not logs:
        return None

    minutes_by_player: dict[str, list[float]] = defaultdict(list)
    usage_by_player: dict[str, list[float]] = defaultdict(list)
    passes_by_player: dict[str, list[float]] = defaultdict(list)
    touches_by_player: dict[str, list[float]] = defaultdict(list)
    rebounds_by_player: dict[str, list[float]] = defaultdict(list)
    blocks_by_player: dict[str, list[float]] = defaultdict(list)
    threes_by_player: dict[str, list[float]] = defaultdict(list)
    start_flags_by_player: dict[str, list[float]] = defaultdict(list)
    close_flags_by_player: dict[str, list[float]] = defaultdict(list)

    for log in logs:
        if log.minutes is not None:
            minutes_by_player[log.player_id].append(float(log.minutes))
        if log.rebounds is not None:
            rebounds_by_player[log.player_id].append(float(log.rebounds))
        if log.blocks is not None:
            blocks_by_player[log.player_id].append(float(log.blocks))
        if log.threes_made is not None:
            threes_by_player[log.player_id].append(float(log.threes_made))

    for row in advanced_rows:
        if row.usage_percentage is not None:
            usage_by_player[row.player_id].append(float(row.usage_percentage))
        if row.passes is not None:
            passes_by_player[row.player_id].append(float(row.passes))
        if row.touches is not None:
            touches_by_player[row.player_id].append(float(row.touches))

    for row in rotation_rows:
        if row.started is not None:
            start_flags_by_player[row.player_id].append(1.0 if row.started else 0.0)
        if row.closed_game is not None:
            close_flags_by_player[row.player_id].append(1.0 if row.closed_game else 0.0)

    player_ids = sorted(minutes_by_player.keys())
    if not player_ids:
        return None

    baseline_minutes = {player_id: _mean(values) or 0.0 for player_id, values in minutes_by_player.items()}
    baseline_usage = {player_id: _mean(values) or 0.0 for player_id, values in usage_by_player.items()}
    baseline_passes = {player_id: _mean(values) or 0.0 for player_id, values in passes_by_player.items()}
    baseline_touches = {player_id: _mean(values) or 0.0 for player_id, values in touches_by_player.items()}
    baseline_rebounds = {player_id: _mean(values) or 0.0 for player_id, values in rebounds_by_player.items()}
    baseline_blocks = {player_id: _mean(values) or 0.0 for player_id, values in blocks_by_player.items()}
    baseline_threes = {player_id: _mean(values) or 0.0 for player_id, values in threes_by_player.items()}
    start_rates = {player_id: _mean(values) or 0.0 for player_id, values in start_flags_by_player.items()}
    close_rates = {player_id: _mean(values) or 0.0 for player_id, values in close_flags_by_player.items()}

    role_rank = sorted(
        player_ids,
        key=lambda player_id: (
            baseline_minutes.get(player_id, 0.0)
            + 4.0 * start_rates.get(player_id, 0.0)
            + 2.0 * close_rates.get(player_id, 0.0),
            baseline_usage.get(player_id, 0.0),
        ),
        reverse=True,
    )
    usage_rank = sorted(player_ids, key=lambda player_id: baseline_usage.get(player_id, 0.0), reverse=True)
    ballhandler_rank = sorted(
        player_ids,
        key=lambda player_id: (baseline_passes.get(player_id, 0.0) * 0.7) + (baseline_touches.get(player_id, 0.0) * 0.3),
        reverse=True,
    )
    frontcourt_rank = sorted(
        player_ids,
        key=lambda player_id: (
            baseline_rebounds.get(player_id, 0.0) * 0.70
            + baseline_blocks.get(player_id, 0.0) * 2.0
            - baseline_threes.get(player_id, 0.0) * 0.15
        ),
        reverse=True,
    )

    max_usage = max((baseline_usage.get(player_id, 0.0) for player_id in player_ids), default=0.0)
    max_passes = max((baseline_passes.get(player_id, 0.0) for player_id in player_ids), default=0.0)
    max_touches = max((baseline_touches.get(player_id, 0.0) for player_id in player_ids), default=0.0)
    max_frontcourt_raw = max(
        (
            baseline_rebounds.get(player_id, 0.0) * 0.70
            + baseline_blocks.get(player_id, 0.0) * 2.0
            - baseline_threes.get(player_id, 0.0) * 0.15
            for player_id in player_ids
        ),
        default=0.0,
    )

    player_role_profiles: dict[str, TeamPlayerRoleProfile] = {}
    for player_id in player_ids:
        ballhandler_raw = baseline_passes.get(player_id, 0.0) * 0.7 + baseline_touches.get(player_id, 0.0) * 0.3
        frontcourt_raw = (
            baseline_rebounds.get(player_id, 0.0) * 0.70
            + baseline_blocks.get(player_id, 0.0) * 2.0
            - baseline_threes.get(player_id, 0.0) * 0.15
        )
        player_role_profiles[player_id] = TeamPlayerRoleProfile(
            player_id=player_id,
            baseline_minutes=baseline_minutes.get(player_id, 0.0),
            baseline_usage=baseline_usage.get(player_id, 0.0),
            baseline_passes=baseline_passes.get(player_id, 0.0),
            baseline_touches=baseline_touches.get(player_id, 0.0),
            baseline_rebounds=baseline_rebounds.get(player_id, 0.0),
            baseline_blocks=baseline_blocks.get(player_id, 0.0),
            baseline_threes=baseline_threes.get(player_id, 0.0),
            start_rate=start_rates.get(player_id, 0.0),
            close_rate=close_rates.get(player_id, 0.0),
            ballhandler_score=(ballhandler_raw / max(ballhandler_raw, max_passes * 0.7 + max_touches * 0.3, 1.0)),
            usage_score=(baseline_usage.get(player_id, 0.0) / max(max_usage, 0.01)),
            frontcourt_score=max(0.0, frontcourt_raw) / max(max(max_frontcourt_raw, 0.0), 1.0),
        )

    return TeamRolePrior(
        team_id=team_id,
        team_abbreviation=team_abbreviation,
        top7_player_ids=set(role_rank[:7]),
        top9_player_ids=set(role_rank[:9]),
        high_usage_player_ids=set(usage_rank[: min(4, len(usage_rank))]),
        primary_ballhandler_ids=set(ballhandler_rank[: min(2, len(ballhandler_rank))]),
        frontcourt_player_ids=set(frontcourt_rank[: min(4, len(frontcourt_rank))]),
        player_role_profiles=player_role_profiles,
        baseline_minutes_by_player_id=baseline_minutes,
        baseline_usage_by_player_id=baseline_usage,
    )


def _load_recent_team_game_ids(
    logs: list[HistoricalGameLog],
    *,
    cutoff: datetime | None,
    lookback_games: int,
) -> list[str]:
    game_ids: list[str] = []
    seen: set[str] = set()
    for log in _sort_logs_desc(logs):
        if cutoff is not None and log.game_date >= cutoff:
            continue
        if log.game_id in seen:
            continue
        seen.add(log.game_id)
        game_ids.append(log.game_id)
        if len(game_ids) >= lookback_games:
            break
    return game_ids


def load_team_role_prior(
    session: Session,
    *,
    team_id: str | None,
    team_abbreviation: str | None,
    cutoff: datetime | None,
    cache: dict[tuple[str, str], TeamRolePrior | None] | None = None,
    lookback_games: int = 20,
    logs_by_team: dict[str, list[HistoricalGameLog]] | None = None,
    advanced_by_player_game: dict[tuple[str, str], HistoricalAdvancedLog] | None = None,
    rotation_by_team_game_player: dict[tuple[str, str, str], PlayerRotationGame] | None = None,
) -> TeamRolePrior | None:
    resolved_team_abbr = (team_abbreviation or "").upper()
    resolved_team_id = str(team_id) if team_id else ""
    cache_key = (resolved_team_id or resolved_team_abbr, cutoff.isoformat() if cutoff is not None else "")
    if cache is not None and cache_key in cache:
        return cache[cache_key]

    if not resolved_team_abbr and resolved_team_id:
        team = session.get(Team, resolved_team_id)
        resolved_team_abbr = (team.abbreviation if team and team.abbreviation else "").upper()
    if not resolved_team_id and resolved_team_abbr:
        team = session.query(Team).filter(Team.abbreviation == resolved_team_abbr).one_or_none()
        resolved_team_id = str(team.team_id) if team is not None else ""
    if not resolved_team_abbr:
        return None

    if logs_by_team is not None:
        team_logs_pool = list(logs_by_team.get(resolved_team_abbr, []))
    else:
        query = session.query(HistoricalGameLog).filter(HistoricalGameLog.team == resolved_team_abbr)
        if cutoff is not None:
            query = query.filter(HistoricalGameLog.game_date < cutoff)
        team_logs_pool = query.all()

    recent_game_ids = _load_recent_team_game_ids(team_logs_pool, cutoff=cutoff, lookback_games=lookback_games)
    if not recent_game_ids:
        if cache is not None:
            cache[cache_key] = None
        return None

    recent_game_id_set = set(recent_game_ids)
    team_logs = [log for log in team_logs_pool if log.game_id in recent_game_id_set]

    if advanced_by_player_game is not None:
        advanced_rows = [
            row
            for (player_id, game_id), row in advanced_by_player_game.items()
            if game_id in recent_game_id_set and player_id in {log.player_id for log in team_logs}
        ]
    else:
        advanced_rows = (
            session.query(HistoricalAdvancedLog)
            .filter(
                HistoricalAdvancedLog.game_id.in_(recent_game_ids),
                HistoricalAdvancedLog.player_id.in_([log.player_id for log in team_logs]),
            )
            .all()
        )

    if rotation_by_team_game_player is not None and resolved_team_id:
        rotation_rows = [
            row
            for (row_team_id, game_id, _player_id), row in rotation_by_team_game_player.items()
            if row_team_id == resolved_team_id and game_id in recent_game_id_set
        ]
    elif resolved_team_id:
        rotation_rows = (
            session.query(PlayerRotationGame)
            .filter(PlayerRotationGame.team_id == resolved_team_id, PlayerRotationGame.game_id.in_(recent_game_ids))
            .all()
        )
    else:
        rotation_rows = []

    prior = _build_team_role_prior_from_rows(
        team_id=resolved_team_id,
        team_abbreviation=resolved_team_abbr,
        logs=team_logs,
        advanced_rows=advanced_rows,
        rotation_rows=rotation_rows,
    )
    if cache is not None:
        cache[cache_key] = prior
    return prior


def build_team_role_priors(
    *,
    cutoff: datetime | None = None,
    team_ids: set[str] | None = None,
    lookback_games: int = 20,
) -> dict[str, TeamRolePrior]:
    with session_scope() as session:
        teams = session.query(Team).all()
        selected_teams = [team for team in teams if not team_ids or str(team.team_id) in team_ids]
        priors: dict[str, TeamRolePrior] = {}
        cache: dict[tuple[str, str], TeamRolePrior | None] = {}
        for team in selected_teams:
            prior = load_team_role_prior(
                session,
                team_id=str(team.team_id),
                team_abbreviation=team.abbreviation,
                cutoff=cutoff,
                cache=cache,
                lookback_games=lookback_games,
            )
            if prior is not None:
                priors[prior.team_id] = prior
        return priors


def _build_role_based_official_injury_context(
    team_rows: list[dict[str, Any]] | None,
    team_role_prior: TeamRolePrior | None,
    *,
    player_id: str | None,
) -> dict[str, Any]:
    base = {
        "teammate_out_count_top7": None,
        "teammate_out_count_top9": None,
        "missing_high_usage_teammates": None,
        "missing_primary_ballhandler": None,
        "missing_frontcourt_rotation_piece": None,
        "vacated_minutes_proxy": None,
        "vacated_usage_proxy": None,
        "role_replacement_minutes_proxy": None,
        "role_replacement_usage_proxy": None,
        "role_replacement_touches_proxy": None,
        "role_replacement_passes_proxy": None,
    }
    if not team_rows or team_role_prior is None:
        return base

    severity_by_status = {
        "OUT": 1.0,
        "SUSPENDED": 1.0,
        "DOUBTFUL": 0.7,
        "QUESTIONABLE": 0.35,
        "PROBABLE": 0.1,
    }
    teammate_out_count_top7 = 0.0
    teammate_out_count_top9 = 0.0
    missing_high_usage_teammates = 0.0
    missing_primary_ballhandler = False
    missing_frontcourt_rotation_piece = False
    vacated_minutes_proxy = 0.0
    vacated_usage_proxy = 0.0
    role_replacement_minutes_proxy = 0.0
    role_replacement_usage_proxy = 0.0
    role_replacement_touches_proxy = 0.0
    role_replacement_passes_proxy = 0.0
    saw_role_signal = False

    target_profile = team_role_prior.player_role_profiles.get(str(player_id)) if player_id is not None else None

    for row in team_rows:
        teammate_id = row.get("player_id")
        if player_id and teammate_id is not None and str(teammate_id) == str(player_id):
            continue
        status = str(row.get("current_status") or "").upper()
        severity = severity_by_status.get(status)
        if severity is None or teammate_id in (None, ""):
            continue

        teammate_key = str(teammate_id)
        if teammate_key in team_role_prior.top7_player_ids:
            teammate_out_count_top7 += severity
            saw_role_signal = True
        if teammate_key in team_role_prior.top9_player_ids:
            teammate_out_count_top9 += severity
            saw_role_signal = True
        if teammate_key in team_role_prior.high_usage_player_ids:
            missing_high_usage_teammates += severity
            saw_role_signal = True
        if teammate_key in team_role_prior.primary_ballhandler_ids and severity >= 0.35:
            missing_primary_ballhandler = True
            saw_role_signal = True
        if teammate_key in team_role_prior.frontcourt_player_ids and severity >= 0.35:
            missing_frontcourt_rotation_piece = True
            saw_role_signal = True

        missing_profile = team_role_prior.player_role_profiles.get(teammate_key)
        if target_profile is not None and missing_profile is not None:
            replacement_fit = _player_role_similarity(target_profile, missing_profile)
            role_replacement_minutes_proxy += missing_profile.baseline_minutes * severity * replacement_fit
            role_replacement_usage_proxy += missing_profile.baseline_usage * severity * replacement_fit
            role_replacement_touches_proxy += missing_profile.baseline_touches * severity * replacement_fit
            role_replacement_passes_proxy += missing_profile.baseline_passes * severity * replacement_fit

        vacated_minutes_proxy += team_role_prior.baseline_minutes_by_player_id.get(teammate_key, 0.0) * severity
        vacated_usage_proxy += team_role_prior.baseline_usage_by_player_id.get(teammate_key, 0.0) * severity

    if (
        not saw_role_signal
        and vacated_minutes_proxy <= 0.0
        and vacated_usage_proxy <= 0.0
        and role_replacement_minutes_proxy <= 0.0
    ):
        return base

    return {
        "teammate_out_count_top7": round(teammate_out_count_top7, 4),
        "teammate_out_count_top9": round(teammate_out_count_top9, 4),
        "missing_high_usage_teammates": round(missing_high_usage_teammates, 4),
        "missing_primary_ballhandler": missing_primary_ballhandler,
        "missing_frontcourt_rotation_piece": missing_frontcourt_rotation_piece if missing_frontcourt_rotation_piece else None,
        "vacated_minutes_proxy": round(vacated_minutes_proxy, 4) if vacated_minutes_proxy > 0.0 else None,
        "vacated_usage_proxy": round(vacated_usage_proxy, 4) if vacated_usage_proxy > 0.0 else None,
        "role_replacement_minutes_proxy": round(role_replacement_minutes_proxy, 4) if role_replacement_minutes_proxy > 0.0 else None,
        "role_replacement_usage_proxy": round(role_replacement_usage_proxy, 4) if role_replacement_usage_proxy > 0.0 else None,
        "role_replacement_touches_proxy": round(role_replacement_touches_proxy, 4) if role_replacement_touches_proxy > 0.0 else None,
        "role_replacement_passes_proxy": round(role_replacement_passes_proxy, 4) if role_replacement_passes_proxy > 0.0 else None,
    }


def _select_newer_absence_impact_row(
    current: AbsenceImpactSummary | None,
    candidate: AbsenceImpactSummary,
) -> AbsenceImpactSummary:
    if current is None:
        return candidate

    current_end = current.window_end_date or date.min
    candidate_end = candidate.window_end_date or date.min
    if candidate_end != current_end:
        return candidate if candidate_end > current_end else current

    current_confidence = float(current.sample_confidence or 0.0)
    candidate_confidence = float(candidate.sample_confidence or 0.0)
    if candidate_confidence != current_confidence:
        return candidate if candidate_confidence > current_confidence else current

    current_updated = current.updated_at or current.created_at or datetime.min
    candidate_updated = candidate.updated_at or candidate.created_at or datetime.min
    return candidate if candidate_updated >= current_updated else current



def _build_absence_impact_index(rows: list[AbsenceImpactSummary]) -> AbsenceImpactIndex:
    by_id: dict[tuple[str, str, str], AbsenceImpactSummary] = {}
    by_name: dict[tuple[str, str, str], AbsenceImpactSummary] = {}

    for row in rows:
        team_abbreviation = str(row.team_abbreviation or "").upper()
        beneficiary_player_id = str(row.beneficiary_player_id or "")
        source_player_id = str(row.source_player_id or "")
        if not team_abbreviation or not beneficiary_player_id or not source_player_id:
            continue

        id_key = (team_abbreviation, beneficiary_player_id, source_player_id)
        by_id[id_key] = _select_newer_absence_impact_row(by_id.get(id_key), row)

        normalized_source_name = normalize_name(row.source_player_name or "")
        if normalized_source_name:
            name_key = (team_abbreviation, beneficiary_player_id, normalized_source_name)
            by_name[name_key] = _select_newer_absence_impact_row(by_name.get(name_key), row)

    return AbsenceImpactIndex(
        by_team_beneficiary_source_id=by_id,
        by_team_beneficiary_source_name=by_name,
    )



def _build_absence_impact_context(
    *,
    team_rows: list[dict[str, Any]] | None,
    absence_impact_index: AbsenceImpactIndex | None,
    team_abbreviation: str | None,
    player_id: str | None,
) -> dict[str, Any]:
    base = {
        "absence_impact_minutes_delta": None,
        "absence_impact_usage_delta": None,
        "absence_impact_touches_delta": None,
        "absence_impact_passes_delta": None,
        "absence_impact_sample_confidence": None,
        "absence_impact_source_count": None,
    }
    if not team_rows or absence_impact_index is None or not team_abbreviation or not player_id:
        return base

    matched_summaries: list[AbsenceImpactSummary] = []
    seen_source_keys: set[tuple[str, str]] = set()
    for teammate_row in team_rows:
        status = str(teammate_row.get("current_status") or "").upper()
        if status not in {"OUT", "SUSPENDED"}:
            continue
        source_player_id = teammate_row.get("player_id")
        source_player_name = teammate_row.get("player_name")
        if source_player_id not in (None, "") and str(source_player_id) == str(player_id):
            continue

        summary = None
        if source_player_id not in (None, ""):
            summary = absence_impact_index.by_team_beneficiary_source_id.get(
                (str(team_abbreviation).upper(), str(player_id), str(source_player_id))
            )
        if summary is None:
            normalized_source_name = normalize_name(source_player_name or "")
            if normalized_source_name:
                summary = absence_impact_index.by_team_beneficiary_source_name.get(
                    (str(team_abbreviation).upper(), str(player_id), normalized_source_name)
                )
        if summary is None:
            continue

        source_key = (str(summary.source_player_id), str(summary.source_player_name or ""))
        if source_key in seen_source_keys:
            continue
        seen_source_keys.add(source_key)
        matched_summaries.append(summary)

    if not matched_summaries:
        return base

    matched_summaries.sort(
        key=lambda row: (
            float(row.sample_confidence or 0.0),
            float(row.impact_score or 0.0),
            row.window_end_date or date.min,
        ),
        reverse=True,
    )

    minutes_delta = 0.0
    usage_delta = 0.0
    touches_delta = 0.0
    passes_delta = 0.0
    best_confidence = 0.0
    source_count = 0
    for summary in matched_summaries[:3]:
        sample_confidence = float(summary.sample_confidence or 0.0)
        if sample_confidence < 0.18 or int(summary.source_out_game_count or 0) < 2:
            continue
        weight = min(sample_confidence, 1.0)
        minutes_delta += float(summary.minutes_delta or 0.0) * weight
        usage_delta += float(summary.usage_delta or 0.0) * weight
        touches_delta += float(summary.touches_delta or 0.0) * weight
        passes_delta += float(summary.passes_delta or 0.0) * weight
        best_confidence = max(best_confidence, sample_confidence)
        source_count += 1

    if source_count == 0:
        return base

    return {
        "absence_impact_minutes_delta": round(minutes_delta, 4) if abs(minutes_delta) > 0.0001 else None,
        "absence_impact_usage_delta": round(usage_delta, 4) if abs(usage_delta) > 0.0001 else None,
        "absence_impact_touches_delta": round(touches_delta, 4) if abs(touches_delta) > 0.0001 else None,
        "absence_impact_passes_delta": round(passes_delta, 4) if abs(passes_delta) > 0.0001 else None,
        "absence_impact_sample_confidence": round(best_confidence, 4) if best_confidence > 0.0 else None,
        "absence_impact_source_count": float(source_count),
    }



def _build_official_injury_aggregates(
    row: dict[str, Any] | None,
    team_summary: dict[str, Any] | None,
    *,
    team_rows: list[dict[str, Any]] | None = None,
    team_role_prior: TeamRolePrior | None = None,
    player_id: str | None = None,
    team_abbreviation: str | None = None,
    absence_impact_index: AbsenceImpactIndex | None = None,
    captured_at: datetime,
) -> dict[str, Any]:
    base = {
        "official_injury_status": None,
        "official_injury_reason": None,
        "official_report_datetime_utc": None,
        "official_teammate_out_count": None,
        "official_teammate_doubtful_count": None,
        "official_teammate_questionable_count": None,
        "official_available": None,
        "late_scratch_risk": None,
        "teammate_out_count_top7": None,
        "teammate_out_count_top9": None,
        "missing_high_usage_teammates": None,
        "missing_primary_ballhandler": None,
        "missing_frontcourt_rotation_piece": None,
        "vacated_minutes_proxy": None,
        "vacated_usage_proxy": None,
        "role_replacement_minutes_proxy": None,
        "role_replacement_usage_proxy": None,
        "role_replacement_touches_proxy": None,
        "role_replacement_passes_proxy": None,
        "absence_impact_minutes_delta": None,
        "absence_impact_usage_delta": None,
        "absence_impact_touches_delta": None,
        "absence_impact_passes_delta": None,
        "absence_impact_sample_confidence": None,
        "absence_impact_source_count": None,
        "pregame_context_confidence": None,
    }
    if row is None and team_summary is None and not team_rows:
        return base

    report_datetime = None
    if row is not None:
        report_datetime = row.get("report_datetime_utc")
    if report_datetime is None and team_summary is not None:
        report_datetime = team_summary.get("report_datetime_utc")
    if report_datetime is None and team_rows:
        report_datetime = max(
            [candidate.get("report_datetime_utc") for candidate in team_rows if candidate.get("report_datetime_utc") is not None],
            default=None,
        )

    confidence = None
    if isinstance(report_datetime, datetime):
        age_hours = max((captured_at - report_datetime).total_seconds() / 3600.0, 0.0)
        confidence = max(0.35, min(0.92, 0.92 - 0.06 * age_hours))
    elif row is not None or team_summary is not None or team_rows:
        confidence = 0.5

    if team_summary is not None:
        base["official_teammate_out_count"] = float(team_summary.get("out_count") or 0.0)
        base["official_teammate_doubtful_count"] = float(team_summary.get("doubtful_count") or 0.0)
        base["official_teammate_questionable_count"] = float(team_summary.get("questionable_count") or 0.0)

    role_context = _build_role_based_official_injury_context(team_rows, team_role_prior, player_id=player_id)
    absence_impact_context = _build_absence_impact_context(
        team_rows=team_rows,
        absence_impact_index=absence_impact_index,
        team_abbreviation=team_abbreviation,
        player_id=player_id,
    )
    base.update(role_context)
    base.update(absence_impact_context)

    if row is None:
        base["official_report_datetime_utc"] = report_datetime
        if confidence is None:
            base["pregame_context_confidence"] = 0.25 if team_summary is not None else None
        elif (
            role_context.get("vacated_minutes_proxy") is not None
            or role_context.get("role_replacement_minutes_proxy") is not None
            or role_context.get("missing_primary_ballhandler")
            or role_context.get("missing_frontcourt_rotation_piece")
        ):
            base["pregame_context_confidence"] = min(float(confidence), 0.65)
        else:
            base["pregame_context_confidence"] = min(float(confidence), 0.25)
        return base

    status = str(row.get("current_status") or "").upper()
    base["official_injury_status"] = status or None
    base["official_injury_reason"] = row.get("reason")
    base["official_report_datetime_utc"] = report_datetime
    base["pregame_context_confidence"] = confidence

    if status in {"OUT", "SUSPENDED"}:
        base["official_available"] = False
        base["late_scratch_risk"] = 1.0
    elif status == "AVAILABLE":
        base["official_available"] = True
        base["late_scratch_risk"] = 0.0
    elif status == "PROBABLE":
        base["official_available"] = True
        base["late_scratch_risk"] = 0.15
    elif status == "QUESTIONABLE":
        base["late_scratch_risk"] = 0.65
    elif status == "DOUBTFUL":
        base["late_scratch_risk"] = 0.85

    if status == "NOT_YET_SUBMITTED" and confidence is not None:
        base["pregame_context_confidence"] = min(confidence, 0.35)

    return base


def _has_official_injury_context(
    *,
    official_injury_row: dict[str, Any] | None,
    official_injury_team_summary: dict[str, Any] | None,
    official_injury_team_rows: list[dict[str, Any]] | None,
) -> bool:
    return official_injury_row is not None or official_injury_team_summary is not None or bool(official_injury_team_rows)


def _resolve_context_source(
    *,
    pregame_context_row: dict[str, Any] | None,
    official_injury_attached: bool,
    official_injury_row: dict[str, Any] | None,
) -> str:
    if pregame_context_row is not None:
        return "pregame_context"
    if official_injury_row is not None:
        return "official_injury_player"
    if official_injury_attached:
        return "official_injury_team"
    return "none"


def _apply_context_source_confidence_cap(aggregates: dict[str, Any], *, context_source: str) -> dict[str, Any]:
    confidence = aggregates.get("pregame_context_confidence")
    if confidence is None:
        return aggregates

    capped = dict(aggregates)
    if context_source == "official_injury_player":
        capped["pregame_context_confidence"] = min(float(confidence), 0.55)
    elif context_source == "official_injury_team":
        capped["pregame_context_confidence"] = min(float(confidence), 0.35)
    return capped


def _merge_context_aggregates(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = dict(fallback)
    merged.update(
        {
            key: value
            for key, value in primary.items()
            if key not in {"late_scratch_risk", "pregame_context_confidence", "teammate_out_count_top7", "teammate_out_count_top9"}
            and value is not None
        }
    )

    for key in (
        "official_available",
        "projected_available",
        "expected_start",
        "starter_confidence",
        "missing_high_usage_teammates",
        "missing_primary_ballhandler",
        "missing_frontcourt_rotation_piece",
        "vacated_minutes_proxy",
        "vacated_usage_proxy",
        "role_replacement_minutes_proxy",
        "role_replacement_usage_proxy",
        "role_replacement_touches_proxy",
        "role_replacement_passes_proxy",
        "absence_impact_minutes_delta",
        "absence_impact_usage_delta",
        "absence_impact_touches_delta",
        "absence_impact_passes_delta",
        "absence_impact_sample_confidence",
        "absence_impact_source_count",
        "projected_lineup_confirmed",
        "official_starter_flag",
    ):
        primary_value = primary.get(key)
        if primary_value is not None:
            merged[key] = primary_value

    primary_late = primary.get("late_scratch_risk")
    fallback_late = fallback.get("late_scratch_risk")
    if primary_late is None:
        merged["late_scratch_risk"] = fallback_late
    elif fallback_late is None:
        merged["late_scratch_risk"] = primary_late
    else:
        merged["late_scratch_risk"] = max(float(primary_late), float(fallback_late))

    primary_confidence = primary.get("pregame_context_confidence")
    fallback_confidence = fallback.get("pregame_context_confidence")
    if primary_confidence is None:
        merged["pregame_context_confidence"] = fallback_confidence
    elif fallback_confidence is None:
        merged["pregame_context_confidence"] = primary_confidence
    else:
        merged["pregame_context_confidence"] = max(float(primary_confidence), float(fallback_confidence))

    for key in ("teammate_out_count_top7", "teammate_out_count_top9"):
        primary_value = primary.get(key)
        fallback_value = fallback.get(key)
        if primary_value is None:
            merged[key] = fallback_value
        elif fallback_value is None:
            merged[key] = primary_value
        else:
            merged[key] = max(float(primary_value), float(fallback_value))

    if fallback.get("official_available") is False:
        merged["official_available"] = False
        merged["projected_available"] = False
        merged["expected_start"] = False
        merged["starter_confidence"] = 0.0
        merged["official_starter_flag"] = False

    return merged


def _build_pregame_context_aggregates(row: dict[str, Any] | None) -> dict[str, float | bool | None]:
    if row is None:
        return {
            "expected_start": None,
            "starter_confidence": None,
            "official_available": None,
            "projected_available": None,
            "late_scratch_risk": None,
            "teammate_out_count_top7": None,
            "teammate_out_count_top9": None,
            "missing_high_usage_teammates": None,
            "missing_primary_ballhandler": None,
            "missing_frontcourt_rotation_piece": None,
            "vacated_minutes_proxy": None,
            "vacated_usage_proxy": None,
            "role_replacement_minutes_proxy": None,
            "role_replacement_usage_proxy": None,
            "role_replacement_touches_proxy": None,
            "role_replacement_passes_proxy": None,
            "absence_impact_minutes_delta": None,
            "absence_impact_usage_delta": None,
            "absence_impact_touches_delta": None,
            "absence_impact_passes_delta": None,
            "absence_impact_sample_confidence": None,
            "absence_impact_source_count": None,
            "projected_lineup_confirmed": None,
            "official_starter_flag": None,
            "pregame_context_confidence": None,
        }

    return {
        "expected_start": bool(row.get("expected_start")) if row.get("expected_start") is not None else None,
        "starter_confidence": float(row.get("starter_confidence")) if row.get("starter_confidence") is not None else None,
        "official_available": bool(row.get("official_available")) if row.get("official_available") is not None else None,
        "projected_available": bool(row.get("projected_available")) if row.get("projected_available") is not None else None,
        "late_scratch_risk": float(row.get("late_scratch_risk")) if row.get("late_scratch_risk") is not None else None,
        "teammate_out_count_top7": float(row.get("teammate_out_count_top7")) if row.get("teammate_out_count_top7") is not None else None,
        "teammate_out_count_top9": float(row.get("teammate_out_count_top9")) if row.get("teammate_out_count_top9") is not None else None,
        "missing_high_usage_teammates": float(row.get("missing_high_usage_teammates")) if row.get("missing_high_usage_teammates") is not None else None,
        "missing_primary_ballhandler": bool(row.get("missing_primary_ballhandler")) if row.get("missing_primary_ballhandler") is not None else None,
        "missing_frontcourt_rotation_piece": bool(row.get("missing_frontcourt_rotation_piece")) if row.get("missing_frontcourt_rotation_piece") is not None else None,
        "vacated_minutes_proxy": float(row.get("vacated_minutes_proxy")) if row.get("vacated_minutes_proxy") is not None else None,
        "vacated_usage_proxy": float(row.get("vacated_usage_proxy")) if row.get("vacated_usage_proxy") is not None else None,
        "role_replacement_minutes_proxy": float(row.get("role_replacement_minutes_proxy")) if row.get("role_replacement_minutes_proxy") is not None else None,
        "role_replacement_usage_proxy": float(row.get("role_replacement_usage_proxy")) if row.get("role_replacement_usage_proxy") is not None else None,
        "role_replacement_touches_proxy": float(row.get("role_replacement_touches_proxy")) if row.get("role_replacement_touches_proxy") is not None else None,
        "role_replacement_passes_proxy": float(row.get("role_replacement_passes_proxy")) if row.get("role_replacement_passes_proxy") is not None else None,
        "absence_impact_minutes_delta": float(row.get("absence_impact_minutes_delta")) if row.get("absence_impact_minutes_delta") is not None else None,
        "absence_impact_usage_delta": float(row.get("absence_impact_usage_delta")) if row.get("absence_impact_usage_delta") is not None else None,
        "absence_impact_touches_delta": float(row.get("absence_impact_touches_delta")) if row.get("absence_impact_touches_delta") is not None else None,
        "absence_impact_passes_delta": float(row.get("absence_impact_passes_delta")) if row.get("absence_impact_passes_delta") is not None else None,
        "absence_impact_sample_confidence": float(row.get("absence_impact_sample_confidence")) if row.get("absence_impact_sample_confidence") is not None else None,
        "absence_impact_source_count": float(row.get("absence_impact_source_count")) if row.get("absence_impact_source_count") is not None else None,
        "projected_lineup_confirmed": bool(row.get("projected_lineup_confirmed")) if row.get("projected_lineup_confirmed") is not None else None,
        "official_starter_flag": bool(row.get("official_starter_flag")) if row.get("official_starter_flag") is not None else None,
        "pregame_context_confidence": float(row.get("pregame_context_confidence")) if row.get("pregame_context_confidence") is not None else None,
    }


def _load_recent_player_logs(
    session: Session,
    *,
    player_id: str,
    cutoff: datetime | None,
    history_limit: int,
    logs_by_player: dict[str, list[HistoricalGameLog]] | None = None,
) -> list[HistoricalGameLog]:
    if logs_by_player is not None:
        candidate_logs = _sort_logs_desc(logs_by_player.get(player_id, []))
        if cutoff is not None:
            candidate_logs = [log for log in candidate_logs if log.game_date < cutoff]
        return candidate_logs[:history_limit]

    query = session.query(HistoricalGameLog).filter(HistoricalGameLog.player_id == player_id)
    if cutoff is not None:
        query = query.filter(HistoricalGameLog.game_date < cutoff)
    return (
        query.order_by(HistoricalGameLog.game_date.desc(), HistoricalGameLog.game_id.desc())
        .limit(history_limit)
        .all()
    )


def _load_player_advanced_rows(
    session: Session,
    *,
    player_id: str,
    recent_logs: list[HistoricalGameLog],
    advanced_by_player_game: dict[tuple[str, str], HistoricalAdvancedLog] | None = None,
) -> list[HistoricalAdvancedLog]:
    game_ids = [log.game_id for log in recent_logs]
    if not game_ids:
        return []
    if advanced_by_player_game is not None:
        return [advanced_by_player_game[(player_id, log.game_id)] for log in recent_logs if (player_id, log.game_id) in advanced_by_player_game]

    advanced_by_game = {
        row.game_id: row
        for row in session.query(HistoricalAdvancedLog)
        .filter(HistoricalAdvancedLog.player_id == player_id, HistoricalAdvancedLog.game_id.in_(game_ids))
        .all()
    }
    return [advanced_by_game[log.game_id] for log in recent_logs if log.game_id in advanced_by_game]


def _load_player_rotation_rows(
    session: Session,
    *,
    player_id: str,
    recent_logs: list[HistoricalGameLog],
    rotation_by_player_game: dict[tuple[str, str], PlayerRotationGame] | None = None,
) -> list[PlayerRotationGame]:
    game_ids = [log.game_id for log in recent_logs]
    if not game_ids:
        return []
    if rotation_by_player_game is not None:
        return [rotation_by_player_game[(player_id, log.game_id)] for log in recent_logs if (player_id, log.game_id) in rotation_by_player_game]

    rotation_by_game = {
        row.game_id: row
        for row in session.query(PlayerRotationGame)
        .filter(PlayerRotationGame.player_id == player_id, PlayerRotationGame.game_id.in_(game_ids))
        .all()
    }
    return [rotation_by_game[log.game_id] for log in recent_logs if log.game_id in rotation_by_game]


def build_pregame_feature_seed(
    session: Session,
    request: PregameFeatureRequest,
    *,
    games_by_id: dict[str, Game] | None = None,
    team_id_by_abbreviation: dict[str, str] | None = None,
    defense_by_season_team: dict[tuple[str, str], TeamDefensiveStat] | None = None,
    league_avg_def_rating_by_season: dict[str, float | None] | None = None,
    league_avg_pace_by_season: dict[str, float | None] | None = None,
    league_avg_opponent_points_by_season: dict[str, float | None] | None = None,
    pregame_context_index: PregameContextIndex | None = None,
    official_injury_index: OfficialInjuryReportIndex | None = None,
    absence_impact_index: AbsenceImpactIndex | None = None,
    team_role_prior_cache: dict[tuple[str, str], TeamRolePrior | None] | None = None,
    logs_by_player: dict[str, list[HistoricalGameLog]] | None = None,
    advanced_by_player_game: dict[tuple[str, str], HistoricalAdvancedLog] | None = None,
    rotation_by_player_game: dict[tuple[str, str], PlayerRotationGame] | None = None,
    logs_by_team: dict[str, list[HistoricalGameLog]] | None = None,
    rotation_by_team_game_player: dict[tuple[str, str, str], PlayerRotationGame] | None = None,
    history_limit: int = 15,
) -> PregameFeatureSeed | None:
    game = games_by_id.get(request.game_id) if games_by_id is not None else session.get(Game, request.game_id)
    cutoff = request.game_date or (game.game_time_utc if game and game.game_time_utc else None) or (game.game_date if game else None) or request.captured_at

    recent_logs = _load_recent_player_logs(
        session,
        player_id=request.player_id,
        cutoff=cutoff,
        history_limit=history_limit,
        logs_by_player=logs_by_player,
    )
    if not recent_logs:
        return None

    latest_log = recent_logs[0]
    team_abbreviation, opponent_abbreviation, is_home = _resolve_team_context(
        request.team_abbreviation or latest_log.team,
        request.opponent_abbreviation or latest_log.opponent,
        game,
        latest_log,
        request.is_home,
    )

    advanced_rows = _load_player_advanced_rows(
        session,
        player_id=request.player_id,
        recent_logs=recent_logs,
        advanced_by_player_game=advanced_by_player_game,
    )
    rotation_rows = _load_player_rotation_rows(
        session,
        player_id=request.player_id,
        recent_logs=recent_logs,
        rotation_by_player_game=rotation_by_player_game,
    )

    days_rest = None
    if latest_log.game_date is not None and cutoff is not None:
        days_rest = max((cutoff.date() - latest_log.game_date.date()).days, 0)

    season = (game.season if game and game.season else None) or _season_from_game_date(cutoff)
    team_team_id = team_id_by_abbreviation.get(team_abbreviation or "") if team_id_by_abbreviation else None
    opponent_team_id = team_id_by_abbreviation.get(opponent_abbreviation or "") if team_id_by_abbreviation else None
    team_defense = defense_by_season_team.get((season, team_team_id)) if defense_by_season_team and season and team_team_id else None
    opponent_defense = defense_by_season_team.get((season, opponent_team_id)) if defense_by_season_team and season and opponent_team_id else None

    report_game_date = cutoff.date() if isinstance(cutoff, datetime) else None
    pregame_context_row = None
    if pregame_context_index is not None:
        pregame_context_row = match_pregame_context_row(
            pregame_context_index,
            game_id=request.game_id,
            player_id=request.player_id,
            team_abbreviation=team_abbreviation,
            player_name=request.player_name,
            captured_at=request.captured_at,
        )

    official_injury_row = None
    official_injury_team_summary = None
    official_injury_team_rows: list[dict[str, Any]] | None = None
    if official_injury_index is not None:
        official_injury_row = match_official_injury_row(
            official_injury_index,
            game_date=report_game_date,
            player_id=request.player_id,
            team_abbreviation=team_abbreviation,
            player_name=request.player_name,
        )
        official_injury_team_summary = get_official_team_summary(
            official_injury_index,
            game_date=report_game_date,
            team_abbreviation=team_abbreviation,
        )
        official_injury_team_rows = get_official_team_rows(
            official_injury_index,
            game_date=report_game_date,
            team_abbreviation=team_abbreviation,
        )

    team_role_prior = load_team_role_prior(
        session,
        team_id=team_team_id,
        team_abbreviation=team_abbreviation,
        cutoff=cutoff,
        cache=team_role_prior_cache,
        logs_by_team=logs_by_team,
        advanced_by_player_game=advanced_by_player_game,
        rotation_by_team_game_player=rotation_by_team_game_player,
    )

    return PregameFeatureSeed(
        game_id=request.game_id,
        player_id=request.player_id,
        player_name=request.player_name,
        stat_type=request.stat_type,
        line=float(request.line),
        over_odds=int(request.over_odds),
        under_odds=int(request.under_odds),
        captured_at=request.captured_at,
        game_date=cutoff,
        team_abbreviation=team_abbreviation,
        opponent_abbreviation=opponent_abbreviation,
        is_home=is_home,
        days_rest=days_rest,
        back_to_back=days_rest == 1 if days_rest is not None else None,
        recent_logs=recent_logs,
        advanced_rows=advanced_rows,
        rotation_rows=rotation_rows,
        team_defense=team_defense,
        opponent_defense=opponent_defense,
        league_avg_def_rating=league_avg_def_rating_by_season.get(season) if league_avg_def_rating_by_season and season else None,
        league_avg_pace=league_avg_pace_by_season.get(season) if league_avg_pace_by_season and season else None,
        league_avg_opponent_points=league_avg_opponent_points_by_season.get(season) if league_avg_opponent_points_by_season and season else None,
        pregame_context_row=pregame_context_row,
        official_injury_row=official_injury_row,
        official_injury_team_summary=official_injury_team_summary,
        official_injury_team_rows=official_injury_team_rows,
        absence_impact_index=absence_impact_index,
        team_role_prior=team_role_prior,
    )


def load_pregame_feature_seeds(
    captured_at: datetime | None = None,
    stat_type: str = "points",
    limit: int | None = None,
) -> list[PregameFeatureSeed]:
    with session_scope() as session:
        latest_captured_at = captured_at
        if latest_captured_at is None:
            latest_captured_at = (
                session.query(PlayerPropSnapshot.captured_at)
                .filter(PlayerPropSnapshot.stat_type == stat_type, PlayerPropSnapshot.is_live.is_(False))
                .order_by(PlayerPropSnapshot.captured_at.desc())
                .limit(1)
                .scalar()
            )

        if latest_captured_at is None:
            return []

        market_query = (
            session.query(PlayerPropSnapshot)
            .filter(
                PlayerPropSnapshot.stat_type == stat_type,
                PlayerPropSnapshot.is_live.is_(False),
                PlayerPropSnapshot.captured_at == latest_captured_at,
            )
            .order_by(PlayerPropSnapshot.game_id, PlayerPropSnapshot.player_name)
        )
        if limit is not None:
            market_query = market_query.limit(limit)
        markets = market_query.all()
        if not markets:
            return []

        game_ids = [market.game_id for market in markets]
        games_by_id = {
            game.game_id: game
            for game in session.query(Game)
            .filter(Game.game_id.in_(game_ids))
            .all()
        }
        teams = session.query(Team).all()
        team_id_by_abbreviation = {team.abbreviation: team.team_id for team in teams if team.abbreviation}

        defense_by_season_team, league_avg_def_rating_by_season, league_avg_pace_by_season, league_avg_opponent_points_by_season = _build_defense_context(
            session.query(TeamDefensiveStat).all()
        )

        pregame_rows = load_pregame_context_snapshot_rows(session, game_ids=game_ids, captured_at=latest_captured_at)
        if not pregame_rows:
            pregame_rows = load_pregame_context_feature_rows()
        pregame_context_index = build_pregame_context_index(pregame_rows)

        official_injury_dates = sorted(
            {
                (game.game_time_utc if game and game.game_time_utc else game.game_date if game else latest_captured_at).date()
                for game in games_by_id.values()
                if (game.game_time_utc if game and game.game_time_utc else game.game_date if game else latest_captured_at) is not None
            }
            | {latest_captured_at.date()}
        )
        official_injury_index = build_official_injury_report_index(
            load_latest_official_injury_report_rows(
                session,
                report_dates=official_injury_dates,
                captured_at=latest_captured_at,
            )
        )
        absence_impact_index = _build_absence_impact_index(session.query(AbsenceImpactSummary).all())
        team_role_prior_cache: dict[tuple[str, str], TeamRolePrior | None] = {}

        seeds: list[PregameFeatureSeed] = []
        for market in markets:
            seed = build_pregame_feature_seed(
                session,
                PregameFeatureRequest(
                    game_id=market.game_id,
                    player_id=market.player_id,
                    player_name=market.player_name,
                    stat_type=market.stat_type,
                    captured_at=market.captured_at,
                    line=float(market.line),
                    over_odds=int(market.over_odds),
                    under_odds=int(market.under_odds),
                    team_abbreviation=market.team,
                    opponent_abbreviation=market.opponent,
                ),
                games_by_id=games_by_id,
                team_id_by_abbreviation=team_id_by_abbreviation,
                defense_by_season_team=defense_by_season_team,
                league_avg_def_rating_by_season=league_avg_def_rating_by_season,
                league_avg_pace_by_season=league_avg_pace_by_season,
                league_avg_opponent_points_by_season=league_avg_opponent_points_by_season,
                pregame_context_index=pregame_context_index,
                official_injury_index=official_injury_index,
                absence_impact_index=absence_impact_index,
                team_role_prior_cache=team_role_prior_cache,
            )
            if seed is not None:
                seeds.append(seed)

    return seeds


def build_pregame_opportunity_features(
    captured_at: datetime | None = None,
    stat_type: str = "points",
    limit: int | None = None,
) -> list[PregameOpportunityFeatures]:
    seeds = load_pregame_feature_seeds(captured_at=captured_at, stat_type=stat_type, limit=limit)
    return [seed.build_opportunity_features() for seed in seeds]
