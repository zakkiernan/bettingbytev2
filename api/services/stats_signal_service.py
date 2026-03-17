from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
import json
from statistics import NormalDist
from typing import Literal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from analytics.features_pregame import PregamePointsFeatures, build_pregame_points_features
from api.schemas.board import PropBoardMeta, PropBoardResponse, PropBoardRow, SignalReadiness
from api.schemas.detail import FeatureSnapshot, GameLogEntry, InjuryEntry, OpportunityContext, PointsBreakdown, PropDetailResponse
from api.schemas.edges import EdgeResponse
from api.schemas.health import SignalRunHealth
from api.schemas.players import SignalHistoryEntry
from database.db import session_scope
from database.models import (
    Game,
    HistoricalGameLog,
    OddsSnapshot,
    OfficialInjuryReport,
    OfficialInjuryReportEntry,
    PlayerPropSnapshot,
    StatsSignalSnapshot,
)

POINTS_STAT_TYPE = "points"
CURRENT_SNAPSHOT_PHASE = "current"
MIN_EDGE_TO_RECOMMEND = 1.5
MIN_CONFIDENCE_TO_RECOMMEND = 0.55
MIN_PROBABILITY_TO_RECOMMEND = 0.56
MAX_RECENT_LOGS = 10
MIN_RECENT_GAMES_FOR_RECOMMENDATION = 5
MAX_SIGNAL_CAPTURE_AGE_MINUTES = 90
INJURY_REPORT_REQUIRED_WINDOW_MINUTES = 240
LOW_CONTEXT_CONFIDENCE_THRESHOLD = 0.45

_RECENT_POINT_WEIGHTS: tuple[tuple[float, str], ...] = (
    (0.42, "season_points_avg"),
    (0.33, "last10_points_avg"),
    (0.25, "last5_points_avg"),
)
_MINUTES_WEIGHTS: tuple[tuple[float, str], ...] = (
    (0.50, "season_minutes_avg"),
    (0.30, "last10_minutes_avg"),
    (0.20, "last5_minutes_avg"),
)
_ROTATION_MINUTES_WEIGHTS: tuple[tuple[float, str], ...] = (
    (0.40, "season_rotation_minutes_avg"),
    (0.35, "last10_rotation_minutes_avg"),
    (0.25, "last5_rotation_minutes_avg"),
)
_USAGE_WEIGHTS: tuple[tuple[float, str], ...] = (
    (0.45, "season_usage_pct"),
    (0.35, "last10_usage_pct"),
    (0.20, "last5_usage_pct"),
)
_TOUCHES_WEIGHTS: tuple[tuple[float, str], ...] = (
    (0.45, "season_touches"),
    (0.35, "last10_touches"),
    (0.20, "last5_touches"),
)
_START_RATE_WEIGHTS: tuple[tuple[float, str], ...] = (
    (0.35, "season_started_rate"),
    (0.35, "last10_started_rate"),
    (0.30, "last5_started_rate"),
)
_CLOSE_RATE_WEIGHTS: tuple[tuple[float, str], ...] = (
    (0.35, "season_closed_rate"),
    (0.35, "last10_closed_rate"),
    (0.30, "last5_closed_rate"),
)
_INJURY_STATUS_LABELS = {
    "OUT": "Out",
    "DOUBTFUL": "Doubtful",
    "QUESTIONABLE": "Questionable",
    "PROBABLE": "Probable",
}


@dataclass(slots=True)
class StatsSignalProfile:
    projected_value: float
    edge_over: float
    edge_under: float
    over_probability: float
    under_probability: float
    confidence: float
    recommended_side: Literal["OVER", "UNDER"] | None
    recent_hit_rate: float | None
    recent_games_count: int
    key_factor: str | None
    breakdown: PointsBreakdown
    opportunity: OpportunityContext
    feature_snapshot: FeatureSnapshot
    readiness: SignalReadiness = field(default_factory=SignalReadiness)
    source_context_captured_at: datetime | None = None
    source_injury_report_at: datetime | None = None


@dataclass(slots=True)
class StatsSignalCard:
    snapshot: PlayerPropSnapshot
    game: Game | None
    profile: StatsSignalProfile
    recent_logs: list[HistoricalGameLog]

    def to_board_row(self) -> PropBoardRow:
        home_abbr = self.game.home_team_abbreviation or "???" if self.game else "???"
        away_abbr = self.game.away_team_abbreviation or "???" if self.game else "???"
        return PropBoardRow(
            signal_id=int(self.snapshot.id),
            game_id=self.snapshot.game_id,
            game_time_utc=self.game.game_time_utc if self.game else None,
            home_team_abbreviation=home_abbr,
            away_team_abbreviation=away_abbr,
            player_id=self.snapshot.player_id,
            player_name=self.snapshot.player_name,
            team_abbreviation=self.profile.feature_snapshot.team_abbreviation or (self.snapshot.team or ""),
            stat_type=self.snapshot.stat_type,
            line=float(self.snapshot.line),
            over_odds=int(self.snapshot.over_odds),
            under_odds=int(self.snapshot.under_odds),
            projected_value=self.profile.projected_value,
            edge_over=self.profile.edge_over,
            edge_under=self.profile.edge_under,
            over_probability=self.profile.over_probability,
            under_probability=self.profile.under_probability,
            confidence=self.profile.confidence,
            recommended_side=self.profile.recommended_side,
            recent_hit_rate=self.profile.recent_hit_rate,
            recent_games_count=self.profile.recent_games_count,
            key_factor=self.profile.key_factor,
            readiness=self.profile.readiness,
        )

    def to_detail_response(self) -> PropDetailResponse:
        board_row = self.to_board_row()
        recent_game_log = [
            GameLogEntry(
                game_id=row.game_id,
                game_date=row.game_date,
                opponent=row.opponent,
                is_home=row.is_home,
                minutes=float(row.minutes or 0.0),
                points=float(row.points or 0.0),
                rebounds=float(row.rebounds or 0.0),
                assists=float(row.assists or 0.0),
                steals=float(row.steals or 0.0),
                blocks=float(row.blocks or 0.0),
                turnovers=float(row.turnovers or 0.0),
                threes_made=float(row.threes_made or 0.0),
                field_goals_made=float(row.field_goals_made or 0.0),
                field_goals_attempted=float(row.field_goals_attempted or 0.0),
                free_throws_made=float(row.free_throws_made or 0.0),
                free_throws_attempted=float(row.free_throws_attempted or 0.0),
                plus_minus=float(row.plus_minus or 0.0),
            )
            for row in self.recent_logs
        ]
        return PropDetailResponse(
            **board_row.model_dump(),
            breakdown=self.profile.breakdown,
            opportunity=self.profile.opportunity,
            features=self.profile.feature_snapshot,
            recent_game_log=recent_game_log,
        )


def _today_window() -> tuple[datetime, datetime]:
    today = date.today()
    start = datetime(today.year, today.month, today.day, 0, 0, 0)
    end = start + timedelta(days=1)
    return start, end


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _dump_model_json(value: object) -> str:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")  # type: ignore[call-arg]
    else:
        payload = value
    return json.dumps(payload, sort_keys=True)


def _load_json_dict(payload: str | None) -> dict[str, object]:
    if not payload:
        return {}
    loaded = json.loads(payload)
    return loaded if isinstance(loaded, dict) else {}


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _float_or_none(value: float | int | None) -> float | None:
    return float(value) if value is not None else None


def _value_or_zero(value: float | int | None) -> float:
    return float(value) if value is not None else 0.0


def _weighted_average(weighted_values: list[tuple[float, float | None]]) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for weight, value in weighted_values:
        if value is None:
            continue
        numerator += weight * float(value)
        denominator += weight
    if denominator <= 0:
        return None
    return numerator / denominator


def _ppm(features: PregamePointsFeatures) -> float:
    weighted_values: list[tuple[float, float | None]] = []
    for weight, points_attr, minutes_attr in (
        (0.50, "season_points_avg", "season_minutes_avg"),
        (0.30, "last10_points_avg", "last10_minutes_avg"),
        (0.20, "last5_points_avg", "last5_minutes_avg"),
    ):
        points = _float_or_none(getattr(features, points_attr))
        minutes = _float_or_none(getattr(features, minutes_attr))
        if points is None or minutes is None or minutes <= 0:
            continue
        weighted_values.append((weight, points / minutes))

    ppm = _weighted_average(weighted_values)
    if ppm is None or ppm <= 0:
        return 0.65
    return _clamp(ppm, 0.35, 1.15)


def _title_case_status(status: str | None) -> str | None:
    if status is None:
        return None
    return _INJURY_STATUS_LABELS.get(str(status).upper())


def _recent_hit_rate(recent_logs: list[HistoricalGameLog], line: float) -> tuple[float | None, int]:
    results = [float(row.points or 0.0) > line for row in recent_logs[:MAX_RECENT_LOGS]]
    if not results:
        return None, 0
    return sum(1 for hit in results if hit) / len(results), len(results)


def _line_probability(projected_value: float, line: float, last10_points_std: float | None) -> tuple[float, float]:
    distribution_std = max(4.0, _value_or_zero(last10_points_std), projected_value * 0.18)
    distribution = NormalDist(mu=projected_value, sigma=distribution_std)
    over_probability = 1.0 - distribution.cdf(line)
    over_probability = _clamp(over_probability, 0.0, 1.0)
    return over_probability, 1.0 - over_probability


def _age_minutes(later: datetime, earlier: datetime | None) -> int | None:
    if earlier is None:
        return None
    delta_seconds = (later - earlier).total_seconds()
    return max(int(delta_seconds // 60), 0)


def _minutes_to_tip(game: Game | None, *, evaluation_time: datetime) -> int | None:
    if game is None or game.game_time_utc is None:
        return None
    return int((game.game_time_utc - evaluation_time).total_seconds() // 60)


def _build_signal_readiness(
    *,
    snapshot: PlayerPropSnapshot,
    game: Game | None,
    feature: PregamePointsFeatures | None,
    recent_games_count: int,
    latest_injury_report_at: datetime | None,
    evaluation_time: datetime,
) -> SignalReadiness:
    blockers: list[str] = []
    warnings: list[str] = []

    line_age_minutes = _age_minutes(evaluation_time, snapshot.captured_at)
    minutes_to_tip = _minutes_to_tip(game, evaluation_time=evaluation_time)
    using_fallback = feature is None

    if using_fallback:
        blockers.append("Pregame feature build is unavailable for this snapshot")

    if recent_games_count < MIN_RECENT_GAMES_FOR_RECOMMENDATION:
        blockers.append(f"Only {recent_games_count} recent games are available")

    if (
        line_age_minutes is not None
        and line_age_minutes > MAX_SIGNAL_CAPTURE_AGE_MINUTES
        and (minutes_to_tip is None or minutes_to_tip > 0)
    ):
        blockers.append(f"Pregame line snapshot is {line_age_minutes} minutes old")

    if (
        minutes_to_tip is not None
        and 0 < minutes_to_tip <= INJURY_REPORT_REQUIRED_WINDOW_MINUTES
        and latest_injury_report_at is None
    ):
        blockers.append("Official injury report is missing inside the pregame window")

    if feature is not None:
        context_confidence = _value_or_zero(feature.pregame_context_confidence)
        context_source = (feature.context_source or "none").strip().lower()
        if context_source == "none":
            warnings.append("Signal is missing enriched pregame context")
        elif context_source != "pregame_context":
            warnings.append(f"Signal is leaning on {context_source.replace('_', ' ')} context")

        if feature.pregame_context_confidence is not None and context_confidence < LOW_CONTEXT_CONFIDENCE_THRESHOLD:
            warnings.append(f"Pregame context confidence is only {context_confidence:.2f}")

    status: Literal["ready", "limited", "blocked"] = "ready"
    if blockers:
        status = "blocked"
    elif warnings:
        status = "limited"

    return SignalReadiness(
        is_ready=not blockers,
        status=status,
        blockers=blockers,
        warnings=warnings,
        line_age_minutes=line_age_minutes,
        minutes_to_tip=minutes_to_tip,
        using_fallback=using_fallback,
    )


def _availability_modifier(features: PregamePointsFeatures, *, context_confidence: float) -> float:
    if features.official_available is False:
        return 0.12
    modifier = 1.0
    if features.projected_available is False:
        modifier *= 0.40
    if features.late_scratch_risk is not None:
        modifier *= _clamp(1.0 - (float(features.late_scratch_risk) * context_confidence * 0.30), 0.35, 1.0)
    return modifier


def _build_opportunity_snapshot(features: PregamePointsFeatures) -> tuple[OpportunityContext, dict[str, float]]:
    context_confidence = _value_or_zero(features.pregame_context_confidence)

    minutes_base = _weighted_average(
        [(weight, _float_or_none(getattr(features, attr))) for weight, attr in _MINUTES_WEIGHTS]
    ) or 0.0
    rotation_minutes = _weighted_average(
        [(weight, _float_or_none(getattr(features, attr))) for weight, attr in _ROTATION_MINUTES_WEIGHTS]
    )
    rotation_weight = 0.30 * _clamp(features.rotation_sample_size / 8.0, 0.0, 1.0) if rotation_minutes is not None else 0.0
    expected_minutes = _weighted_average(
        [
            (1.0 - rotation_weight, minutes_base),
            (rotation_weight, rotation_minutes),
        ]
    ) or minutes_base

    availability_modifier = _availability_modifier(features, context_confidence=context_confidence)

    vacated_minutes_bonus = _clamp(
        _value_or_zero(features.vacated_minutes_proxy) * 0.05,
        0.0,
        2.5,
    ) * context_confidence
    vacated_usage_bonus = _clamp(
        _value_or_zero(features.vacated_usage_proxy) * 0.22
        + _value_or_zero(features.missing_high_usage_teammates) * 0.006
        + (0.010 if features.missing_primary_ballhandler else 0.0),
        0.0,
        0.045,
    ) * context_confidence
    role_replacement_minutes_bonus = _clamp(
        _value_or_zero(features.role_replacement_minutes_proxy) * 0.035,
        0.0,
        2.5,
    ) * context_confidence
    if features.missing_frontcourt_rotation_piece:
        role_replacement_minutes_bonus += 0.9 * context_confidence

    role_replacement_usage_bonus = _clamp(
        _value_or_zero(features.role_replacement_usage_proxy) * 0.14,
        0.0,
        0.025,
    ) * context_confidence

    absence_confidence = _clamp(_value_or_zero(features.absence_impact_sample_confidence), 0.0, 1.0)
    absence_minutes_bonus = _clamp(
        _value_or_zero(features.absence_impact_minutes_delta) * 0.10,
        0.0,
        1.5,
    ) * absence_confidence
    absence_usage_bonus = _clamp(
        _value_or_zero(features.absence_impact_usage_delta) * 0.16,
        0.0,
        0.020,
    ) * absence_confidence

    expected_minutes = max(
        0.0,
        expected_minutes * availability_modifier + vacated_minutes_bonus + role_replacement_minutes_bonus + absence_minutes_bonus,
    )

    expected_usage_pct = _weighted_average(
        [(weight, _float_or_none(getattr(features, attr))) for weight, attr in _USAGE_WEIGHTS]
    ) or 0.0
    expected_usage_pct = _clamp(
        expected_usage_pct + vacated_usage_bonus + role_replacement_usage_bonus + absence_usage_bonus,
        0.0,
        0.45,
    )

    expected_touches = _weighted_average(
        [(weight, _float_or_none(getattr(features, attr))) for weight, attr in _TOUCHES_WEIGHTS]
    ) or 0.0
    expected_touches += _clamp(_value_or_zero(features.role_replacement_touches_proxy) * 0.08, 0.0, 4.0) * context_confidence
    expected_touches += _clamp(_value_or_zero(features.absence_impact_touches_delta) * 0.08, 0.0, 3.0) * absence_confidence
    if features.missing_primary_ballhandler:
        expected_touches += 2.5 * context_confidence

    expected_start_rate = _weighted_average(
        [(weight, _float_or_none(getattr(features, attr))) for weight, attr in _START_RATE_WEIGHTS]
    ) or 0.0
    if features.expected_start is not None:
        start_signal = 1.0 if features.expected_start else 0.0
        expected_start_rate = _weighted_average(
            [
                (1.0 - (0.45 * context_confidence), expected_start_rate),
                (0.45 * context_confidence, start_signal),
            ]
        ) or expected_start_rate

    expected_close_rate = _weighted_average(
        [(weight, _float_or_none(getattr(features, attr))) for weight, attr in _CLOSE_RATE_WEIGHTS]
    ) or 0.0

    minutes_stability = 1.0 - _clamp(_value_or_zero(features.last10_minutes_std) / 8.0, 0.0, 1.0)
    rotation_stability = 1.0 - _clamp(_value_or_zero(features.last10_rotation_minutes_std) / 8.0, 0.0, 1.0)
    usage_alignment = 1.0 - _clamp(
        abs(_value_or_zero(features.last5_usage_pct) - _value_or_zero(features.season_usage_pct)) / 0.12,
        0.0,
        1.0,
    )
    role_stability = _clamp(
        0.30 * minutes_stability
        + 0.20 * rotation_stability
        + 0.22 * usage_alignment
        + 0.16 * _clamp(features.sample_size / 12.0, 0.0, 1.0)
        + 0.12 * (1.0 - _clamp(_value_or_zero(features.late_scratch_risk), 0.0, 1.0)),
        0.0,
        1.0,
    )
    opportunity_score = _clamp(
        0.42 * _clamp(expected_minutes / 36.0, 0.0, 1.2)
        + 0.22 * _clamp(expected_usage_pct / 0.30, 0.0, 1.2)
        + 0.10 * _clamp(expected_touches / 70.0, 0.0, 1.2)
        + 0.14 * role_stability
        + 0.12 * context_confidence,
        0.0,
        1.25,
    )
    opportunity_confidence = _clamp(
        0.30 * role_stability
        + 0.22 * _clamp(features.sample_size / 12.0, 0.0, 1.0)
        + 0.16 * minutes_stability
        + 0.12 * rotation_stability
        + 0.10 * context_confidence
        + 0.10 * availability_modifier,
        0.0,
        1.0,
    )

    opportunity = OpportunityContext(
        expected_minutes=round(expected_minutes, 3),
        season_minutes_avg=round(_value_or_zero(features.season_minutes_avg), 3),
        expected_usage_pct=round(expected_usage_pct, 4),
        expected_start_rate=round(expected_start_rate, 4),
        expected_close_rate=round(expected_close_rate, 4),
        role_stability=round(role_stability, 4),
        opportunity_score=round(opportunity_score, 4),
        opportunity_confidence=round(opportunity_confidence, 4),
        availability_modifier=round(availability_modifier, 4),
        vacated_minutes_bonus=round(vacated_minutes_bonus + role_replacement_minutes_bonus + absence_minutes_bonus, 3),
        vacated_usage_bonus=round(vacated_usage_bonus + role_replacement_usage_bonus + absence_usage_bonus, 4),
        injury_entries=[],
    )
    return opportunity, {
        "expected_minutes": expected_minutes,
        "expected_usage_pct": expected_usage_pct,
        "expected_touches": expected_touches,
        "context_confidence": context_confidence,
        "vacated_minutes_bonus": vacated_minutes_bonus + role_replacement_minutes_bonus + absence_minutes_bonus,
        "vacated_usage_bonus": vacated_usage_bonus + role_replacement_usage_bonus + absence_usage_bonus,
    }


def _derive_key_factor(
    features: PregamePointsFeatures,
    *,
    opportunity_score: float,
    recent_hit_rate: float | None,
    edge_over: float,
) -> str | None:
    if features.official_injury_status:
        label = _title_case_status(features.official_injury_status)
        return f"Player listed as {label} on official injury report" if label else None
    if features.context_source == "pregame_context":
        return "Pregame context is driving tonight's signal"
    if features.context_source == "official_injury_player":
        return "Official injury report adds direct availability context"
    if features.context_source == "official_injury_team":
        return "Teammate absences are creating role pressure"
    if recent_hit_rate is not None and recent_hit_rate >= 0.70:
        return "Recent results have been clearing this line consistently"
    if recent_hit_rate is not None and recent_hit_rate <= 0.30:
        return "Recent results have been staying under this line"
    if features.last5_points_avg is not None and features.season_points_avg is not None:
        delta = float(features.last5_points_avg) - float(features.season_points_avg)
        if abs(delta) >= 3.0:
            direction = "above" if delta > 0 else "below"
            return f"Recent form is {abs(delta):.1f} points {direction} season average"
    if features.back_to_back:
        return "Back-to-back spot adds downside fatigue risk"
    if opportunity_score >= 0.78:
        return "Minutes and usage context are both supportive"
    if edge_over <= -2.0:
        return "Recent production and matchup context lean under"
    return None


def build_stats_signal_profile(
    features: PregamePointsFeatures,
    *,
    recent_logs: list[HistoricalGameLog],
    injury_entries: list[InjuryEntry],
) -> StatsSignalProfile:
    opportunity, opportunity_inputs = _build_opportunity_snapshot(features)
    points_per_minute = _ppm(features)

    base_points_avg = _weighted_average(
        [(weight, _float_or_none(getattr(features, attr))) for weight, attr in _RECENT_POINT_WEIGHTS]
    ) or 0.0
    base_scoring = max(base_points_avg, opportunity_inputs["expected_minutes"] * points_per_minute)

    recent_form_adjustment = 0.0
    if features.last5_points_avg is not None and features.season_points_avg is not None:
        recent_form_adjustment += (float(features.last5_points_avg) - float(features.season_points_avg)) * 0.18
    if features.last10_points_avg is not None and features.season_points_avg is not None:
        recent_form_adjustment += (float(features.last10_points_avg) - float(features.season_points_avg)) * 0.08
    recent_form_adjustment = _clamp(recent_form_adjustment, -2.25, 2.25)

    minutes_adjustment = 0.0
    if features.season_minutes_avg is not None:
        minutes_adjustment = (opportunity_inputs["expected_minutes"] - float(features.season_minutes_avg)) * points_per_minute * 0.30

    usage_adjustment = 0.0
    if features.season_usage_pct is not None:
        usage_adjustment += (opportunity_inputs["expected_usage_pct"] - float(features.season_usage_pct)) * 7.0
    if features.season_touches is not None:
        usage_adjustment += (opportunity_inputs["expected_touches"] - float(features.season_touches)) * 0.01
    usage_adjustment = _clamp(usage_adjustment, -2.0, 2.0)

    efficiency_adjustment = 0.0
    if features.last10_ts_pct is not None and features.season_ts_pct is not None:
        efficiency_adjustment += (float(features.last10_ts_pct) - float(features.season_ts_pct)) * 6.0
    if features.last10_fg_pct is not None and features.season_fg_pct is not None:
        efficiency_adjustment += (float(features.last10_fg_pct) - float(features.season_fg_pct)) * 2.4
    efficiency_adjustment = _clamp(efficiency_adjustment, -1.2, 1.2)

    opponent_adjustment = 0.0
    if features.opponent_def_rating is not None and features.league_avg_def_rating is not None:
        opponent_adjustment = (float(features.league_avg_def_rating) - float(features.opponent_def_rating)) * 0.12
    opponent_adjustment = _clamp(opponent_adjustment, -1.0, 1.0)

    pace_adjustment = 0.0
    if features.team_pace is not None and features.opponent_pace is not None and features.league_avg_pace is not None:
        pace_adjustment = (((float(features.team_pace) + float(features.opponent_pace)) / 2.0) - float(features.league_avg_pace)) * 0.12
    pace_adjustment = _clamp(pace_adjustment, -1.0, 1.0)

    context_adjustment = 0.0
    if features.is_home:
        context_adjustment += 0.20
    if features.back_to_back:
        context_adjustment -= 0.55
    if features.days_rest is not None and features.days_rest >= 2:
        context_adjustment += min(features.days_rest - 1, 2) * 0.10
    context_adjustment += opportunity_inputs["vacated_minutes_bonus"] * 0.18
    context_adjustment += opportunity_inputs["vacated_usage_bonus"] * 12.0
    context_adjustment = _clamp(context_adjustment, -1.2, 1.5)

    projected_value = max(
        0.0,
        base_scoring
        + recent_form_adjustment
        + minutes_adjustment
        + usage_adjustment
        + efficiency_adjustment
        + opponent_adjustment
        + pace_adjustment
        + context_adjustment,
    )
    edge_over = projected_value - float(features.line)
    edge_under = -edge_over
    over_probability, under_probability = _line_probability(projected_value, float(features.line), features.last10_points_std)

    recent_hit_rate, recent_games_count = _recent_hit_rate(recent_logs, float(features.line))
    sample_strength = _clamp(features.sample_size / 12.0, 0.0, 1.0)
    points_stability = 1.0 - _clamp(_value_or_zero(features.last10_points_std) / 12.0, 0.0, 1.0)
    minutes_trend_stability = 1.0 - _clamp(
        abs(_value_or_zero(features.last5_minutes_avg) - _value_or_zero(features.last10_minutes_avg)) / 6.0,
        0.0,
        1.0,
    )
    recent_support = 0.0 if recent_hit_rate is None else _clamp(abs(recent_hit_rate - 0.5) * 2.0, 0.0, 1.0)
    confidence = _clamp(
        0.22 * sample_strength
        + 0.18 * points_stability
        + 0.14 * opportunity.role_stability
        + 0.12 * opportunity.opportunity_confidence
        + 0.10 * _clamp(opportunity.opportunity_score, 0.0, 1.0)
        + 0.12 * _clamp(abs(edge_over) / 4.0, 0.0, 1.0)
        + 0.12 * recent_support
        + 0.10 * minutes_trend_stability,
        0.0,
        1.0,
    )

    recommended_side: Literal["OVER", "UNDER"] | None = None
    if features.official_available is not False and _value_or_zero(features.late_scratch_risk) < 0.75:
        if edge_over >= MIN_EDGE_TO_RECOMMEND and over_probability >= MIN_PROBABILITY_TO_RECOMMEND and confidence >= MIN_CONFIDENCE_TO_RECOMMEND:
            recommended_side = "OVER"
        elif edge_under >= MIN_EDGE_TO_RECOMMEND and under_probability >= MIN_PROBABILITY_TO_RECOMMEND and confidence >= MIN_CONFIDENCE_TO_RECOMMEND:
            recommended_side = "UNDER"

    opportunity.injury_entries = injury_entries
    feature_snapshot = FeatureSnapshot(
        team_abbreviation=features.team_abbreviation or "",
        opponent_abbreviation=features.opponent_abbreviation or "",
        is_home=bool(features.is_home),
        days_rest=features.days_rest,
        back_to_back=bool(features.back_to_back),
        sample_size=int(features.sample_size or 0),
        season_points_avg=_float_or_none(features.season_points_avg),
        last10_points_avg=_float_or_none(features.last10_points_avg),
        last5_points_avg=_float_or_none(features.last5_points_avg),
        season_minutes_avg=_float_or_none(features.season_minutes_avg),
        last10_minutes_avg=_float_or_none(features.last10_minutes_avg),
        last5_minutes_avg=_float_or_none(features.last5_minutes_avg),
        season_usage_pct=_float_or_none(features.season_usage_pct),
        opponent_def_rating=_float_or_none(features.opponent_def_rating),
        opponent_pace=_float_or_none(features.opponent_pace),
        team_pace=_float_or_none(features.team_pace),
        context_source=features.context_source,
    )

    key_factor = _derive_key_factor(
        features,
        opportunity_score=opportunity.opportunity_score,
        recent_hit_rate=recent_hit_rate,
        edge_over=edge_over,
    )
    breakdown = PointsBreakdown(
        base_scoring=round(base_scoring, 3),
        recent_form_adjustment=round(recent_form_adjustment, 3),
        minutes_adjustment=round(minutes_adjustment, 3),
        usage_adjustment=round(usage_adjustment, 3),
        efficiency_adjustment=round(efficiency_adjustment, 3),
        opponent_adjustment=round(opponent_adjustment, 3),
        pace_adjustment=round(pace_adjustment, 3),
        context_adjustment=round(context_adjustment, 3),
        expected_minutes=round(opportunity.expected_minutes, 3),
        expected_usage_pct=round(opportunity.expected_usage_pct, 4),
        points_per_minute=round(points_per_minute, 3),
        projected_points=round(projected_value, 3),
    )

    return StatsSignalProfile(
        projected_value=round(projected_value, 3),
        edge_over=round(edge_over, 3),
        edge_under=round(edge_under, 3),
        over_probability=round(over_probability, 4),
        under_probability=round(under_probability, 4),
        confidence=round(confidence, 4),
        recommended_side=recommended_side,
        recent_hit_rate=round(recent_hit_rate, 4) if recent_hit_rate is not None else None,
        recent_games_count=recent_games_count,
        key_factor=key_factor,
        breakdown=breakdown,
        opportunity=opportunity,
        feature_snapshot=feature_snapshot,
        source_context_captured_at=features.captured_at if features.pregame_context_attached else None,
        source_injury_report_at=features.official_report_datetime_utc,
    )


def _build_fallback_profile(
    snapshot: PlayerPropSnapshot,
    game: Game | None,
    *,
    recent_logs: list[HistoricalGameLog],
    injury_entries: list[InjuryEntry],
) -> StatsSignalProfile:
    recent_points = [float(row.points or 0.0) for row in recent_logs[:MAX_RECENT_LOGS]]
    recent_minutes = [float(row.minutes or 0.0) for row in recent_logs[:MAX_RECENT_LOGS] if row.minutes is not None]
    projected_value = sum(recent_points) / len(recent_points) if recent_points else float(snapshot.line)
    recent_hit_rate, recent_games_count = _recent_hit_rate(recent_logs, float(snapshot.line))
    over_probability, under_probability = _line_probability(projected_value, float(snapshot.line), None)
    edge_over = projected_value - float(snapshot.line)
    sample_strength = _clamp(recent_games_count / 10.0, 0.0, 1.0)
    confidence = _clamp(0.20 + 0.35 * sample_strength + 0.20 * _clamp(abs(edge_over) / 4.0, 0.0, 1.0), 0.0, 0.72)
    recommended_side: Literal["OVER", "UNDER"] | None = None
    if edge_over >= 2.0 and confidence >= 0.55:
        recommended_side = "OVER"
    elif edge_over <= -2.0 and confidence >= 0.55:
        recommended_side = "UNDER"

    average_minutes = round(sum(recent_minutes) / len(recent_minutes), 3) if recent_minutes else 0.0
    opportunity = OpportunityContext(
        expected_minutes=average_minutes,
        season_minutes_avg=average_minutes,
        expected_usage_pct=0.0,
        expected_start_rate=0.0,
        expected_close_rate=0.0,
        role_stability=round(sample_strength, 4),
        opportunity_score=round(sample_strength, 4),
        opportunity_confidence=round(confidence, 4),
        availability_modifier=1.0,
        vacated_minutes_bonus=0.0,
        vacated_usage_bonus=0.0,
        injury_entries=injury_entries,
    )
    feature_snapshot = FeatureSnapshot(
        team_abbreviation=snapshot.team or "",
        opponent_abbreviation=snapshot.opponent or "",
        is_home=bool(game and game.home_team_abbreviation == snapshot.team),
        days_rest=None,
        back_to_back=False,
        sample_size=recent_games_count,
        season_points_avg=round(projected_value, 3),
        last10_points_avg=round(projected_value, 3),
        last5_points_avg=round(projected_value, 3),
        season_minutes_avg=average_minutes or None,
        last10_minutes_avg=average_minutes or None,
        last5_minutes_avg=average_minutes or None,
        season_usage_pct=None,
        opponent_def_rating=None,
        opponent_pace=None,
        team_pace=None,
        context_source="none",
    )
    breakdown = PointsBreakdown(
        base_scoring=round(projected_value, 3),
        recent_form_adjustment=0.0,
        minutes_adjustment=0.0,
        usage_adjustment=0.0,
        efficiency_adjustment=0.0,
        opponent_adjustment=0.0,
        pace_adjustment=0.0,
        context_adjustment=0.0,
        expected_minutes=opportunity.expected_minutes,
        expected_usage_pct=0.0,
        points_per_minute=round(projected_value / average_minutes, 3) if average_minutes > 0 else 0.0,
        projected_points=round(projected_value, 3),
    )
    return StatsSignalProfile(
        projected_value=round(projected_value, 3),
        edge_over=round(edge_over, 3),
        edge_under=round(-edge_over, 3),
        over_probability=round(over_probability, 4),
        under_probability=round(under_probability, 4),
        confidence=round(confidence, 4),
        recommended_side=recommended_side,
        recent_hit_rate=round(recent_hit_rate, 4) if recent_hit_rate is not None else None,
        recent_games_count=recent_games_count,
        key_factor="Limited historical sample; leaning on recent production" if recent_games_count else "Historical sample is limited",
        breakdown=breakdown,
        opportunity=opportunity,
        feature_snapshot=feature_snapshot,
        source_context_captured_at=None,
        source_injury_report_at=None,
    )


def _load_recent_logs_by_player(db: Session, player_ids: list[str]) -> dict[str, list[HistoricalGameLog]]:
    unique_player_ids = sorted({player_id for player_id in player_ids if player_id})
    if not unique_player_ids:
        return {}

    rows = (
        db.execute(
            select(HistoricalGameLog)
            .where(HistoricalGameLog.player_id.in_(unique_player_ids))
            .order_by(HistoricalGameLog.player_id, HistoricalGameLog.game_date.desc())
        )
        .scalars()
        .all()
    )

    logs_by_player: dict[str, list[HistoricalGameLog]] = defaultdict(list)
    for row in rows:
        bucket = logs_by_player[str(row.player_id)]
        if len(bucket) < MAX_RECENT_LOGS:
            bucket.append(row)
    return dict(logs_by_player)


def _load_features_by_snapshot(snapshots: list[PlayerPropSnapshot]) -> dict[tuple[datetime, str, str, str], PregamePointsFeatures]:
    features_by_snapshot: dict[tuple[datetime, str, str, str], PregamePointsFeatures] = {}
    for captured_at in sorted({snapshot.captured_at for snapshot in snapshots}):
        for feature in build_pregame_points_features(captured_at=captured_at):
            features_by_snapshot[(captured_at, feature.game_id, feature.player_id, POINTS_STAT_TYPE)] = feature
    return features_by_snapshot


def _injury_entries_for_team_date(rows: list[OfficialInjuryReportEntry]) -> list[InjuryEntry]:
    latest_by_player: dict[str, OfficialInjuryReportEntry] = {}
    for row in rows:
        key = row.player_name or ""
        current = latest_by_player.get(key)
        current_time = current.report_datetime_utc if current is not None else None
        if current is None or (row.report_datetime_utc or datetime.min) >= (current_time or datetime.min):
            latest_by_player[key] = row

    entries: list[InjuryEntry] = []
    for row in latest_by_player.values():
        label = _title_case_status(row.current_status)
        if label is None:
            continue
        entries.append(
            InjuryEntry(
                player_name=row.player_name or "",
                team_abbreviation=row.team_abbreviation or "",
                current_status=label,
                reason=row.reason or "",
            )
        )
    entries.sort(key=lambda entry: (entry.current_status, entry.player_name))
    return entries


def _load_injury_entries_by_team_date(
    db: Session,
    *,
    team_dates: set[tuple[str, date]],
) -> dict[tuple[str, date], list[InjuryEntry]]:
    if not team_dates:
        return {}

    team_abbreviations = sorted({team for team, _ in team_dates})
    game_dates = sorted({game_date for _, game_date in team_dates})
    rows = (
        db.execute(
            select(OfficialInjuryReportEntry)
            .where(
                OfficialInjuryReportEntry.team_abbreviation.in_(team_abbreviations),
                OfficialInjuryReportEntry.game_date.in_(game_dates),
                OfficialInjuryReportEntry.current_status.in_(list(_INJURY_STATUS_LABELS.keys())),
            )
            .order_by(
                OfficialInjuryReportEntry.team_abbreviation,
                OfficialInjuryReportEntry.game_date,
                OfficialInjuryReportEntry.report_datetime_utc.desc(),
            )
        )
        .scalars()
        .all()
    )

    grouped_rows: dict[tuple[str, date], list[OfficialInjuryReportEntry]] = defaultdict(list)
    for row in rows:
        if row.team_abbreviation and row.game_date:
            grouped_rows[(row.team_abbreviation, row.game_date)].append(row)

    return {
        key: _injury_entries_for_team_date(group_rows)
        for key, group_rows in grouped_rows.items()
    }


def _load_latest_injury_reports_by_date(
    db: Session,
    *,
    game_dates: set[date],
) -> dict[date, datetime]:
    if not game_dates:
        return {}

    rows = db.execute(
        select(
            OfficialInjuryReport.report_date,
            func.max(OfficialInjuryReport.report_datetime_utc).label("latest_report_at"),
        )
        .where(OfficialInjuryReport.report_date.in_(sorted(game_dates)))
        .group_by(OfficialInjuryReport.report_date)
    ).all()

    return {
        row.report_date: row.latest_report_at
        for row in rows
        if row.report_date is not None and row.latest_report_at is not None
    }


def _build_cards_from_snapshots(
    db: Session,
    snapshots: list[PlayerPropSnapshot],
    *,
    evaluation_time: datetime | None = None,
) -> list[StatsSignalCard]:
    if not snapshots:
        return []
    evaluation_time = evaluation_time or _utcnow()

    games_by_id = {
        game.game_id: game
        for game in db.execute(
            select(Game).where(Game.game_id.in_([snapshot.game_id for snapshot in snapshots]))
        ).scalars().all()
    }
    features_by_snapshot = _load_features_by_snapshot(snapshots)
    recent_logs_by_player = _load_recent_logs_by_player(db, [snapshot.player_id for snapshot in snapshots])

    team_dates: set[tuple[str, date]] = set()
    for snapshot in snapshots:
        game = games_by_id.get(snapshot.game_id)
        game_date = game.game_date.date() if game and game.game_date else None
        if snapshot.team and game_date is not None:
            team_dates.add((snapshot.team, game_date))
    injury_entries_by_team_date = _load_injury_entries_by_team_date(db, team_dates=team_dates)
    injury_reports_by_date = _load_latest_injury_reports_by_date(
        db,
        game_dates={game_date for _, game_date in team_dates},
    )

    cards: list[StatsSignalCard] = []
    for snapshot in snapshots:
        game = games_by_id.get(snapshot.game_id)
        recent_logs = recent_logs_by_player.get(snapshot.player_id, [])
        game_date = game.game_date.date() if game and game.game_date else None
        injury_entries = injury_entries_by_team_date.get((snapshot.team or "", game_date), []) if snapshot.team and game_date else []

        feature = features_by_snapshot.get((snapshot.captured_at, snapshot.game_id, snapshot.player_id, snapshot.stat_type))
        if feature is None:
            profile = _build_fallback_profile(snapshot, game, recent_logs=recent_logs, injury_entries=injury_entries)
        else:
            profile = build_stats_signal_profile(feature, recent_logs=recent_logs, injury_entries=injury_entries)
        profile.readiness = _build_signal_readiness(
            snapshot=snapshot,
            game=game,
            feature=feature,
            recent_games_count=profile.recent_games_count,
            latest_injury_report_at=injury_reports_by_date.get(game_date) if game_date is not None else None,
            evaluation_time=evaluation_time,
        )
        if profile.readiness.blockers:
            profile.recommended_side = None

        cards.append(
            StatsSignalCard(
                snapshot=snapshot,
                game=game,
                profile=profile,
                recent_logs=recent_logs,
            )
        )

    return cards


def _serialize_signal_snapshot(card: StatsSignalCard, *, created_at: datetime) -> StatsSignalSnapshot:
    readiness = card.profile.readiness
    feature_snapshot = card.profile.feature_snapshot

    return StatsSignalSnapshot(
        game_id=card.snapshot.game_id,
        player_id=card.snapshot.player_id,
        player_name=card.snapshot.player_name,
        team_abbreviation=feature_snapshot.team_abbreviation or (card.snapshot.team or None),
        opponent_abbreviation=feature_snapshot.opponent_abbreviation or (card.snapshot.opponent or None),
        stat_type=card.snapshot.stat_type,
        snapshot_phase=card.snapshot.snapshot_phase,
        line=float(card.snapshot.line),
        over_odds=int(card.snapshot.over_odds),
        under_odds=int(card.snapshot.under_odds),
        projected_value=card.profile.projected_value,
        edge_over=card.profile.edge_over,
        edge_under=card.profile.edge_under,
        over_probability=card.profile.over_probability,
        under_probability=card.profile.under_probability,
        confidence=card.profile.confidence,
        recommended_side=card.profile.recommended_side,
        recent_hit_rate=card.profile.recent_hit_rate,
        recent_games_count=card.profile.recent_games_count,
        key_factor=card.profile.key_factor,
        is_ready=readiness.is_ready,
        readiness_status=readiness.status,
        using_fallback=readiness.using_fallback,
        readiness_json=_dump_model_json(readiness),
        breakdown_json=_dump_model_json(card.profile.breakdown),
        opportunity_json=_dump_model_json(card.profile.opportunity),
        features_json=_dump_model_json(feature_snapshot),
        source_prop_captured_at=card.snapshot.captured_at,
        source_context_captured_at=card.profile.source_context_captured_at,
        source_injury_report_at=card.profile.source_injury_report_at,
        created_at=created_at,
    )


def persist_current_signal_snapshots() -> dict[str, int]:
    generated_at = _utcnow()
    with session_scope() as db:
        snapshots = _load_current_snapshots(db)
        if not snapshots:
            return {
                "signal_snapshots": 0,
                "signal_games": 0,
                "signal_recommendations": 0,
                "signal_blocked": 0,
            }

        cards = _build_cards_from_snapshots(db, snapshots, evaluation_time=generated_at)
        rows = [_serialize_signal_snapshot(card, created_at=generated_at) for card in cards]
        db.add_all(rows)
        return {
            "signal_snapshots": len(rows),
            "signal_games": len({row.game_id for row in rows}),
            "signal_recommendations": sum(1 for row in rows if row.recommended_side is not None),
            "signal_blocked": sum(1 for row in rows if row.readiness_status == "blocked"),
        }


def _base_snapshot_query():
    return select(PlayerPropSnapshot).where(
        PlayerPropSnapshot.is_live == False,  # noqa: E712
        PlayerPropSnapshot.snapshot_phase == CURRENT_SNAPSHOT_PHASE,
        PlayerPropSnapshot.stat_type == POINTS_STAT_TYPE,
    )


def _load_current_snapshots(
    db: Session,
    *,
    game_ids: list[str] | None = None,
    player_id: str | None = None,
) -> list[PlayerPropSnapshot]:
    query = _base_snapshot_query()
    if game_ids is not None:
        if not game_ids:
            return []
        query = query.where(PlayerPropSnapshot.game_id.in_(game_ids))
    if player_id is not None:
        query = query.where(PlayerPropSnapshot.player_id == player_id)
    query = query.order_by(PlayerPropSnapshot.game_id, PlayerPropSnapshot.player_name)
    return db.execute(query).scalars().all()


def _load_snapshots_for_today(db: Session, *, game_id: str | None = None) -> tuple[list[PlayerPropSnapshot], list[str]]:
    start, end = _today_window()
    today_game_ids = [
        row[0]
        for row in db.execute(
            select(Game.game_id).where(
                Game.game_date >= start,
                Game.game_date < end,
            )
        ).all()
    ]
    scoped_game_ids = [game_id] if game_id is not None else today_game_ids
    return _load_current_snapshots(db, game_ids=scoped_game_ids), scoped_game_ids


def get_prop_board_response(
    db: Session,
    *,
    game_id: str | None = None,
    recommended_only: bool = False,
    min_confidence: float | None = None,
) -> PropBoardResponse:
    snapshots, scoped_game_ids = _load_snapshots_for_today(db, game_id=game_id)
    if not snapshots:
        return PropBoardResponse(
            props=[],
            meta=PropBoardMeta(
                total_count=0,
                game_count=0 if game_id is None else len(scoped_game_ids),
                updated_at=None,
            ),
        )

    cards = _build_cards_from_snapshots(db, snapshots, evaluation_time=_utcnow())
    rows = [card.to_board_row() for card in cards]
    if recommended_only:
        rows = [row for row in rows if row.recommended_side is not None]
    if min_confidence is not None:
        rows = [row for row in rows if row.confidence >= min_confidence]

    rows.sort(
        key=lambda row: (
            row.recommended_side is None,
            -(row.confidence or 0.0),
            -abs(row.edge_over or 0.0),
        )
    )
    updated_at = max((snapshot.captured_at for snapshot in snapshots), default=None)
    total_game_count = len({snapshot.game_id for snapshot in snapshots})
    return PropBoardResponse(
        props=rows,
        meta=PropBoardMeta(
            total_count=len(rows),
            game_count=total_game_count,
            updated_at=updated_at,
        ),
    )


def get_prop_detail_response(db: Session, snapshot_id: int) -> PropDetailResponse | None:
    snapshot = db.get(PlayerPropSnapshot, snapshot_id)
    if snapshot is None or snapshot.is_live or snapshot.stat_type != POINTS_STAT_TYPE:
        return None
    cards = _build_cards_from_snapshots(db, [snapshot], evaluation_time=_utcnow())
    return cards[0].to_detail_response() if cards else None


def get_active_prop_rows_for_player(db: Session, player_id: str) -> list[PropBoardRow]:
    snapshots, _ = _load_snapshots_for_today(db)
    filtered = [snapshot for snapshot in snapshots if snapshot.player_id == player_id]
    rows = [card.to_board_row() for card in _build_cards_from_snapshots(db, filtered, evaluation_time=_utcnow())]
    rows.sort(key=lambda row: (row.recommended_side is None, -(row.confidence or 0.0), -abs(row.edge_over or 0.0)))
    return rows


def get_prop_counts_by_game(db: Session, game_ids: list[str]) -> dict[str, tuple[int, int]]:
    snapshots = _load_current_snapshots(db, game_ids=game_ids)
    counts = {game_id: (0, 0) for game_id in game_ids}
    for row in (card.to_board_row() for card in _build_cards_from_snapshots(db, snapshots, evaluation_time=_utcnow())):
        props, edges = counts.get(row.game_id, (0, 0))
        props += 1
        if row.recommended_side is not None:
            edges += 1
        counts[row.game_id] = (props, edges)
    return counts


def get_edges_today_response(db: Session) -> list[EdgeResponse]:
    board = get_prop_board_response(db, recommended_only=True)
    game_ids = list({row.game_id for row in board.props})
    games_by_id = {
        game.game_id: game
        for game in db.execute(select(Game).where(Game.game_id.in_(game_ids))).scalars().all()
    } if game_ids else {}

    edges: list[EdgeResponse] = []
    for row in board.props:
        game = games_by_id.get(row.game_id)
        matchup = f"{game.away_team_abbreviation} @ {game.home_team_abbreviation}" if game else f"{row.away_team_abbreviation} @ {row.home_team_abbreviation}"
        edges.append(
            EdgeResponse(
                signal_id=row.signal_id,
                game_id=row.game_id,
                game_time_utc=row.game_time_utc,
                matchup=matchup,
                player_id=row.player_id,
                player_name=row.player_name,
                team_abbreviation=row.team_abbreviation,
                stat_type=row.stat_type,
                line=row.line,
                projected_value=row.projected_value,
                edge=row.edge_over if row.recommended_side == "OVER" else row.edge_under,
                confidence=row.confidence,
                recommended_side=row.recommended_side,
                key_factor=row.key_factor,
            )
        )
    return edges


def build_signal_run_health(db: Session, today_game_ids: list[str]) -> SignalRunHealth:
    snapshots = _load_current_snapshots(db, game_ids=today_game_ids)
    if not snapshots:
        return SignalRunHealth()

    rows = [card.to_board_row() for card in _build_cards_from_snapshots(db, snapshots, evaluation_time=_utcnow())]
    return SignalRunHealth(
        last_run_at=max((snapshot.captured_at for snapshot in snapshots), default=None),
        signals_generated=len(rows),
        signals_with_recommendation=sum(1 for row in rows if row.recommended_side is not None),
        signals_ready=sum(1 for row in rows if row.readiness.status == "ready"),
        signals_limited=sum(1 for row in rows if row.readiness.status == "limited"),
        signals_blocked=sum(1 for row in rows if row.readiness.status == "blocked"),
        signals_using_fallback=sum(1 for row in rows if row.readiness.using_fallback),
        signals_missing_source_game=0,
    )


def get_historical_pregame_lines(
    db: Session,
    *,
    player_id: str,
    stat_type: str,
    game_ids: list[str],
) -> dict[str, float]:
    if not game_ids:
        return {}

    latest_odds_subquery = (
        select(
            OddsSnapshot.game_id,
            func.max(OddsSnapshot.captured_at).label("latest_captured_at"),
        )
        .where(
            OddsSnapshot.player_id == player_id,
            OddsSnapshot.stat_type == stat_type,
            OddsSnapshot.market_phase == "pregame",
            OddsSnapshot.game_id.in_(game_ids),
        )
        .group_by(OddsSnapshot.game_id)
        .subquery()
    )

    odds_rows = db.execute(
        select(OddsSnapshot.game_id, OddsSnapshot.line).join(
            latest_odds_subquery,
            and_(
                OddsSnapshot.game_id == latest_odds_subquery.c.game_id,
                OddsSnapshot.captured_at == latest_odds_subquery.c.latest_captured_at,
            ),
        )
    ).all()
    lines = {row.game_id: float(row.line) for row in odds_rows}

    missing_game_ids = [game_id for game_id in game_ids if game_id not in lines]
    if not missing_game_ids:
        return lines

    fallback_subquery = (
        select(
            PlayerPropSnapshot.game_id,
            func.max(PlayerPropSnapshot.captured_at).label("latest_captured_at"),
        )
        .where(
            PlayerPropSnapshot.player_id == player_id,
            PlayerPropSnapshot.stat_type == stat_type,
            PlayerPropSnapshot.is_live == False,  # noqa: E712
            PlayerPropSnapshot.game_id.in_(missing_game_ids),
        )
        .group_by(PlayerPropSnapshot.game_id)
        .subquery()
    )

    fallback_rows = db.execute(
        select(PlayerPropSnapshot.game_id, PlayerPropSnapshot.line).join(
            fallback_subquery,
            and_(
                PlayerPropSnapshot.game_id == fallback_subquery.c.game_id,
                PlayerPropSnapshot.captured_at == fallback_subquery.c.latest_captured_at,
            ),
        )
    ).all()
    for row in fallback_rows:
        lines[row.game_id] = float(row.line)

    return lines


def get_player_signal_history(
    db: Session,
    *,
    player_id: str,
    stat_type: str = POINTS_STAT_TYPE,
    limit: int = 20,
) -> list[SignalHistoryEntry]:
    latest_snapshot_subquery = (
        select(
            StatsSignalSnapshot.game_id,
            func.max(StatsSignalSnapshot.created_at).label("latest_created_at"),
        )
        .where(
            StatsSignalSnapshot.player_id == player_id,
            StatsSignalSnapshot.stat_type == stat_type,
        )
        .group_by(StatsSignalSnapshot.game_id)
        .subquery()
    )

    rows = db.execute(
        select(StatsSignalSnapshot, Game.game_time_utc)
        .join(
            latest_snapshot_subquery,
            and_(
                StatsSignalSnapshot.game_id == latest_snapshot_subquery.c.game_id,
                StatsSignalSnapshot.created_at == latest_snapshot_subquery.c.latest_created_at,
            ),
        )
        .outerjoin(Game, Game.game_id == StatsSignalSnapshot.game_id)
        .order_by(StatsSignalSnapshot.created_at.desc())
        .limit(limit)
    ).all()

    history: list[SignalHistoryEntry] = []
    for snapshot, game_time_utc in rows:
        history.append(
            SignalHistoryEntry(
                signal_snapshot_id=int(snapshot.id),
                game_id=snapshot.game_id,
                game_time_utc=game_time_utc,
                created_at=snapshot.created_at,
                snapshot_phase=snapshot.snapshot_phase,
                stat_type=snapshot.stat_type,
                line=float(snapshot.line),
                projected_value=float(snapshot.projected_value),
                confidence=float(snapshot.confidence) if snapshot.confidence is not None else None,
                recommended_side=snapshot.recommended_side,
                key_factor=snapshot.key_factor,
                readiness=SignalReadiness.model_validate(_load_json_dict(snapshot.readiness_json)),
                breakdown=PointsBreakdown.model_validate(_load_json_dict(snapshot.breakdown_json)),
                opportunity=OpportunityContext.model_validate(_load_json_dict(snapshot.opportunity_json)),
                features=FeatureSnapshot.model_validate(_load_json_dict(snapshot.features_json)),
                source_prop_captured_at=snapshot.source_prop_captured_at,
                source_context_captured_at=snapshot.source_context_captured_at,
                source_injury_report_at=snapshot.source_injury_report_at,
            )
        )
    return history
