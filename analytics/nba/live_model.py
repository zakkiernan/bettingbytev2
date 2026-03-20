from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re

from database.models import LiveGameSnapshot, LivePlayerSnapshot

SUPPORTED_LIVE_STAT_TYPES = ("points", "rebounds", "assists", "threes")
EDGE_ALERT_THRESHOLD = 1.5
PACE_SHIFT_ALERT_PCT = 8.0
_SCORE_TO_POSSESSIONS_FACTOR = 2.24
_ISO_CLOCK_RE = re.compile(
    r"^PT(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class LiveProjection:
    player_id: str
    player_name: str
    team_abbreviation: str
    stat_type: str
    line: float
    current_stat: float
    live_projection: float
    pace_projection: float
    live_edge: float
    pregame_projection: float
    on_court: bool
    minutes_played: float
    fouls: float


@dataclass(slots=True)
class GamePace:
    current_pace: float
    expected_pace: float
    scoring_impact_pct: float


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _value_or_zero(value: float | int | None) -> float:
    return float(value) if value is not None else 0.0


def _stat_value(stat_type: str, player_snapshot: LivePlayerSnapshot) -> float:
    if stat_type == "points":
        return _value_or_zero(player_snapshot.points)
    if stat_type == "rebounds":
        return _value_or_zero(player_snapshot.rebounds)
    if stat_type == "assists":
        return _value_or_zero(player_snapshot.assists)
    if stat_type == "threes":
        return _value_or_zero(player_snapshot.threes_made)
    raise ValueError(f"Unsupported live stat type: {stat_type!r}")


def _parse_clock_minutes_remaining(game_clock: str | None) -> float:
    if not game_clock:
        return 0.0

    normalized = game_clock.strip()
    match = _ISO_CLOCK_RE.match(normalized)
    if match:
        minutes = float(match.group("minutes") or 0.0)
        seconds = float(match.group("seconds") or 0.0)
        return minutes + seconds / 60.0

    if ":" in normalized:
        minutes_text, seconds_text = normalized.split(":", 1)
        try:
            minutes = float(minutes_text)
            seconds = float(seconds_text)
        except ValueError:
            return 0.0
        return minutes + seconds / 60.0

    return 0.0


def format_game_clock(game_clock: str | None) -> str:
    if not game_clock:
        return "Not Started"

    normalized = game_clock.strip()
    minutes_remaining = _parse_clock_minutes_remaining(normalized)
    if minutes_remaining <= 0.0 and normalized and ":" not in normalized and not normalized.upper().startswith("PT"):
        return normalized

    total_seconds = max(int(round(minutes_remaining * 60.0)), 0)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def _elapsed_regulation_minutes(game_snapshot: LiveGameSnapshot) -> float:
    period = int(game_snapshot.period or 0)
    if period <= 0:
        return 0.0

    if period <= 4:
        period_length = 12.0
        completed_minutes = max(period - 1, 0) * period_length
    else:
        period_length = 5.0
        completed_minutes = 48.0 + max(period - 5, 0) * period_length

    remaining_in_period = _clamp(_parse_clock_minutes_remaining(game_snapshot.game_clock), 0.0, period_length)
    return _clamp(completed_minutes + (period_length - remaining_in_period), 0.0, completed_minutes + period_length)


def compute_game_pace(
    game_snapshot: LiveGameSnapshot,
    expected_pace: float,
) -> GamePace:
    expected = max(float(expected_pace or 0.0), 0.0)
    elapsed_minutes = _elapsed_regulation_minutes(game_snapshot)
    total_points = _value_or_zero(game_snapshot.home_team_score) + _value_or_zero(game_snapshot.away_team_score)

    if expected <= 0.0:
        return GamePace(current_pace=0.0, expected_pace=0.0, scoring_impact_pct=0.0)

    if elapsed_minutes <= 0.5 or total_points <= 0.0:
        return GamePace(current_pace=expected, expected_pace=expected, scoring_impact_pct=0.0)

    estimated_possessions = total_points / _SCORE_TO_POSSESSIONS_FACTOR
    current_pace = estimated_possessions * 48.0 / elapsed_minutes
    scoring_impact_pct = ((current_pace / expected) - 1.0) * 100.0
    return GamePace(
        current_pace=round(current_pace, 2),
        expected_pace=round(expected, 2),
        scoring_impact_pct=round(scoring_impact_pct, 2),
    )


def project_live_player(
    pregame_projection: float,
    pregame_line: float,
    stat_type: str,
    player_snapshot: LivePlayerSnapshot,
    game_snapshot: LiveGameSnapshot,
    expected_pace: float,
) -> LiveProjection:
    current_stat = _stat_value(stat_type, player_snapshot)
    minutes_played = _clamp(_value_or_zero(player_snapshot.minutes), 0.0, 48.0)
    fouls = _value_or_zero(player_snapshot.fouls)

    minutes_remaining = max(48.0 - minutes_played, 0.0)
    period = int(game_snapshot.period or 0)
    if (period == 3 and fouls >= 4.0) or (period >= 4 and fouls >= 5.0):
        minutes_remaining *= 0.75

    current_per_minute_rate = current_stat / max(minutes_played, 1.0)
    pace = compute_game_pace(game_snapshot, expected_pace)
    pace_factor = pace.current_pace / pace.expected_pace if pace.expected_pace > 0.0 else 1.0

    pace_projected_remaining = current_per_minute_rate * minutes_remaining * pace_factor
    pace_projection = current_stat + pace_projected_remaining

    game_progress = _clamp(minutes_played / 48.0, 0.0, 1.0)
    live_projection = (1.0 - game_progress) * float(pregame_projection) + game_progress * pace_projection

    return LiveProjection(
        player_id=str(player_snapshot.player_id),
        player_name=player_snapshot.player_name,
        team_abbreviation="",
        stat_type=stat_type,
        line=float(pregame_line),
        current_stat=round(current_stat, 2),
        live_projection=round(live_projection, 2),
        pace_projection=round(pace_projection, 2),
        live_edge=round(live_projection - float(pregame_line), 2),
        pregame_projection=round(float(pregame_projection), 2),
        on_court=bool(player_snapshot.on_court),
        minutes_played=round(minutes_played, 2),
        fouls=round(fouls, 2),
    )


def _alert_created_at() -> datetime:
    return datetime.now(UTC)


def _alert_payload(
    *,
    alert_type: str,
    player_name: str,
    message: str,
    edge_value: float | None = None,
    player_key: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": f"{alert_type}:{player_key}",
        "type": alert_type,
        "player_name": player_name,
        "message": message,
        "created_at": _alert_created_at(),
    }
    if edge_value is not None:
        payload["edge_value"] = round(float(edge_value), 2)
    return payload


def generate_alerts(
    projections: list[LiveProjection],
    pregame_projections: dict[str, float],
    pace: GamePace,
) -> list[dict]:
    alerts: list[dict] = []

    if abs(pace.scoring_impact_pct) > PACE_SHIFT_ALERT_PCT:
        direction = "above" if pace.scoring_impact_pct > 0 else "below"
        alerts.append(
            _alert_payload(
                alert_type="pace_shift",
                player_name="Game Pace",
                message=f"Game pace is {abs(pace.scoring_impact_pct):.1f}% {direction} the pregame expectation.",
                player_key="game",
            )
        )

    for projection in projections:
        player_key = f"{projection.player_id}:{projection.stat_type}"
        pregame_projection = float(
            pregame_projections.get(player_key, pregame_projections.get(projection.player_id, projection.pregame_projection))
        )
        pregame_edge = pregame_projection - projection.line
        current_rate_projection = (
            projection.current_stat / max(projection.minutes_played, 1.0)
        ) * 48.0

        if 0.0 < projection.minutes_played <= 12.0:
            if current_rate_projection >= pregame_projection * 1.20:
                alerts.append(
                    _alert_payload(
                        alert_type="hot_start",
                        player_name=projection.player_name,
                        message=f"{projection.player_name} is tracking more than 20% above pregame {projection.stat_type} pace.",
                        edge_value=projection.live_edge,
                        player_key=player_key,
                    )
                )
            elif current_rate_projection <= pregame_projection * 0.80:
                alerts.append(
                    _alert_payload(
                        alert_type="cold_start",
                        player_name=projection.player_name,
                        message=f"{projection.player_name} is tracking more than 20% below pregame {projection.stat_type} pace.",
                        edge_value=projection.live_edge,
                        player_key=player_key,
                    )
                )

        edge_flipped = pregame_edge == 0.0 and projection.live_edge != 0.0
        if not edge_flipped and pregame_edge != 0.0 and projection.live_edge != 0.0:
            edge_flipped = (pregame_edge > 0.0) != (projection.live_edge > 0.0)

        edge_crossed_threshold = abs(pregame_edge) < EDGE_ALERT_THRESHOLD <= abs(projection.live_edge)
        if edge_flipped or edge_crossed_threshold:
            alerts.append(
                _alert_payload(
                    alert_type="edge_emerged",
                    player_name=projection.player_name,
                    message=f"{projection.player_name} now shows a live {projection.stat_type} edge of {projection.live_edge:+.2f}.",
                    edge_value=projection.live_edge,
                    player_key=player_key,
                )
            )

        if projection.fouls >= 4.0 and projection.minutes_played < 36.0:
            alerts.append(
                _alert_payload(
                    alert_type="foul_trouble",
                    player_name=projection.player_name,
                    message=f"{projection.player_name} is in foul trouble with {projection.fouls:.0f} fouls.",
                    edge_value=projection.live_edge,
                    player_key=player_key,
                )
            )

    return alerts
