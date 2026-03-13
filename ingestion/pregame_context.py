from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from analytics.name_matching import normalize_name
from analytics.pregame_context_loader import (
    build_pregame_context_index,
    load_pregame_context_snapshot_rows,
    match_pregame_context_row,
)
from database.db import session_scope
from database.models import Game, HistoricalGameLog, PlayerPropSnapshot
from ingestion.writer import write_pregame_context_snapshots

FEATURE_PACK_ROOT = Path(__file__).resolve().parent.parent / "pregame_context_feature_pack"
FEATURE_PACK_SRC = FEATURE_PACK_ROOT / "src"
DEFAULT_BASE_DIR = FEATURE_PACK_ROOT / "data" / "pregame_context"
DEFAULT_FEATURES_PATH = DEFAULT_BASE_DIR / "features" / "latest.json"
DEFAULT_TEAM_PRIORS_PATH = FEATURE_PACK_ROOT / "config" / "team_priors.json"


@dataclass(slots=True)
class PregameContextSyncResult:
    payload: dict[str, Any]
    feature_rows: list[dict[str, Any]]
    latest_payload_path: Path
    history_payload_path: Path
    feature_rows_path: Path
    history_feature_rows_path: Path
    attachment_metrics: dict[str, Any]
    captured_at: datetime | None


def sync_pregame_context(
    *,
    base_dir: str | Path | None = None,
    team_priors_path: str | Path | None = None,
    captured_at: datetime | None = None,
    stat_type: str = "points",
) -> PregameContextSyncResult:
    _ensure_feature_pack_importable()
    from nbarotations_scraper import (
        PregameContextIngestor,
        TeamGameRef,
        TeamPriors,
        build_pregame_feature_rows,
        load_team_priors,
        save_feature_rows,
        save_pregame_payload,
    )

    resolved_base_dir = Path(base_dir) if base_dir is not None else DEFAULT_BASE_DIR
    resolved_team_priors = _resolve_team_priors_path(team_priors_path)
    target_games, resolved_captured_at = _load_target_games(captured_at=captured_at, stat_type=stat_type)
    schedule_refs = [TeamGameRef(**game) for game in target_games]

    payload = PregameContextIngestor().fetch(schedule_refs=schedule_refs or None)
    latest_payload_path, history_payload_path = save_pregame_payload(payload, base_dir=resolved_base_dir)

    priors: dict[int, TeamPriors]
    if resolved_team_priors is not None:
        priors = load_team_priors(resolved_team_priors)
    else:
        priors = _build_runtime_team_priors(TeamPriors, captured_at=resolved_captured_at)

    feature_rows = build_pregame_feature_rows(payload, priors_by_team_id=priors)
    feature_rows = _decorate_feature_rows(feature_rows, payload=payload, captured_at=resolved_captured_at)
    feature_rows_path = save_feature_rows(feature_rows, resolved_base_dir / "features" / "latest.json")
    history_feature_rows_path = _save_feature_rows_history(feature_rows, resolved_base_dir / "features" / "history", resolved_captured_at)
    write_pregame_context_snapshots(feature_rows, captured_at=resolved_captured_at)

    attachment_metrics = summarize_pregame_context_attachment(
        feature_rows=feature_rows,
        captured_at=resolved_captured_at,
        stat_type=stat_type,
    )
    return PregameContextSyncResult(
        payload=payload,
        feature_rows=feature_rows,
        latest_payload_path=latest_payload_path,
        history_payload_path=history_payload_path,
        feature_rows_path=feature_rows_path,
        history_feature_rows_path=history_feature_rows_path,
        attachment_metrics=attachment_metrics,
        captured_at=resolved_captured_at,
    )


def summarize_pregame_context_attachment(
    *,
    feature_rows: list[dict[str, Any]] | None = None,
    captured_at: datetime | None = None,
    stat_type: str = "points",
) -> dict[str, Any]:
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
            return {
                "captured_at": None,
                "market_count": 0,
                "attached_count": 0,
                "attached_pct": 0.0,
                "market_game_ids": [],
                "context_game_ids": [],
                "overlap_game_ids": [],
                "missing_context_game_ids": [],
                "expected_start_count": 0,
                "projected_unavailable_count": 0,
                "high_late_scratch_risk_count": 0,
            }

        markets = (
            session.query(PlayerPropSnapshot, Game)
            .outerjoin(Game, Game.game_id == PlayerPropSnapshot.game_id)
            .filter(
                PlayerPropSnapshot.stat_type == stat_type,
                PlayerPropSnapshot.is_live.is_(False),
                PlayerPropSnapshot.captured_at == latest_captured_at,
            )
            .all()
        )
        market_game_ids = sorted({market.game_id for market, _ in markets if market.game_id})

        rows = feature_rows
        if rows is None:
            rows = load_pregame_context_snapshot_rows(session, game_ids=market_game_ids, captured_at=latest_captured_at)
            if not rows:
                rows = _load_feature_rows(DEFAULT_FEATURES_PATH)

        index = build_pregame_context_index(rows)
        context_game_ids = sorted({str(row.get("game_id") or "") for row in rows if row.get("game_id")})
        overlap_game_ids = sorted(set(market_game_ids) & set(context_game_ids))

        attached_count = 0
        expected_start_count = 0
        projected_unavailable_count = 0
        high_late_scratch_risk_count = 0
        coverage_examples: list[dict[str, Any]] = []

        for market, game in markets:
            team_abbr = _resolve_market_team_abbreviation(session, market, game)
            row = match_pregame_context_row(
                index,
                game_id=market.game_id,
                player_id=market.player_id,
                team_abbreviation=team_abbr,
                player_name=market.player_name,
                captured_at=latest_captured_at,
            )
            if row is None:
                continue
            attached_count += 1
            if row.get("expected_start") is True:
                expected_start_count += 1
            if row.get("projected_available") is False or row.get("official_available") is False:
                projected_unavailable_count += 1
            if float(row.get("late_scratch_risk") or 0.0) >= 0.35:
                high_late_scratch_risk_count += 1
            if len(coverage_examples) < 10:
                coverage_examples.append(
                    {
                        "game_id": market.game_id,
                        "player_name": market.player_name,
                        "team": team_abbr,
                        "expected_start": row.get("expected_start"),
                        "projected_available": row.get("projected_available"),
                        "late_scratch_risk": row.get("late_scratch_risk"),
                        "pregame_context_confidence": row.get("pregame_context_confidence"),
                    }
                )

    market_count = len(markets)
    return {
        "captured_at": latest_captured_at.isoformat() if latest_captured_at is not None else None,
        "market_count": market_count,
        "attached_count": attached_count,
        "attached_pct": round(attached_count / market_count, 4) if market_count else 0.0,
        "market_game_ids": market_game_ids,
        "context_game_ids": context_game_ids,
        "overlap_game_ids": overlap_game_ids,
        "overlap_game_count": len(overlap_game_ids),
        "missing_context_game_ids": sorted(set(market_game_ids) - set(context_game_ids)),
        "expected_start_count": expected_start_count,
        "projected_unavailable_count": projected_unavailable_count,
        "high_late_scratch_risk_count": high_late_scratch_risk_count,
        "examples": coverage_examples,
    }


def build_pregame_context_source_payloads(result: PregameContextSyncResult) -> list[dict[str, Any]]:
    captured_at = result.captured_at or _captured_at_from_payload(result.payload)
    return [
        {
            "source": "pregame_context",
            "payload_type": "normalized_payload",
            "external_id": None,
            "context": {
                "latest_payload_path": str(result.latest_payload_path),
                "history_payload_path": str(result.history_payload_path),
            },
            "payload": result.payload,
            "captured_at": captured_at,
        },
        {
            "source": "pregame_context",
            "payload_type": "feature_rows",
            "external_id": None,
            "context": {
                "feature_rows_path": str(result.feature_rows_path),
                "history_feature_rows_path": str(result.history_feature_rows_path),
                "attachment_metrics": result.attachment_metrics,
            },
            "payload": {"rows": result.feature_rows},
            "captured_at": captured_at,
        },
    ]


def _decorate_feature_rows(
    rows: list[dict[str, Any]],
    *,
    payload: dict[str, Any],
    captured_at: datetime | None,
) -> list[dict[str, Any]]:
    source_captured_at = _captured_at_from_payload(payload)
    effective_captured_at = captured_at or source_captured_at
    decorated: list[dict[str, Any]] = []
    for row in rows:
        player_name = row.get("player_name") or ""
        decorated.append(
            {
                **row,
                "team_abbreviation": row.get("team_abbr"),
                "normalized_player_name": normalize_name(player_name) if player_name else None,
                "source_captured_at": source_captured_at,
                "captured_at": effective_captured_at,
            }
        )
    return decorated


def _build_runtime_team_priors(team_priors_cls: Any, *, captured_at: datetime | None) -> dict[int, Any]:
    from analytics.features_opportunity import build_team_role_priors

    role_priors = build_team_role_priors(cutoff=captured_at)
    converted: dict[int, Any] = {}
    for team_id, prior in role_priors.items():
        try:
            converted[int(team_id)] = team_priors_cls(
                top7_player_ids={int(player_id) for player_id in prior.top7_player_ids},
                top9_player_ids={int(player_id) for player_id in prior.top9_player_ids},
                high_usage_player_ids={int(player_id) for player_id in prior.high_usage_player_ids},
                primary_ballhandler_ids={int(player_id) for player_id in prior.primary_ballhandler_ids},
                frontcourt_rotation_player_ids=set(),
                baseline_minutes_by_player_id={int(player_id): float(value) for player_id, value in prior.baseline_minutes_by_player_id.items()},
                baseline_usage_by_player_id={int(player_id): float(value) for player_id, value in prior.baseline_usage_by_player_id.items()},
            )
        except ValueError:
            continue
    return converted


def _save_feature_rows_history(rows: list[dict[str, Any]], history_dir: Path, captured_at: datetime | None) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    timestamp = (captured_at or datetime.utcnow()).strftime("%Y%m%d_%H%M%S")
    history_path = history_dir / f"{timestamp}.json"
    history_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return history_path


def _captured_at_from_payload(payload: dict[str, Any]) -> datetime:
    value = payload.get("fetched_at_utc")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.utcnow()


def _ensure_feature_pack_importable() -> None:
    path = str(FEATURE_PACK_SRC)
    if path not in sys.path:
        sys.path.append(path)


def _resolve_team_priors_path(path: str | Path | None) -> str | Path | None:
    if path is not None:
        return path
    if DEFAULT_TEAM_PRIORS_PATH.exists():
        return DEFAULT_TEAM_PRIORS_PATH
    return None


def _load_feature_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []


def _load_target_games(*, captured_at: datetime | None, stat_type: str) -> tuple[list[dict[str, Any]], datetime | None]:
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
            return [], None

        game_ids = [
            str(game_id)
            for game_id, in session.query(PlayerPropSnapshot.game_id)
            .filter(
                PlayerPropSnapshot.stat_type == stat_type,
                PlayerPropSnapshot.is_live.is_(False),
                PlayerPropSnapshot.captured_at == latest_captured_at,
            )
            .distinct()
            .all()
        ]
        if not game_ids:
            return [], latest_captured_at

        games = {
            game.game_id: game
            for game in session.query(Game).filter(Game.game_id.in_(game_ids)).all()
        }

    refs: list[dict[str, Any]] = []
    for game_id in game_ids:
        game = games.get(game_id)
        if game is None:
            continue
        away_abbr = (game.away_team_abbreviation or "").upper()
        home_abbr = (game.home_team_abbreviation or "").upper()
        if not away_abbr or not home_abbr:
            continue
        refs.append(
            {
                "game_id": game.game_id,
                "away_abbr": away_abbr,
                "home_abbr": home_abbr,
                "away_team_id": _to_int_or_none(game.away_team_id),
                "home_team_id": _to_int_or_none(game.home_team_id),
                "game_time_utc": _isoformat_or_none(game.game_time_utc or game.game_date),
                "game_status": int(game.game_status or 1),
                "game_status_text": game.status_text or "scheduled",
            }
        )
    return refs, latest_captured_at


def _resolve_market_team_abbreviation(session: Any, market: PlayerPropSnapshot, game: Game | None) -> str | None:
    candidate_team = market.team
    candidate_opponent = market.opponent
    latest_log = None

    if not candidate_team or not candidate_opponent:
        cutoff = game.game_time_utc if game and game.game_time_utc else game.game_date if game and game.game_date else market.captured_at
        latest_log = (
            session.query(HistoricalGameLog)
            .filter(HistoricalGameLog.player_id == market.player_id, HistoricalGameLog.game_date < cutoff)
            .order_by(HistoricalGameLog.game_date.desc())
            .limit(1)
            .one_or_none()
        )
        if latest_log is not None:
            candidate_team = candidate_team or latest_log.team
            candidate_opponent = candidate_opponent or latest_log.opponent

    if game is None:
        return candidate_team

    home = game.home_team_abbreviation
    away = game.away_team_abbreviation
    teams = {home, away}

    if candidate_team in teams:
        return candidate_team
    if candidate_opponent in teams:
        return away if candidate_opponent == home else home
    if latest_log is not None and latest_log.team in teams:
        return latest_log.team
    return candidate_team


def _isoformat_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _to_int_or_none(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except Exception:
        return None
