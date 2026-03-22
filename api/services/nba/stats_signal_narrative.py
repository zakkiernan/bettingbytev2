from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.narrative import AbsenceStoryEntry, LineupContextNarrative, NarrativeContext
from database.models import AbsenceImpactSummary, Game, OfficialInjuryReportEntry, PregameContextSnapshot


def get_narrative_context(
    db: Session,
    game_id: str,
    player_id: str,
    team_abbreviation: str,
) -> NarrativeContext:
    lineup_context: LineupContextNarrative | None = None

    latest_capture = db.execute(
        select(func.max(PregameContextSnapshot.captured_at)).where(
            PregameContextSnapshot.game_id == game_id,
            PregameContextSnapshot.player_id == player_id,
        )
    ).scalar()

    if latest_capture:
        ctx = db.execute(
            select(PregameContextSnapshot).where(
                PregameContextSnapshot.game_id == game_id,
                PregameContextSnapshot.player_id == player_id,
                PregameContextSnapshot.captured_at == latest_capture,
            )
        ).scalars().first()

        if ctx:
            top7 = int(ctx.teammate_out_count_top7 or 0)
            depletion = "none"
            if top7 >= 3:
                depletion = "severe"
            elif top7 >= 1:
                depletion = "moderate"

            lineup_context = LineupContextNarrative(
                expected_start=ctx.expected_start,
                starter_confidence=ctx.starter_confidence,
                late_scratch_risk=ctx.late_scratch_risk,
                missing_teammates_top7=top7,
                missing_high_usage_teammates=int(ctx.missing_high_usage_teammates or 0),
                missing_primary_ballhandler=ctx.missing_primary_ballhandler,
                missing_frontcourt_rotation_piece=ctx.missing_frontcourt_rotation_piece,
                vacated_minutes_proxy=ctx.vacated_minutes_proxy,
                vacated_usage_proxy=ctx.vacated_usage_proxy,
                pregame_context_confidence=ctx.pregame_context_confidence,
                projected_lineup_confirmed=ctx.projected_lineup_confirmed,
                rotation_depletion=depletion,
            )

    absence_stories: list[AbsenceStoryEntry] = []
    game = db.get(Game, game_id)
    if game and game.game_date:
        game_dt = game.game_date.date() if hasattr(game.game_date, "date") else game.game_date
        out_entries = (
            db.execute(
                select(OfficialInjuryReportEntry)
                .where(
                    OfficialInjuryReportEntry.team_abbreviation == team_abbreviation,
                    OfficialInjuryReportEntry.game_date == game_dt,
                    OfficialInjuryReportEntry.current_status.in_(["Out", "Doubtful"]),
                )
            )
            .scalars()
            .all()
        )

        out_player_ids = {entry.player_id for entry in out_entries if entry.player_id}
        if out_player_ids:
            impact_rows = (
                db.execute(
                    select(AbsenceImpactSummary)
                    .where(
                        AbsenceImpactSummary.beneficiary_player_id == player_id,
                        AbsenceImpactSummary.source_player_id.in_(out_player_ids),
                    )
                    .order_by(func.abs(AbsenceImpactSummary.impact_score).desc())
                    .limit(5)
                )
                .scalars()
                .all()
            )

            out_status_map = {
                entry.player_id: entry.current_status
                for entry in out_entries
                if entry.player_id
            }

            for row in impact_rows:
                absence_stories.append(
                    AbsenceStoryEntry(
                        absent_player_name=row.source_player_name,
                        absent_player_id=row.source_player_id,
                        current_status=out_status_map.get(row.source_player_id),
                        points_delta=row.points_delta,
                        minutes_delta=row.minutes_delta,
                        usage_delta=row.usage_delta,
                        rebounds_delta=row.rebounds_delta,
                        assists_delta=row.assists_delta,
                        games_count=row.source_out_game_count,
                        sample_confidence=row.sample_confidence,
                    )
                )

    return NarrativeContext(
        lineup_context=lineup_context,
        absence_stories=absence_stories,
    )
