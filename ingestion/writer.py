from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import MetaData, Table, delete, insert, select, update

from database.db import session_scope
from database.models import (
    Game,
    HistoricalAdvancedLog,
    HistoricalGameLog,
    IngestionRun,
    IngestionRunItem,
    LiveGameSnapshot,
    LivePlayerSnapshot,
    ModelSignal,
    OddsSnapshot,
    OfficialInjuryReport,
    OfficialInjuryReportEntry,
    Player,
    PlayerRotationGame,
    PlayerRotationStint,
    PlayerPropSnapshot,
    PregameContextSnapshot,
    SourcePayload,
    SportsbookEventMap,
    Team,
    TeamDefensiveStat,
    TeamRotationGame,
)

logger = logging.getLogger(__name__)


def _to_json(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, default=str)


def create_ingestion_run(job_name: str, metrics: dict[str, Any] | None = None) -> int:
    with session_scope() as session:
        run = IngestionRun(
            job_name=job_name,
            status="running",
            metrics_json=_to_json(metrics or {}),
        )
        session.add(run)
        session.flush()
        run_id = int(run.id)

    logger.info("Started ingestion run %s for %s", run_id, job_name)
    return run_id


def finalize_ingestion_run(
    run_id: int,
    status: str,
    metrics: dict[str, Any] | None = None,
    error_text: str | None = None,
) -> None:
    with session_scope() as session:
        run = session.get(IngestionRun, run_id)
        if run is None:
            raise ValueError(f"Ingestion run {run_id} was not found")

        run.status = status
        run.finished_at = datetime.utcnow()
        run.metrics_json = _to_json(metrics or {})
        run.error_text = error_text

    logger.info("Finished ingestion run %s with status %s", run_id, status)


def create_ingestion_run_item(
    run_id: int,
    entity_type: str,
    entity_key: str,
    stage: str,
    status: str,
    metrics: dict[str, Any] | None = None,
    error_text: str | None = None,
) -> None:
    with session_scope() as session:
        session.add(
            IngestionRunItem(
                run_id=run_id,
                entity_type=entity_type,
                entity_key=entity_key,
                stage=stage,
                status=status,
                metrics_json=_to_json(metrics),
                error_text=error_text,
            )
        )


def write_source_payloads(payloads: list[dict[str, Any]]) -> None:
    if not payloads:
        return

    with session_scope() as session:
        for payload in payloads:
            session.add(
                SourcePayload(
                    source=payload["source"],
                    payload_type=payload["payload_type"],
                    external_id=payload.get("external_id"),
                    context_json=_to_json(payload.get("context")),
                    payload_json=json.dumps(payload["payload"], sort_keys=True, default=str),
                    captured_at=payload.get("captured_at", datetime.utcnow()),
                )
            )

    logger.info("Inserted %s raw source payloads", len(payloads))


def write_official_injury_report(report: dict[str, Any], entries: list[dict[str, Any]]) -> int:
    with session_scope() as session:
        existing = (
            session.query(OfficialInjuryReport)
            .filter(OfficialInjuryReport.pdf_url == report["pdf_url"])
            .one_or_none()
        )

        if existing is None:
            existing = OfficialInjuryReport(**report)
            session.add(existing)
            session.flush()
        else:
            for field, value in report.items():
                setattr(existing, field, value)
            session.flush()
            session.query(OfficialInjuryReportEntry).filter(OfficialInjuryReportEntry.report_id == existing.id).delete()

        report_id = int(existing.id)
        for entry in entries:
            session.add(OfficialInjuryReportEntry(report_id=report_id, **entry))

    logger.info("Upserted official injury report %s with %s entries", report.get("pdf_url"), len(entries))
    return report_id


def write_pregame_context_snapshots(rows: list[dict[str, Any]], *, captured_at: datetime | None = None) -> None:
    if not rows:
        return

    with session_scope() as session:
        for row in rows:
            row_captured_at = captured_at or row.get("captured_at") or datetime.utcnow()
            existing = (
                session.query(PregameContextSnapshot)
                .filter(
                    PregameContextSnapshot.game_id == str(row["game_id"]),
                    PregameContextSnapshot.player_key == str(row["player_key"]),
                    PregameContextSnapshot.captured_at == row_captured_at,
                )
                .one_or_none()
            )

            payload = {
                "game_id": str(row["game_id"]),
                "team_id": str(row["team_id"]) if row.get("team_id") not in (None, "") else None,
                "team_abbreviation": row.get("team_abbr") or row.get("team_abbreviation"),
                "opponent_team_id": str(row["opponent_team_id"]) if row.get("opponent_team_id") not in (None, "") else None,
                "player_id": str(row["player_id"]) if row.get("player_id") not in (None, "") else None,
                "player_key": str(row["player_key"]),
                "normalized_player_name": row.get("normalized_player_name"),
                "player_name": row.get("player_name"),
                "expected_start": row.get("expected_start"),
                "starter_confidence": float(row["starter_confidence"]) if row.get("starter_confidence") is not None else None,
                "official_available": row.get("official_available"),
                "projected_available": row.get("projected_available"),
                "late_scratch_risk": float(row["late_scratch_risk"]) if row.get("late_scratch_risk") is not None else None,
                "teammate_out_count_top7": float(row["teammate_out_count_top7"]) if row.get("teammate_out_count_top7") is not None else None,
                "teammate_out_count_top9": float(row["teammate_out_count_top9"]) if row.get("teammate_out_count_top9") is not None else None,
                "missing_high_usage_teammates": float(row["missing_high_usage_teammates"]) if row.get("missing_high_usage_teammates") is not None else None,
                "missing_primary_ballhandler": row.get("missing_primary_ballhandler"),
                "missing_frontcourt_rotation_piece": row.get("missing_frontcourt_rotation_piece"),
                "vacated_minutes_proxy": float(row["vacated_minutes_proxy"]) if row.get("vacated_minutes_proxy") is not None else None,
                "vacated_usage_proxy": float(row["vacated_usage_proxy"]) if row.get("vacated_usage_proxy") is not None else None,
                "role_replacement_minutes_proxy": float(row["role_replacement_minutes_proxy"]) if row.get("role_replacement_minutes_proxy") is not None else None,
                "role_replacement_usage_proxy": float(row["role_replacement_usage_proxy"]) if row.get("role_replacement_usage_proxy") is not None else None,
                "role_replacement_touches_proxy": float(row["role_replacement_touches_proxy"]) if row.get("role_replacement_touches_proxy") is not None else None,
                "role_replacement_passes_proxy": float(row["role_replacement_passes_proxy"]) if row.get("role_replacement_passes_proxy") is not None else None,
                "projected_lineup_confirmed": row.get("projected_lineup_confirmed"),
                "official_starter_flag": row.get("official_starter_flag"),
                "pregame_context_confidence": float(row["pregame_context_confidence"]) if row.get("pregame_context_confidence") is not None else None,
                "source_captured_at": row.get("source_captured_at"),
                "captured_at": row_captured_at,
            }

            if existing is not None:
                for field, value in payload.items():
                    setattr(existing, field, value)
                continue

            session.add(PregameContextSnapshot(**payload))

    logger.info("Upserted %s pregame context snapshots", len(rows))



def write_teams(teams: list[dict[str, Any]]) -> None:
    if not teams:
        return

    with session_scope() as session:
        for team in teams:
            existing = session.get(Team, team["team_id"])
            if existing:
                existing.abbreviation = team["abbreviation"]
                existing.full_name = team["full_name"]
                existing.city = team.get("city")
                existing.nickname = team.get("nickname")
                existing.conference = team.get("conference")
                existing.division = team.get("division")
                existing.is_active = team.get("is_active", True)
                continue

            session.add(Team(**team))

    logger.info("Upserted %s teams", len(teams))


def write_players(players: list[dict[str, Any]]) -> None:
    if not players:
        return

    with session_scope() as session:
        for player in players:
            existing = session.get(Player, player["player_id"])
            if existing:
                existing.full_name = player["full_name"]
                existing.first_name = player.get("first_name")
                existing.last_name = player.get("last_name")
                existing.is_active = player.get("is_active", True)
                continue

            session.add(Player(**player))

    logger.info("Upserted %s players", len(players))


def write_games(games: list[dict[str, Any]]) -> None:
    if not games:
        return

    with session_scope() as session:
        for game in games:
            existing = session.get(Game, game["game_id"])
            if existing:
                for field in (
                    "season",
                    "game_date",
                    "home_team_id",
                    "away_team_id",
                    "home_team_abbreviation",
                    "away_team_abbreviation",
                    "game_status",
                    "status_text",
                    "game_time_utc",
                    "is_in_season_tournament",
                ):
                    value = game.get(field)
                    if value is not None:
                        setattr(existing, field, value)
                continue

            session.add(
                Game(
                    game_id=game["game_id"],
                    season=game.get("season"),
                    game_date=game.get("game_date"),
                    home_team_id=game.get("home_team_id"),
                    away_team_id=game.get("away_team_id"),
                    home_team_abbreviation=game.get("home_team_abbreviation"),
                    away_team_abbreviation=game.get("away_team_abbreviation"),
                    game_status=game.get("game_status"),
                    status_text=game.get("status_text"),
                    game_time_utc=game.get("game_time_utc"),
                    is_in_season_tournament=game.get("is_in_season_tournament"),
                )
            )

    logger.info("Upserted %s games", len(games))


def write_sportsbook_event_mappings(event_mappings: list[dict[str, Any]]) -> None:
    if not event_mappings:
        return

    with session_scope() as session:
        for mapping in event_mappings:
            existing = (
                session.query(SportsbookEventMap)
                .filter(
                    SportsbookEventMap.sportsbook == mapping["sportsbook"],
                    SportsbookEventMap.event_id == mapping["event_id"],
                )
                .first()
            )

            if existing:
                existing.event_name = mapping["event_name"]
                existing.nba_game_id = mapping.get("nba_game_id")
                existing.captured_at = mapping.get("captured_at", datetime.utcnow())
                continue

            session.add(
                SportsbookEventMap(
                    sportsbook=mapping["sportsbook"],
                    event_id=mapping["event_id"],
                    event_name=mapping["event_name"],
                    nba_game_id=mapping.get("nba_game_id"),
                    captured_at=mapping.get("captured_at", datetime.utcnow()),
                )
            )

    logger.info("Upserted %s sportsbook event mappings", len(event_mappings))


def write_prop_snapshot(props: list[dict[str, Any]], is_live: bool = False, snapshot_phase: str = "current") -> None:
    if not props:
        return

    with session_scope() as session:
        table = Table("player_prop_snapshots", MetaData(), autoload_with=session.bind)
        has_snapshot_phase = "snapshot_phase" in table.c
        affected_game_ids = sorted({str(prop["game_id"]) for prop in props if prop.get("game_id")})
        incoming_keys = {
            (str(prop["game_id"]), str(prop["player_id"]), str(prop["stat_type"]))
            for prop in props
        }

        for prop in props:
            filters = [
                table.c.game_id == prop["game_id"],
                table.c.player_id == prop["player_id"],
                table.c.stat_type == prop["stat_type"],
                table.c.is_live == is_live,
            ]
            if has_snapshot_phase:
                filters.append(table.c.snapshot_phase == snapshot_phase)

            existing_id = session.execute(
                select(table.c.id).where(*filters).limit(1)
            ).scalar_one_or_none()

            payload = {
                "game_id": prop["game_id"],
                "player_id": prop["player_id"],
                "player_name": prop["player_name"],
                "team": prop.get("team"),
                "opponent": prop.get("opponent"),
                "stat_type": prop["stat_type"],
                "line": prop["line"],
                "over_odds": prop["over_odds"],
                "under_odds": prop["under_odds"],
                "is_live": is_live,
                "captured_at": prop["captured_at"],
            }
            if has_snapshot_phase:
                payload["snapshot_phase"] = snapshot_phase

            if existing_id is not None:
                session.execute(
                    update(table)
                    .where(table.c.id == existing_id)
                    .values(**payload)
                )
                continue

            session.execute(insert(table).values(**payload))

        if affected_game_ids:
            stale_filters = [
                table.c.game_id.in_(affected_game_ids),
                table.c.is_live == is_live,
            ]
            if has_snapshot_phase:
                stale_filters.append(table.c.snapshot_phase == snapshot_phase)

            current_rows = session.execute(
                select(
                    table.c.id,
                    table.c.game_id,
                    table.c.player_id,
                    table.c.stat_type,
                ).where(*stale_filters)
            ).all()

            stale_ids = [
                row.id
                for row in current_rows
                if (str(row.game_id), str(row.player_id), str(row.stat_type)) not in incoming_keys
            ]
            if stale_ids:
                session.execute(delete(table).where(table.c.id.in_(stale_ids)))

    logger.info("Upserted %s player prop snapshots for %s phase", len(props), snapshot_phase)


def write_odds_snapshot(props: list[dict[str, Any]], market_phase: str) -> None:
    if not props:
        return

    with session_scope() as session:
        for prop in props:
            session.add(
                OddsSnapshot(
                    game_id=prop["game_id"],
                    player_id=prop["player_id"],
                    player_name=prop["player_name"],
                    stat_type=prop["stat_type"],
                    line=prop["line"],
                    over_odds=prop["over_odds"],
                    under_odds=prop["under_odds"],
                    source=prop.get("sportsbook", "fanduel"),
                    market_phase=market_phase,
                    captured_at=prop["captured_at"],
                )
            )

    logger.info("Inserted %s odds snapshots for %s phase", len(props), market_phase)


def write_historical_game_logs(game_logs: list[dict[str, Any]]) -> None:
    if not game_logs:
        return

    with session_scope() as session:
        for log in game_logs:
            existing = (
                session.query(HistoricalGameLog)
                .filter(
                    HistoricalGameLog.game_id == log["game_id"],
                    HistoricalGameLog.player_id == log["player_id"],
                )
                .first()
            )

            if existing:
                for field in (
                    "game_date",
                    "player_name",
                    "team",
                    "opponent",
                    "is_home",
                    "minutes",
                    "points",
                    "rebounds",
                    "assists",
                    "steals",
                    "blocks",
                    "turnovers",
                    "threes_made",
                    "threes_attempted",
                    "field_goals_made",
                    "field_goals_attempted",
                    "free_throws_made",
                    "free_throws_attempted",
                    "plus_minus",
                    "fantasy_points",
                ):
                    setattr(existing, field, log.get(field))
                continue

            session.add(
                HistoricalGameLog(
                    game_id=log["game_id"],
                    game_date=log.get("game_date") or datetime.utcnow(),
                    player_id=log["player_id"],
                    player_name=log["player_name"],
                    team=log["team"],
                    opponent=log.get("opponent") or "UNK",
                    is_home=bool(log["is_home"]),
                    minutes=log.get("minutes"),
                    points=log.get("points"),
                    rebounds=log.get("rebounds"),
                    assists=log.get("assists"),
                    steals=log.get("steals"),
                    blocks=log.get("blocks"),
                    turnovers=log.get("turnovers"),
                    threes_made=log.get("threes_made"),
                    threes_attempted=log.get("threes_attempted"),
                    field_goals_made=log.get("field_goals_made"),
                    field_goals_attempted=log.get("field_goals_attempted"),
                    free_throws_made=log.get("free_throws_made"),
                    free_throws_attempted=log.get("free_throws_attempted"),
                    plus_minus=log.get("plus_minus"),
                    fantasy_points=log.get("fantasy_points"),
                )
            )

    logger.info("Upserted %s historical game logs", len(game_logs))


def write_advanced_logs(advanced_logs: list[dict[str, Any]]) -> None:
    if not advanced_logs:
        return

    with session_scope() as session:
        for log in advanced_logs:
            existing = (
                session.query(HistoricalAdvancedLog)
                .filter(
                    HistoricalAdvancedLog.game_id == log["game_id"],
                    HistoricalAdvancedLog.player_id == log["player_id"],
                )
                .first()
            )

            if existing:
                for field, value in log.items():
                    if field in {"game_id", "player_id"} or value is None:
                        continue
                    setattr(existing, field, value)
                continue

            session.add(
                HistoricalAdvancedLog(
                    game_id=log["game_id"],
                    player_id=log["player_id"],
                    player_name=log.get("player_name"),
                    usage_percentage=log.get("usage_percentage"),
                    estimated_usage_percentage=log.get("estimated_usage_percentage"),
                    pace=log.get("pace"),
                    pace_per40=log.get("pace_per40"),
                    possessions=log.get("possessions"),
                    offensive_rating=log.get("offensive_rating"),
                    defensive_rating=log.get("defensive_rating"),
                    net_rating=log.get("net_rating"),
                    true_shooting_percentage=log.get("true_shooting_percentage"),
                    effective_field_goal_percentage=log.get("effective_field_goal_percentage"),
                    assist_percentage=log.get("assist_percentage"),
                    assist_to_turnover=log.get("assist_to_turnover"),
                    offensive_rebound_percentage=log.get("offensive_rebound_percentage"),
                    defensive_rebound_percentage=log.get("defensive_rebound_percentage"),
                    pie=log.get("pie"),
                    speed=log.get("speed"),
                    distance=log.get("distance"),
                    touches=log.get("touches"),
                    passes=log.get("passes"),
                    secondary_assists=log.get("secondary_assists"),
                    free_throw_assists=log.get("free_throw_assists"),
                    rebound_chances_offensive=log.get("rebound_chances_offensive"),
                    rebound_chances_defensive=log.get("rebound_chances_defensive"),
                    rebound_chances_total=log.get("rebound_chances_total"),
                    contested_field_goals_made=log.get("contested_field_goals_made"),
                    contested_field_goals_attempted=log.get("contested_field_goals_attempted"),
                    uncontested_field_goals_made=log.get("uncontested_field_goals_made"),
                    uncontested_field_goals_attempted=log.get("uncontested_field_goals_attempted"),
                    defended_at_rim_field_goals_made=log.get("defended_at_rim_field_goals_made"),
                    defended_at_rim_field_goals_attempted=log.get("defended_at_rim_field_goals_attempted"),
                )
            )

    logger.info("Upserted %s advanced/tracking logs", len(advanced_logs))


def write_team_rotation_games(team_rotation_games: list[dict[str, Any]]) -> None:
    if not team_rotation_games:
        return

    with session_scope() as session:
        for row in team_rotation_games:
            existing = (
                session.query(TeamRotationGame)
                .filter(
                    TeamRotationGame.game_id == row["game_id"],
                    TeamRotationGame.team_id == row["team_id"],
                )
                .first()
            )

            if existing:
                for field, value in row.items():
                    if field in {"game_id", "team_id"}:
                        continue
                    setattr(existing, field, value)
                continue

            session.add(TeamRotationGame(**row))

    logger.info("Upserted %s team rotation summaries", len(team_rotation_games))


def write_player_rotation_games(player_rotation_games: list[dict[str, Any]]) -> None:
    if not player_rotation_games:
        return

    with session_scope() as session:
        for row in player_rotation_games:
            existing = (
                session.query(PlayerRotationGame)
                .filter(
                    PlayerRotationGame.game_id == row["game_id"],
                    PlayerRotationGame.player_id == row["player_id"],
                )
                .first()
            )

            if existing:
                for field, value in row.items():
                    if field in {"game_id", "player_id"}:
                        continue
                    setattr(existing, field, value)
                continue

            session.add(PlayerRotationGame(**row))

    logger.info("Upserted %s player rotation summaries", len(player_rotation_games))


def write_player_rotation_stints(player_rotation_stints: list[dict[str, Any]]) -> None:
    if not player_rotation_stints:
        return

    with session_scope() as session:
        for row in player_rotation_stints:
            existing = (
                session.query(PlayerRotationStint)
                .filter(
                    PlayerRotationStint.game_id == row["game_id"],
                    PlayerRotationStint.player_id == row["player_id"],
                    PlayerRotationStint.stint_number == row["stint_number"],
                )
                .first()
            )

            if existing:
                for field, value in row.items():
                    if field in {"game_id", "player_id", "stint_number"}:
                        continue
                    setattr(existing, field, value)
                continue

            session.add(PlayerRotationStint(**row))

    logger.info("Upserted %s player rotation stints", len(player_rotation_stints))


def write_team_defensive_stats(defensive_stats: list[dict[str, Any]]) -> None:
    if not defensive_stats:
        return

    with session_scope() as session:
        for stat in defensive_stats:
            existing = (
                session.query(TeamDefensiveStat)
                .filter(
                    TeamDefensiveStat.team_id == stat["team_id"],
                    TeamDefensiveStat.season == stat["season"],
                )
                .first()
            )

            if existing:
                for field, value in stat.items():
                    if field in {"team_id", "season"}:
                        continue
                    setattr(existing, field, value)
                continue

            session.add(TeamDefensiveStat(**stat))

    logger.info("Upserted %s team defensive stat rows", len(defensive_stats))


def write_live_game_snapshots(game_snapshots: list[dict[str, Any]]) -> None:
    if not game_snapshots:
        return

    with session_scope() as session:
        for snapshot in game_snapshots:
            session.add(
                LiveGameSnapshot(
                    game_id=snapshot["game_id"],
                    home_team_id=snapshot["home_team_id"],
                    away_team_id=snapshot["away_team_id"],
                    home_team_score=snapshot.get("home_team_score"),
                    away_team_score=snapshot.get("away_team_score"),
                    period=snapshot.get("period"),
                    game_clock=snapshot.get("game_clock"),
                    game_status=snapshot.get("game_status"),
                    status_text=snapshot.get("status_text"),
                    captured_at=snapshot.get("captured_at", datetime.utcnow()),
                )
            )

    logger.info("Inserted %s live game snapshots", len(game_snapshots))


def write_live_player_snapshots(player_snapshots: list[dict[str, Any]]) -> None:
    if not player_snapshots:
        return

    with session_scope() as session:
        for snapshot in player_snapshots:
            session.add(
                LivePlayerSnapshot(
                    game_id=snapshot["game_id"],
                    player_id=snapshot["player_id"],
                    player_name=snapshot["player_name"],
                    team_id=snapshot["team_id"],
                    minutes=snapshot.get("minutes"),
                    points=snapshot.get("points"),
                    rebounds=snapshot.get("rebounds"),
                    assists=snapshot.get("assists"),
                    steals=snapshot.get("steals"),
                    blocks=snapshot.get("blocks"),
                    turnovers=snapshot.get("turnovers"),
                    field_goals_made=snapshot.get("field_goals_made"),
                    field_goals_attempted=snapshot.get("field_goals_attempted"),
                    threes_made=snapshot.get("threes_made"),
                    threes_attempted=snapshot.get("threes_attempted"),
                    free_throws_made=snapshot.get("free_throws_made"),
                    free_throws_attempted=snapshot.get("free_throws_attempted"),
                    fouls=snapshot.get("fouls"),
                    plus_minus=snapshot.get("plus_minus"),
                    on_court=snapshot.get("on_court"),
                    starter=snapshot.get("starter"),
                    captured_at=snapshot.get("captured_at", datetime.utcnow()),
                )
            )

    logger.info("Inserted %s live player snapshots", len(player_snapshots))


def write_model_signals(signals: list[dict[str, Any]]) -> None:
    if not signals:
        return

    with session_scope() as session:
        for signal in signals:
            session.add(
                ModelSignal(
                    model_name=signal["model_name"],
                    model_version=signal["model_version"],
                    market_phase=signal["market_phase"],
                    sportsbook=signal.get("sportsbook", "fanduel"),
                    game_id=signal["game_id"],
                    player_id=signal["player_id"],
                    player_name=signal["player_name"],
                    stat_type=signal["stat_type"],
                    line=signal["line"],
                    projected_value=signal["projected_value"],
                    over_probability=signal.get("over_probability"),
                    under_probability=signal.get("under_probability"),
                    edge_over=signal.get("edge_over"),
                    edge_under=signal.get("edge_under"),
                    confidence=signal.get("confidence"),
                    recommended_side=signal.get("recommended_side"),
                    metadata_json=signal.get("metadata_json"),
                    created_at=signal.get("created_at", datetime.utcnow()),
                )
            )

    logger.info("Inserted %s model signals", len(signals))


