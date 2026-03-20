from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.audit import SignalAuditEntry
from api.schemas.detail import PointsBreakdown
from database.models import SignalAuditTrail


def _load_json_list(payload: str | None) -> list[str]:
    if not payload:
        return []
    loaded = json.loads(payload)
    if not isinstance(loaded, list):
        return []
    return [str(value) for value in loaded]


def _build_audit_entry(row: SignalAuditTrail) -> SignalAuditEntry:
    breakdown_payload = json.loads(row.breakdown_json) if row.breakdown_json else {}
    if not isinstance(breakdown_payload, dict):
        breakdown_payload = {}
    return SignalAuditEntry(
        id=int(row.id),
        game_id=row.game_id,
        player_id=row.player_id,
        stat_type=row.stat_type,
        snapshot_phase=row.snapshot_phase,
        line=float(row.line),
        projected_value=float(row.projected_value),
        edge=float(row.edge),
        confidence=float(row.confidence),
        recommended_side=row.recommended_side,
        readiness_status=row.readiness_status,
        blockers=_load_json_list(row.blockers_json),
        warnings=_load_json_list(row.warnings_json),
        breakdown=PointsBreakdown(**breakdown_payload),
        source_context_captured_at=row.source_context_captured_at,
        source_injury_report_at=row.source_injury_report_at,
        captured_at=row.captured_at,
    )


def get_player_game_audit_rows(db: Session, *, player_id: str, game_id: str) -> list[SignalAuditEntry]:
    rows = (
        db.execute(
            select(SignalAuditTrail)
            .where(
                SignalAuditTrail.player_id == player_id,
                SignalAuditTrail.game_id == game_id,
            )
            .order_by(SignalAuditTrail.captured_at.asc(), SignalAuditTrail.id.asc())
        )
        .scalars()
        .all()
    )
    return [_build_audit_entry(row) for row in rows]


def get_game_audit_rows(db: Session, *, game_id: str) -> list[SignalAuditEntry]:
    rows = (
        db.execute(
            select(SignalAuditTrail)
            .where(SignalAuditTrail.game_id == game_id)
            .order_by(
                SignalAuditTrail.captured_at.asc(),
                SignalAuditTrail.player_id.asc(),
                SignalAuditTrail.stat_type.asc(),
                SignalAuditTrail.id.asc(),
            )
        )
        .scalars()
        .all()
    )
    return [_build_audit_entry(row) for row in rows]


def get_recent_audit_rows(db: Session, *, limit: int = 50) -> list[SignalAuditEntry]:
    rows = (
        db.execute(
            select(SignalAuditTrail)
            .order_by(SignalAuditTrail.captured_at.desc(), SignalAuditTrail.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [_build_audit_entry(row) for row in rows]
