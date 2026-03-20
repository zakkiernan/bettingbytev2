from __future__ import annotations

import json
from statistics import mean

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from analytics.live_model import (
    SUPPORTED_LIVE_STAT_TYPES,
    LiveProjection,
    compute_game_pace,
    format_game_clock,
    generate_alerts,
    project_live_player,
)
from api.schemas import LiveAlert, LiveGameResponse, LiveGameSummary, LivePlayerRow, PaceSummary, TeamBrief
from database.models import Game, LiveGameSnapshot, LivePlayerSnapshot, StatsSignalSnapshot, Team

LIVE_GAME_STATUS_ACTIVE = 2
DEFAULT_EXPECTED_PACE = 100.0
EDGE_COUNT_THRESHOLD = 1.5
_UNKNOWN_TEAM = TeamBrief(
    team_id="",
    abbreviation="???",
    full_name="Unknown",
    city="Unknown",
    nickname="Unknown",
)


def _team_brief(team: Team | None, *, team_id: str | None = None) -> TeamBrief:
    if team is None:
        return TeamBrief(
            team_id=team_id or "",
            abbreviation="???",
            full_name="Unknown",
            city="Unknown",
            nickname="Unknown",
        )
    return TeamBrief(
        team_id=team.team_id,
        abbreviation=team.abbreviation,
        full_name=team.full_name,
        city=team.city,
        nickname=team.nickname,
    )


def _load_features(payload: str | None) -> dict[str, object]:
    if not payload:
        return {}
    try:
        loaded = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _latest_game_snapshots(db: Session, *, game_id: str | None = None) -> list[LiveGameSnapshot]:
    latest_by_game = (
        select(
            LiveGameSnapshot.game_id.label("game_id"),
            func.max(LiveGameSnapshot.captured_at).label("captured_at"),
        )
        .group_by(LiveGameSnapshot.game_id)
        .subquery()
    )

    stmt = (
        select(LiveGameSnapshot)
        .join(
            latest_by_game,
            and_(
                LiveGameSnapshot.game_id == latest_by_game.c.game_id,
                LiveGameSnapshot.captured_at == latest_by_game.c.captured_at,
            ),
        )
        .where(LiveGameSnapshot.game_status == LIVE_GAME_STATUS_ACTIVE)
        .order_by(LiveGameSnapshot.game_id)
    )
    if game_id is not None:
        stmt = stmt.where(LiveGameSnapshot.game_id == game_id)
    return db.execute(stmt).scalars().all()


def _latest_player_snapshots(db: Session, game_ids: list[str]) -> dict[tuple[str, str], LivePlayerSnapshot]:
    if not game_ids:
        return {}

    latest_by_player = (
        select(
            LivePlayerSnapshot.game_id.label("game_id"),
            LivePlayerSnapshot.player_id.label("player_id"),
            func.max(LivePlayerSnapshot.captured_at).label("captured_at"),
        )
        .where(LivePlayerSnapshot.game_id.in_(game_ids))
        .group_by(LivePlayerSnapshot.game_id, LivePlayerSnapshot.player_id)
        .subquery()
    )

    rows = (
        db.execute(
            select(LivePlayerSnapshot)
            .join(
                latest_by_player,
                and_(
                    LivePlayerSnapshot.game_id == latest_by_player.c.game_id,
                    LivePlayerSnapshot.player_id == latest_by_player.c.player_id,
                    LivePlayerSnapshot.captured_at == latest_by_player.c.captured_at,
                ),
            )
        )
        .scalars()
        .all()
    )
    return {(row.game_id, row.player_id): row for row in rows}


def _latest_signal_snapshots(db: Session, game_ids: list[str]) -> dict[tuple[str, str, str], StatsSignalSnapshot]:
    if not game_ids:
        return {}

    latest_by_signal = (
        select(
            StatsSignalSnapshot.game_id.label("game_id"),
            StatsSignalSnapshot.player_id.label("player_id"),
            StatsSignalSnapshot.stat_type.label("stat_type"),
            func.max(StatsSignalSnapshot.created_at).label("created_at"),
        )
        .where(
            StatsSignalSnapshot.game_id.in_(game_ids),
            StatsSignalSnapshot.snapshot_phase == "current",
            StatsSignalSnapshot.stat_type.in_(SUPPORTED_LIVE_STAT_TYPES),
        )
        .group_by(
            StatsSignalSnapshot.game_id,
            StatsSignalSnapshot.player_id,
            StatsSignalSnapshot.stat_type,
        )
        .subquery()
    )

    rows = (
        db.execute(
            select(StatsSignalSnapshot)
            .join(
                latest_by_signal,
                and_(
                    StatsSignalSnapshot.game_id == latest_by_signal.c.game_id,
                    StatsSignalSnapshot.player_id == latest_by_signal.c.player_id,
                    StatsSignalSnapshot.stat_type == latest_by_signal.c.stat_type,
                    StatsSignalSnapshot.created_at == latest_by_signal.c.created_at,
                ),
            )
        )
        .scalars()
        .all()
    )
    return {(row.game_id, row.player_id, row.stat_type): row for row in rows}


def _games_by_id(db: Session, game_ids: list[str]) -> dict[str, Game]:
    if not game_ids:
        return {}
    rows = db.execute(select(Game).where(Game.game_id.in_(game_ids))).scalars().all()
    return {row.game_id: row for row in rows}


def _teams_by_id(db: Session, team_ids: set[str]) -> dict[str, Team]:
    if not team_ids:
        return {}
    rows = db.execute(select(Team).where(Team.team_id.in_(team_ids))).scalars().all()
    return {row.team_id: row for row in rows}


def _expected_pace_for_game(signal_rows: list[StatsSignalSnapshot]) -> float:
    candidates: list[float] = []
    for row in signal_rows:
        features = _load_features(row.features_json)
        team_pace = _float_or_none(features.get("team_pace"))
        opponent_pace = _float_or_none(features.get("opponent_pace"))
        if team_pace is not None and opponent_pace is not None:
            candidates.append((team_pace + opponent_pace) / 2.0)
        elif team_pace is not None:
            candidates.append(team_pace)
        elif opponent_pace is not None:
            candidates.append(opponent_pace)

    if not candidates:
        return DEFAULT_EXPECTED_PACE
    return round(mean(candidates), 2)


def _projection_to_row(projection: LiveProjection) -> LivePlayerRow:
    return LivePlayerRow(
        player_id=projection.player_id,
        player_name=projection.player_name,
        team_abbreviation=projection.team_abbreviation,
        stat_type=projection.stat_type,
        line=projection.line,
        current_stat=projection.current_stat,
        live_projection=projection.live_projection,
        pace_projection=projection.pace_projection,
        live_edge=projection.live_edge,
        pregame_projection=projection.pregame_projection,
        on_court=projection.on_court,
        minutes_played=projection.minutes_played,
        fouls=projection.fouls,
    )


def _build_summary(
    *,
    game_snapshot: LiveGameSnapshot,
    game: Game | None,
    teams_by_id: dict[str, Team],
    live_edge_count: int,
) -> LiveGameSummary:
    return LiveGameSummary(
        game_id=game_snapshot.game_id,
        home_team=_team_brief(teams_by_id.get(game_snapshot.home_team_id), team_id=game_snapshot.home_team_id),
        away_team=_team_brief(teams_by_id.get(game_snapshot.away_team_id), team_id=game_snapshot.away_team_id),
        home_score=int(game_snapshot.home_team_score or 0),
        away_score=int(game_snapshot.away_team_score or 0),
        period=int(game_snapshot.period or 0),
        game_clock=format_game_clock(game_snapshot.game_clock),
        live_edge_count=live_edge_count,
        updated_at=game_snapshot.captured_at,
    )


def _build_game_response(
    *,
    game_snapshot: LiveGameSnapshot,
    game: Game | None,
    teams_by_id: dict[str, Team],
    player_snapshots: dict[tuple[str, str], LivePlayerSnapshot],
    signal_rows: list[StatsSignalSnapshot],
) -> LiveGameResponse:
    expected_pace = _expected_pace_for_game(signal_rows)
    pace = compute_game_pace(game_snapshot, expected_pace)

    projections: list[LiveProjection] = []
    pregame_projection_lookup: dict[str, float] = {}
    team_abbreviations: dict[str, str] = {}

    home_team = teams_by_id.get(game_snapshot.home_team_id)
    away_team = teams_by_id.get(game_snapshot.away_team_id)
    if home_team is not None:
        team_abbreviations[home_team.team_id] = home_team.abbreviation
    if away_team is not None:
        team_abbreviations[away_team.team_id] = away_team.abbreviation

    for signal_row in signal_rows:
        player_snapshot = player_snapshots.get((signal_row.game_id, signal_row.player_id))
        if player_snapshot is None:
            continue

        projection = project_live_player(
            pregame_projection=signal_row.projected_value,
            pregame_line=signal_row.line,
            stat_type=signal_row.stat_type,
            player_snapshot=player_snapshot,
            game_snapshot=game_snapshot,
            expected_pace=expected_pace,
        )
        projection.team_abbreviation = signal_row.team_abbreviation or team_abbreviations.get(player_snapshot.team_id, "???")
        projections.append(projection)
        pregame_projection_lookup[f"{projection.player_id}:{projection.stat_type}"] = projection.pregame_projection

    projections.sort(key=lambda row: (-abs(row.live_edge), row.player_name, row.stat_type))
    alert_rows = generate_alerts(projections, pregame_projection_lookup, pace)
    alerts = [LiveAlert(**payload) for payload in alert_rows]
    player_rows = [_projection_to_row(projection) for projection in projections]

    live_edge_count = sum(1 for projection in projections if abs(projection.live_edge) >= EDGE_COUNT_THRESHOLD)
    summary = _build_summary(
        game_snapshot=game_snapshot,
        game=game,
        teams_by_id=teams_by_id,
        live_edge_count=live_edge_count,
    )
    return LiveGameResponse(
        **summary.model_dump(),
        players=player_rows,
        alerts=alerts,
        pace=PaceSummary(
            current_pace=pace.current_pace,
            expected_pace=pace.expected_pace,
            scoring_impact_pct=pace.scoring_impact_pct,
        ),
    )


def get_active_live_games(db: Session) -> list[LiveGameSummary]:
    game_snapshots = _latest_game_snapshots(db)
    if not game_snapshots:
        return []

    game_ids = [row.game_id for row in game_snapshots]
    signal_snapshots = _latest_signal_snapshots(db, game_ids)
    signal_rows_by_game: dict[str, list[StatsSignalSnapshot]] = {}
    for row in signal_snapshots.values():
        signal_rows_by_game.setdefault(row.game_id, []).append(row)

    player_snapshots = _latest_player_snapshots(db, game_ids)
    games_by_id = _games_by_id(db, game_ids)
    team_ids = {
        team_id
        for row in game_snapshots
        for team_id in (row.home_team_id, row.away_team_id)
        if team_id
    }
    teams_by_id = _teams_by_id(db, team_ids)

    summaries: list[LiveGameSummary] = []
    for game_snapshot in game_snapshots:
        response = _build_game_response(
            game_snapshot=game_snapshot,
            game=games_by_id.get(game_snapshot.game_id),
            teams_by_id=teams_by_id,
            player_snapshots=player_snapshots,
            signal_rows=signal_rows_by_game.get(game_snapshot.game_id, []),
        )
        summaries.append(
            LiveGameSummary(
                game_id=response.game_id,
                home_team=response.home_team,
                away_team=response.away_team,
                home_score=response.home_score,
                away_score=response.away_score,
                period=response.period,
                game_clock=response.game_clock,
                live_edge_count=response.live_edge_count,
                updated_at=response.updated_at,
            )
        )

    summaries.sort(key=lambda row: row.updated_at or row.game_id, reverse=True)
    return summaries


def get_live_game(db: Session, game_id: str) -> LiveGameResponse | None:
    game_snapshots = _latest_game_snapshots(db, game_id=game_id)
    if not game_snapshots:
        return None

    game_snapshot = game_snapshots[0]
    player_snapshots = _latest_player_snapshots(db, [game_id])
    signal_rows = [
        row
        for key, row in _latest_signal_snapshots(db, [game_id]).items()
        if key[0] == game_id
    ]
    game = _games_by_id(db, [game_id]).get(game_id)
    teams_by_id = _teams_by_id(
        db,
        {team_id for team_id in (game_snapshot.home_team_id, game_snapshot.away_team_id) if team_id},
    )

    return _build_game_response(
        game_snapshot=game_snapshot,
        game=game,
        teams_by_id=teams_by_id,
        player_snapshots=player_snapshots,
        signal_rows=signal_rows,
    )
