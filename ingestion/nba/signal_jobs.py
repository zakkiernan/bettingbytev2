from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable, ContextManager

from sqlalchemy.orm import Session

from analytics.nba.signals_data import (
    build_cards_from_snapshots as _build_cards_from_snapshots,
    load_current_snapshots as _load_current_snapshots,
    load_latest_signal_audit_metrics as _load_latest_signal_audit_metrics,
    utcnow as _utcnow,
)
from analytics.nba.signals_types import StatsSignalCard
from database.db import session_scope
from database.models import SignalAuditTrail, StatsSignalSnapshot


def _dump_model_json(value: object) -> str:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")  # type: ignore[call-arg]
    elif hasattr(value, "to_dict"):
        payload = value.to_dict()  # type: ignore[assignment]
    else:
        payload = value
    return json.dumps(payload, sort_keys=True, default=str)


def _dump_json_list(values: list[str]) -> str:
    return json.dumps(values, sort_keys=True, default=str)


def _age_minutes(later: datetime, earlier: datetime | None) -> int | None:
    if earlier is None:
        return None
    delta_seconds = (later - earlier).total_seconds()
    return max(int(delta_seconds // 60), 0)


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


def _serialize_signal_audit_row(card: StatsSignalCard, *, created_at: datetime) -> SignalAuditTrail:
    readiness = card.profile.readiness
    return SignalAuditTrail(
        game_id=card.snapshot.game_id,
        player_id=card.snapshot.player_id,
        stat_type=card.snapshot.stat_type,
        snapshot_phase=card.snapshot.snapshot_phase,
        line=float(card.snapshot.line),
        projected_value=card.profile.projected_value,
        edge=round(card.profile.projected_value - float(card.snapshot.line), 3),
        confidence=card.profile.confidence,
        recommended_side=card.profile.recommended_side,
        readiness_status=readiness.status,
        blockers_json=_dump_json_list(readiness.blockers),
        warnings_json=_dump_json_list(readiness.warnings),
        breakdown_json=_dump_model_json(card.profile.breakdown),
        source_context_captured_at=card.profile.source_context_captured_at,
        source_injury_report_at=card.profile.source_injury_report_at,
        captured_at=created_at,
    )


def persist_current_signal_snapshots(
    *,
    session_scope_factory: Callable[[], ContextManager[Session]] | None = None,
    load_current_snapshots_fn: Callable[..., list[Any]] | None = None,
    build_cards_from_snapshots_fn: Callable[..., list[StatsSignalCard]] | None = None,
    utcnow_fn: Callable[[], datetime] | None = None,
) -> dict[str, int]:
    session_scope_factory = session_scope if session_scope_factory is None else session_scope_factory
    load_current_snapshots_fn = _load_current_snapshots if load_current_snapshots_fn is None else load_current_snapshots_fn
    build_cards_from_snapshots_fn = _build_cards_from_snapshots if build_cards_from_snapshots_fn is None else build_cards_from_snapshots_fn
    utcnow_fn = _utcnow if utcnow_fn is None else utcnow_fn
    generated_at = utcnow_fn()
    with session_scope_factory() as db:
        snapshots = load_current_snapshots_fn(db)
        if not snapshots:
            return {
                "signal_snapshots": 0,
                "signal_audit_rows": 0,
                "signal_games": 0,
                "signal_recommendations": 0,
                "signal_blocked": 0,
            }

        cards = build_cards_from_snapshots_fn(db, snapshots, evaluation_time=generated_at)
        rows = [_serialize_signal_snapshot(card, created_at=generated_at) for card in cards]
        audit_rows = [_serialize_signal_audit_row(card, created_at=generated_at) for card in cards]
        db.add_all(rows + audit_rows)
        return {
            "signal_snapshots": len(rows),
            "signal_audit_rows": len(audit_rows),
            "signal_games": len({row.game_id for row in rows}),
            "signal_recommendations": sum(1 for row in rows if row.recommended_side is not None),
            "signal_blocked": sum(1 for row in rows if row.readiness_status == "blocked"),
        }


def repair_current_signal_snapshots(
    *,
    force: bool = False,
    session_scope_factory: Callable[[], ContextManager[Session]] | None = None,
    load_current_snapshots_fn: Callable[..., list[Any]] | None = None,
    build_cards_from_snapshots_fn: Callable[..., list[StatsSignalCard]] | None = None,
    load_latest_signal_audit_metrics_fn: Callable[..., tuple[datetime | None, datetime | None]] | None = None,
    utcnow_fn: Callable[[], datetime] | None = None,
) -> dict[str, int | str | None]:
    session_scope_factory = session_scope if session_scope_factory is None else session_scope_factory
    load_current_snapshots_fn = _load_current_snapshots if load_current_snapshots_fn is None else load_current_snapshots_fn
    build_cards_from_snapshots_fn = _build_cards_from_snapshots if build_cards_from_snapshots_fn is None else build_cards_from_snapshots_fn
    load_latest_signal_audit_metrics_fn = _load_latest_signal_audit_metrics if load_latest_signal_audit_metrics_fn is None else load_latest_signal_audit_metrics_fn
    utcnow_fn = _utcnow if utcnow_fn is None else utcnow_fn
    generated_at = utcnow_fn()
    with session_scope_factory() as db:
        snapshots = load_current_snapshots_fn(db)
        if not snapshots:
            return {
                "signal_snapshots": 0,
                "signal_audit_rows": 0,
                "signal_games": 0,
                "signal_recommendations": 0,
                "signal_blocked": 0,
                "repair_performed": 0,
                "repair_reason": "no_current_snapshots",
            }

        scoped_game_ids = sorted({snapshot.game_id for snapshot in snapshots})
        latest_current_capture = max((snapshot.captured_at for snapshot in snapshots), default=None)
        _, latest_audit_source_prop_captured_at = load_latest_signal_audit_metrics_fn(
            db,
            game_ids=scoped_game_ids,
        )
        audit_lag_minutes = (
            _age_minutes(latest_current_capture, latest_audit_source_prop_captured_at)
            if latest_current_capture is not None and latest_audit_source_prop_captured_at is not None
            else None
        )

        if (
            not force
            and latest_current_capture is not None
            and latest_audit_source_prop_captured_at is not None
            and latest_current_capture <= latest_audit_source_prop_captured_at
        ):
            return {
                "signal_snapshots": 0,
                "signal_audit_rows": 0,
                "signal_games": len(scoped_game_ids),
                "signal_recommendations": 0,
                "signal_blocked": 0,
                "repair_performed": 0,
                "repair_reason": "up_to_date",
                "audit_lag_minutes": audit_lag_minutes,
            }

        cards = build_cards_from_snapshots_fn(db, snapshots, evaluation_time=generated_at)
        rows = [_serialize_signal_snapshot(card, created_at=generated_at) for card in cards]
        audit_rows = [_serialize_signal_audit_row(card, created_at=generated_at) for card in cards]
        db.add_all(rows + audit_rows)
        return {
            "signal_snapshots": len(rows),
            "signal_audit_rows": len(audit_rows),
            "signal_games": len({row.game_id for row in rows}),
            "signal_recommendations": sum(1 for row in rows if row.recommended_side is not None),
            "signal_blocked": sum(1 for row in rows if row.readiness_status == "blocked"),
            "repair_performed": 1,
            "repair_reason": "replayed_from_current_snapshots",
            "audit_lag_minutes": audit_lag_minutes,
        }
