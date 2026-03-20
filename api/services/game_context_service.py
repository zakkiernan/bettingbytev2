from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.detail import InjuryEntry
from api.schemas.game_context import (
    GameContextResponse,
    LineupEntry,
    TeamDefenseSnapshot,
    TeamGameContext,
)
from database.models import (
    Game,
    OfficialInjuryReportEntry,
    PregameContextSnapshot,
    Team,
    TeamDefensiveStat,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CURRENT_SEASON = "2025-26"


def _build_team_context(
    db: Session,
    game_id: str,
    team_abbreviation: str,
    team_name: str | None,
    game_date: date | None,
) -> TeamGameContext:
    """Build the full context for one team in a game."""

    # --- Expected lineup from PregameContextSnapshot ---
    # Get the latest capture for this game/team
    latest_capture = db.execute(
        select(func.max(PregameContextSnapshot.captured_at)).where(
            PregameContextSnapshot.game_id == game_id,
            PregameContextSnapshot.team_abbreviation == team_abbreviation,
        )
    ).scalar()

    expected_lineup: list[LineupEntry] = []
    teammate_out_top7: float | None = None
    teammate_out_top9: float | None = None

    if latest_capture:
        ctx_rows = (
            db.execute(
                select(PregameContextSnapshot).where(
                    PregameContextSnapshot.game_id == game_id,
                    PregameContextSnapshot.team_abbreviation == team_abbreviation,
                    PregameContextSnapshot.captured_at == latest_capture,
                )
            )
            .scalars()
            .all()
        )
        for ctx in ctx_rows:
            expected_lineup.append(
                LineupEntry(
                    player_id=ctx.player_id,
                    player_name=ctx.player_name,
                    expected_start=ctx.expected_start,
                    starter_confidence=ctx.starter_confidence,
                    late_scratch_risk=ctx.late_scratch_risk,
                    official_available=ctx.official_available,
                    projected_available=ctx.projected_available,
                )
            )
            # Take the first non-null value for team-level counts
            if teammate_out_top7 is None and ctx.teammate_out_count_top7 is not None:
                teammate_out_top7 = ctx.teammate_out_count_top7
            if teammate_out_top9 is None and ctx.teammate_out_count_top9 is not None:
                teammate_out_top9 = ctx.teammate_out_count_top9

        # Sort: expected starters first, then by confidence
        expected_lineup.sort(
            key=lambda e: (not (e.expected_start or False), -(e.starter_confidence or 0)),
        )

    # --- Injury entries ---
    injury_entries: list[InjuryEntry] = []
    if game_date:
        inj_rows = (
            db.execute(
                select(OfficialInjuryReportEntry)
                .where(
                    OfficialInjuryReportEntry.team_abbreviation == team_abbreviation,
                    OfficialInjuryReportEntry.game_date == game_date,
                )
                .order_by(OfficialInjuryReportEntry.report_datetime_utc.desc())
            )
            .scalars()
            .all()
        )
        # Deduplicate by player — keep the most recent report entry
        seen_players: set[str] = set()
        for inj in inj_rows:
            player_key = inj.player_name or inj.player_id or ""
            if player_key in seen_players:
                continue
            seen_players.add(player_key)
            if inj.current_status and inj.player_name:
                injury_entries.append(
                    InjuryEntry(
                        player_name=inj.player_name,
                        team_abbreviation=inj.team_abbreviation or team_abbreviation,
                        current_status=inj.current_status,
                        reason=inj.reason or "",
                    )
                )

    # --- Team defense ---
    defense: TeamDefenseSnapshot | None = None
    def_row = db.execute(
        select(TeamDefensiveStat).where(
            TeamDefensiveStat.team_name == team_name,
            TeamDefensiveStat.season == _CURRENT_SEASON,
        )
    ).scalars().first()

    # Fallback: try by abbreviation in team_name field
    if def_row is None:
        team_obj = db.execute(
            select(Team).where(Team.abbreviation == team_abbreviation)
        ).scalars().first()
        if team_obj:
            def_row = db.execute(
                select(TeamDefensiveStat).where(
                    TeamDefensiveStat.team_id == team_obj.team_id,
                    TeamDefensiveStat.season == _CURRENT_SEASON,
                )
            ).scalars().first()

    if def_row:
        defense = TeamDefenseSnapshot(
            defensive_rating=def_row.defensive_rating,
            pace=def_row.pace,
            opponent_points_per_game=def_row.opponent_points_per_game,
            opponent_field_goal_percentage=def_row.opponent_field_goal_percentage,
            opponent_three_point_percentage=def_row.opponent_three_point_percentage,
        )

    return TeamGameContext(
        team_abbreviation=team_abbreviation,
        team_name=team_name,
        expected_lineup=expected_lineup,
        injury_entries=injury_entries,
        defense=defense,
        teammate_out_count_top7=teammate_out_top7,
        teammate_out_count_top9=teammate_out_top9,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_game_context(db: Session, game_id: str) -> GameContextResponse | None:
    """Build full pregame context for a game: both teams' lineups, injuries, defense."""
    game = db.get(Game, game_id)
    if game is None:
        return None

    # Resolve team names
    home_name: str | None = None
    away_name: str | None = None
    team_ids = {game.home_team_id, game.away_team_id} - {None}
    if team_ids:
        teams = {
            t.team_id: t
            for t in db.execute(
                select(Team).where(Team.team_id.in_(team_ids))
            ).scalars().all()
        }
        if game.home_team_id and game.home_team_id in teams:
            home_name = teams[game.home_team_id].full_name
        if game.away_team_id and game.away_team_id in teams:
            away_name = teams[game.away_team_id].full_name

    game_dt = game.game_date.date() if game.game_date else None

    home_ctx = _build_team_context(
        db, game_id,
        game.home_team_abbreviation or "???",
        home_name,
        game_dt,
    )
    away_ctx = _build_team_context(
        db, game_id,
        game.away_team_abbreviation or "???",
        away_name,
        game_dt,
    )

    # Pace matchup: average of both teams
    pace_matchup: float | None = None
    if home_ctx.defense and away_ctx.defense:
        hp = home_ctx.defense.pace
        ap = away_ctx.defense.pace
        if hp is not None and ap is not None:
            pace_matchup = round((hp + ap) / 2, 1)

    return GameContextResponse(
        game_id=game_id,
        game_date=game.game_date,
        game_time_utc=game.game_time_utc,
        home_team=home_ctx,
        away_team=away_ctx,
        pace_matchup=pace_matchup,
    )
