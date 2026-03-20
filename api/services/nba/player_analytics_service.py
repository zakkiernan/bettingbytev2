from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.absence_impact import AbsenceImpactEntry, AbsenceImpactResponse
from api.schemas.advanced_trends import AdvancedTrendPoint, AdvancedTrendsResponse
from api.schemas.rotation import RotationGameEntry, RotationProfile
from database.models import (
    AbsenceImpactSummary,
    HistoricalAdvancedLog,
    HistoricalGameLog,
    Player,
    PlayerRotationGame,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEASON_START = datetime(2025, 10, 1)


# ---------------------------------------------------------------------------
# Advanced Trends
# ---------------------------------------------------------------------------


def get_advanced_trends(
    db: Session,
    player_id: str,
    limit: int = 20,
) -> AdvancedTrendsResponse | None:
    """Return per-game advanced stats joined with basic game context."""
    player = db.get(Player, player_id)
    if player is None:
        return None

    # Join HistoricalAdvancedLog with HistoricalGameLog for game_date/opponent
    stmt = (
        select(HistoricalAdvancedLog, HistoricalGameLog)
        .join(
            HistoricalGameLog,
            (HistoricalAdvancedLog.game_id == HistoricalGameLog.game_id)
            & (HistoricalAdvancedLog.player_id == HistoricalGameLog.player_id),
        )
        .where(
            HistoricalAdvancedLog.player_id == player_id,
            HistoricalGameLog.game_date >= _SEASON_START,
        )
        .order_by(HistoricalGameLog.game_date.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()

    points = [
        AdvancedTrendPoint(
            game_id=adv.game_id,
            game_date=gl.game_date,
            opponent=gl.opponent,
            is_home=gl.is_home,
            minutes=float(gl.minutes or 0.0),
            usage_percentage=adv.usage_percentage,
            true_shooting_percentage=adv.true_shooting_percentage,
            effective_field_goal_percentage=adv.effective_field_goal_percentage,
            pace=adv.pace,
            offensive_rating=adv.offensive_rating,
            defensive_rating=adv.defensive_rating,
            net_rating=adv.net_rating,
            touches=adv.touches,
            passes=adv.passes,
            pie=adv.pie,
        )
        for adv, gl in rows
    ]

    return AdvancedTrendsResponse(
        player_id=player_id,
        player_name=player.full_name,
        game_count=len(points),
        points=points,
    )


# ---------------------------------------------------------------------------
# Rotation Profile
# ---------------------------------------------------------------------------


def get_rotation_profile(
    db: Session,
    player_id: str,
    limit: int = 20,
) -> RotationProfile | None:
    """Return rotation role data with aggregate rates."""
    player = db.get(Player, player_id)
    if player is None:
        return None

    # Join with HistoricalGameLog for game_date/opponent
    stmt = (
        select(PlayerRotationGame, HistoricalGameLog)
        .join(
            HistoricalGameLog,
            (PlayerRotationGame.game_id == HistoricalGameLog.game_id)
            & (PlayerRotationGame.player_id == HistoricalGameLog.player_id),
        )
        .where(
            PlayerRotationGame.player_id == player_id,
            HistoricalGameLog.game_date >= _SEASON_START,
        )
        .order_by(HistoricalGameLog.game_date.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()

    if not rows:
        return RotationProfile(
            player_id=player_id,
            player_name=player.full_name,
        )

    recent_games = []
    starts = 0
    closes = 0
    total_stints = 0.0
    total_seconds = 0.0
    n = len(rows)

    for rot, gl in rows:
        recent_games.append(
            RotationGameEntry(
                game_id=rot.game_id,
                game_date=gl.game_date,
                opponent=gl.opponent,
                started=rot.started,
                closed_game=rot.closed_game,
                stint_count=rot.stint_count,
                total_shift_duration_real=rot.total_shift_duration_real,
                avg_shift_duration_real=rot.avg_shift_duration_real,
            )
        )
        if rot.started:
            starts += 1
        if rot.closed_game:
            closes += 1
        total_stints += float(rot.stint_count or 0)
        total_seconds += float(rot.total_shift_duration_real or 0.0)

    return RotationProfile(
        player_id=player_id,
        player_name=player.full_name,
        games_tracked=n,
        start_rate=round(starts / n, 3) if n else 0.0,
        close_rate=round(closes / n, 3) if n else 0.0,
        avg_stint_count=round(total_stints / n, 2) if n else 0.0,
        avg_minutes=round(total_seconds / n / 600, 1) if n else 0.0,
        recent_games=recent_games,
    )


# ---------------------------------------------------------------------------
# Absence Impact
# ---------------------------------------------------------------------------


def get_absence_impact(
    db: Session,
    player_id: str,
) -> AbsenceImpactResponse | None:
    """Return absence impact data: who benefits when this player sits, and
    how this player benefits when teammates sit."""
    player = db.get(Player, player_id)
    if player is None:
        return None

    def _to_entry(row: AbsenceImpactSummary) -> AbsenceImpactEntry:
        return AbsenceImpactEntry(
            source_player_id=row.source_player_id,
            source_player_name=row.source_player_name,
            beneficiary_player_id=row.beneficiary_player_id,
            beneficiary_player_name=row.beneficiary_player_name,
            team_abbreviation=row.team_abbreviation,
            points_delta=row.points_delta,
            rebounds_delta=row.rebounds_delta,
            assists_delta=row.assists_delta,
            minutes_delta=row.minutes_delta,
            usage_delta=row.usage_delta,
            touches_delta=row.touches_delta,
            source_out_game_count=row.source_out_game_count,
            beneficiary_active_game_count=row.beneficiary_active_game_count,
            impact_score=row.impact_score,
            sample_confidence=row.sample_confidence,
        )

    # When this player sits → who benefits?
    when_sits = (
        db.execute(
            select(AbsenceImpactSummary)
            .where(AbsenceImpactSummary.source_player_id == player_id)
            .order_by(func.abs(AbsenceImpactSummary.impact_score).desc())
            .limit(15)
        )
        .scalars()
        .all()
    )

    # When teammates sit → how does this player benefit?
    when_others = (
        db.execute(
            select(AbsenceImpactSummary)
            .where(AbsenceImpactSummary.beneficiary_player_id == player_id)
            .order_by(func.abs(AbsenceImpactSummary.impact_score).desc())
            .limit(15)
        )
        .scalars()
        .all()
    )

    return AbsenceImpactResponse(
        player_id=player_id,
        player_name=player.full_name,
        when_player_sits=[_to_entry(r) for r in when_sits],
        when_others_sit=[_to_entry(r) for r in when_others],
    )
