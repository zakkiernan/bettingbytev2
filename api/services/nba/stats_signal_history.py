from __future__ import annotations

import json

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from analytics.nba.signals_profile import POINTS_STAT_TYPE
from api.schemas.board import SignalReadiness
from api.schemas.detail import FeatureSnapshot, OpportunityContext, PointsBreakdown
from api.schemas.line_movement import LineMovementPoint, LineMovementResponse
from api.schemas.players import SignalHistoryEntry
from database.models import Game, OddsSnapshot, PlayerPropSnapshot, StatsSignalSnapshot


def _load_json_dict(value: str | None) -> dict[str, object]:
    if not value:
        return {}
    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else {}


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
    offset: int = 0,
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
        .offset(offset)
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


def get_line_movement(db: Session, snapshot_id: int) -> LineMovementResponse | None:
    snapshot = db.get(PlayerPropSnapshot, snapshot_id)
    if snapshot is None:
        return None

    odds_rows = (
        db.execute(
            select(OddsSnapshot)
            .where(
                OddsSnapshot.game_id == snapshot.game_id,
                OddsSnapshot.player_id == snapshot.player_id,
                OddsSnapshot.stat_type == snapshot.stat_type,
            )
            .order_by(OddsSnapshot.captured_at.asc())
        )
        .scalars()
        .all()
    )

    snapshots_list = [
        LineMovementPoint(
            captured_at=row.captured_at,
            line=float(row.line),
            over_odds=int(row.over_odds),
            under_odds=int(row.under_odds),
            market_phase=row.market_phase or "pregame",
        )
        for row in odds_rows
    ]

    opening_line = snapshots_list[0].line if snapshots_list else None
    current_line = float(snapshot.line)

    return LineMovementResponse(
        signal_id=snapshot_id,
        game_id=snapshot.game_id,
        player_id=snapshot.player_id,
        player_name=snapshot.player_name,
        stat_type=snapshot.stat_type,
        current_line=current_line,
        opening_line=opening_line,
        line_movement=round(current_line - opening_line, 1) if opening_line is not None else None,
        snapshots=snapshots_list,
    )
