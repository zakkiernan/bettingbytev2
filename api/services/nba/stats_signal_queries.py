from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from analytics.nba.signals_data import (
    build_cards_from_snapshots as _build_cards_from_snapshots,
    load_current_snapshots as _load_current_snapshots,
    load_latest_signal_audit_metrics as _load_latest_signal_audit_metrics,
    load_signal_audit_archive_summary as _load_signal_audit_archive_summary,
    load_snapshots_for_today as _load_snapshots_for_today,
    utcnow as _utcnow,
)
from analytics.nba.signals_profile import SUPPORTED_STAT_TYPES
from analytics.nba.signals_types import (
    SignalBreakdown,
    SignalFeatureSnapshot,
    SignalInjuryEntry,
    SignalOpportunityContext,
    SignalReadinessResult,
    StatsSignalCard,
)
from api.schemas.board import PropBoardMeta, PropBoardResponse, PropBoardRow, SignalReadiness
from api.schemas.detail import FeatureSnapshot, GameLogEntry, InjuryEntry, OpportunityContext, PointsBreakdown, PropDetailResponse
from api.schemas.edges import EdgeResponse
from api.schemas.health import SignalRunHealth
from api.services.nba.stats_signal_narrative import get_narrative_context
from database.models import Game, PlayerPropSnapshot

_STAT_LOG_ATTRS = {
    "points": "points",
    "rebounds": "rebounds",
    "assists": "assists",
    "threes": "threes_made",
}


def _to_signal_readiness(readiness: SignalReadinessResult) -> SignalReadiness:
    return SignalReadiness(**readiness.model_dump())


def _to_injury_entry(entry: SignalInjuryEntry) -> InjuryEntry:
    return InjuryEntry(**entry.model_dump())


def _to_opportunity_context(opportunity: SignalOpportunityContext) -> OpportunityContext:
    payload = opportunity.model_dump()
    payload["injury_entries"] = [_to_injury_entry(entry) for entry in opportunity.injury_entries]
    return OpportunityContext(**payload)


def _to_feature_snapshot(feature_snapshot: SignalFeatureSnapshot) -> FeatureSnapshot:
    return FeatureSnapshot(**feature_snapshot.model_dump())


def _to_points_breakdown(breakdown: SignalBreakdown) -> PointsBreakdown:
    return PointsBreakdown(**breakdown.model_dump())


def _to_board_row(card: StatsSignalCard) -> PropBoardRow:
    game = card.game
    home_abbr = (game.home_team_abbreviation or "???") if game else "???"
    away_abbr = (game.away_team_abbreviation or "???") if game else "???"

    stat_attr = _STAT_LOG_ATTRS.get(card.snapshot.stat_type, "points")
    recent_values = [
        float(getattr(row, stat_attr) or 0.0)
        for row in card.recent_logs
    ] or None

    return PropBoardRow(
        signal_id=int(card.snapshot.id or 0),
        game_id=card.snapshot.game_id,
        game_time_utc=game.game_time_utc if game else None,
        home_team_abbreviation=home_abbr,
        away_team_abbreviation=away_abbr,
        player_id=card.snapshot.player_id,
        player_name=card.snapshot.player_name,
        team_abbreviation=card.profile.feature_snapshot.team_abbreviation or (card.snapshot.team or ""),
        stat_type=card.snapshot.stat_type,
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
        readiness=_to_signal_readiness(card.profile.readiness),
        recent_values=recent_values,
    )


def _to_detail_response(card: StatsSignalCard) -> PropDetailResponse:
    board_row = _to_board_row(card)
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
        for row in card.recent_logs
    ]
    return PropDetailResponse(
        **board_row.model_dump(),
        breakdown=_to_points_breakdown(card.profile.breakdown),
        opportunity=_to_opportunity_context(card.profile.opportunity),
        features=_to_feature_snapshot(card.profile.feature_snapshot),
        recent_game_log=recent_game_log,
    )


def _card_to_board_row(card: StatsSignalCard) -> PropBoardRow:
    if hasattr(card, "to_board_row"):
        return card.to_board_row()
    return _to_board_row(card)


def get_prop_board_response(
    db: Session,
    *,
    game_id: str | None = None,
    stat_type: str | None = None,
    recommended_only: bool = False,
    min_confidence: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PropBoardResponse:
    snapshots, scoped_game_ids = _load_snapshots_for_today(db, game_id=game_id)
    if not snapshots:
        return PropBoardResponse(
            props=[],
            meta=PropBoardMeta(
                total_count=0,
                game_count=0 if game_id is None else len(scoped_game_ids),
                updated_at=None,
                stat_types_available=[],
            ),
        )

    cards = _build_cards_from_snapshots(db, snapshots, evaluation_time=_utcnow())
    rows = [_card_to_board_row(card) for card in cards]
    available_stat_types = sorted({row.stat_type for row in rows})
    if stat_type is not None:
        rows = [row for row in rows if row.stat_type == stat_type]
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
    total_count = len(rows)
    paged_rows = rows[offset : offset + limit]
    updated_at = max((snapshot.captured_at for snapshot in snapshots), default=None)
    total_game_count = len({snapshot.game_id for snapshot in snapshots})
    return PropBoardResponse(
        props=paged_rows,
        meta=PropBoardMeta(
            total_count=total_count,
            game_count=total_game_count,
            updated_at=updated_at,
            stat_types_available=available_stat_types,
            limit=limit,
            offset=offset,
            returned_count=len(paged_rows),
        ),
    )


def get_prop_detail_response(db: Session, snapshot_id: int) -> PropDetailResponse | None:
    snapshot = db.get(PlayerPropSnapshot, snapshot_id)
    if snapshot is None or snapshot.is_live or snapshot.stat_type not in SUPPORTED_STAT_TYPES:
        return None

    cards = _build_cards_from_snapshots(db, [snapshot], evaluation_time=_utcnow())
    if not cards:
        return None

    detail = _to_detail_response(cards[0])
    team_abbr = cards[0].profile.feature_snapshot.team_abbreviation or (snapshot.team or "")
    detail.narrative = get_narrative_context(db, snapshot.game_id, snapshot.player_id, team_abbr)
    return detail


def get_active_prop_rows_for_player(db: Session, player_id: str) -> list[PropBoardRow]:
    snapshots, _ = _load_snapshots_for_today(db)
    filtered = [snapshot for snapshot in snapshots if snapshot.player_id == player_id]
    rows = [_card_to_board_row(card) for card in _build_cards_from_snapshots(db, filtered, evaluation_time=_utcnow())]
    rows.sort(key=lambda row: (row.recommended_side is None, -(row.confidence or 0.0), -abs(row.edge_over or 0.0)))
    return rows


def get_prop_counts_by_game(db: Session, game_ids: list[str]) -> dict[str, tuple[int, int]]:
    snapshots = _load_current_snapshots(db, game_ids=game_ids)
    counts = {game_id: (0, 0) for game_id in game_ids}
    for row in (_card_to_board_row(card) for card in _build_cards_from_snapshots(db, snapshots, evaluation_time=_utcnow())):
        props, edges = counts.get(row.game_id, (0, 0))
        props += 1
        if row.recommended_side is not None:
            edges += 1
        counts[row.game_id] = (props, edges)
    return counts


def get_edges_today_response(db: Session, *, limit: int = 50, offset: int = 0) -> list[EdgeResponse]:
    board = get_prop_board_response(db, recommended_only=True, limit=limit, offset=offset)
    game_ids = list({row.game_id for row in board.props})
    games_by_id = {
        game.game_id: game
        for game in db.execute(select(Game).where(Game.game_id.in_(game_ids))).scalars().all()
    } if game_ids else {}

    edges: list[EdgeResponse] = []
    for row in board.props:
        game = games_by_id.get(row.game_id)
        matchup = (
            f"{game.away_team_abbreviation} @ {game.home_team_abbreviation}"
            if game
            else f"{row.away_team_abbreviation} @ {row.home_team_abbreviation}"
        )
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
    audit_summary = _load_signal_audit_archive_summary(db)
    if not snapshots:
        return SignalRunHealth(**audit_summary)

    rows = [_card_to_board_row(card) for card in _build_cards_from_snapshots(db, snapshots, evaluation_time=_utcnow())]
    signals_by_stat_type = Counter(row.stat_type for row in rows)
    blocked_by_stat_type = Counter(row.stat_type for row in rows if row.readiness.status == "blocked")
    blocked_reasons = Counter(
        blocker
        for row in rows
        for blocker in row.readiness.blockers
    )
    latest_current_capture = max((snapshot.captured_at for snapshot in snapshots), default=None)
    latest_persisted_at, latest_audit_source_prop_captured_at = _load_latest_signal_audit_metrics(
        db,
        game_ids=today_game_ids,
    )
    audit_lag_minutes = None
    if latest_current_capture is not None and latest_audit_source_prop_captured_at is not None:
        delta_seconds = (latest_current_capture - latest_audit_source_prop_captured_at).total_seconds()
        audit_lag_minutes = max(int(delta_seconds // 60), 0)

    return SignalRunHealth(
        last_run_at=latest_current_capture,
        signals_generated=len(rows),
        signals_with_recommendation=sum(1 for row in rows if row.recommended_side is not None),
        signals_ready=sum(1 for row in rows if row.readiness.status == "ready"),
        signals_limited=sum(1 for row in rows if row.readiness.status == "limited"),
        signals_blocked=sum(1 for row in rows if row.readiness.status == "blocked"),
        signals_using_fallback=sum(1 for row in rows if row.readiness.using_fallback),
        signals_by_stat_type=dict(sorted(signals_by_stat_type.items())),
        blocked_by_stat_type=dict(sorted(blocked_by_stat_type.items())),
        blocked_reasons=dict(sorted(blocked_reasons.items())),
        latest_persisted_at=latest_persisted_at,
        latest_audit_source_prop_captured_at=latest_audit_source_prop_captured_at,
        audit_lag_minutes=audit_lag_minutes,
        signals_missing_source_game=0,
        **audit_summary,
    )
