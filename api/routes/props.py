from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from api.schemas import (
    FeatureSnapshot,
    GameLogEntry,
    OpportunityContext,
    PointsBreakdown,
    PropBoardMeta,
    PropBoardResponse,
    PropBoardRow,
    PropDetailResponse,
)

router = APIRouter(prefix="/props", tags=["props"])


MOCK_PROP = PropBoardRow(
    signal_id=1,
    game_id="0022500001",
    game_time_utc=datetime(2026, 3, 13, 23, 30, tzinfo=timezone.utc),
    home_team_abbreviation="DAL",
    away_team_abbreviation="LAL",
    player_id="2544",
    player_name="LeBron James",
    team_abbreviation="LAL",
    stat_type="points",
    line=26.5,
    over_odds=-110,
    under_odds=-110,
    projected_value=29.7,
    edge_over=3.2,
    edge_under=-3.2,
    over_probability=0.632,
    under_probability=0.368,
    confidence=0.81,
    recommended_side="OVER",
    recent_hit_rate=0.8,
    recent_games_count=10,
    key_factor="Stable role, strong matchup environment",
)


@router.get("/board", response_model=PropBoardResponse)
def get_prop_board() -> PropBoardResponse:
    return PropBoardResponse(
        props=[],
        meta=PropBoardMeta(
            total_count=0,
            game_count=0,
            updated_at=datetime.now(timezone.utc),
            stat_types_available=["points"],
        ),
    )


@router.get("/{signal_id}", response_model=PropDetailResponse)
def get_prop_detail(signal_id: int) -> PropDetailResponse:
    prop_payload = MOCK_PROP.model_dump()
    prop_payload["signal_id"] = signal_id
    return PropDetailResponse(
        **prop_payload,
        breakdown=PointsBreakdown(
            base_scoring=25.1,
            recent_form_adjustment=1.8,
            minutes_adjustment=0.4,
            usage_adjustment=0.9,
            efficiency_adjustment=0.2,
            opponent_adjustment=1.2,
            pace_adjustment=0.1,
            context_adjustment=0.0,
            expected_minutes=35.2,
            expected_usage_pct=31.2,
            points_per_minute=0.84,
            projected_points=29.7,
        ),
        opportunity=OpportunityContext(
            expected_minutes=35.2,
            season_minutes_avg=34.8,
            expected_usage_pct=31.2,
            expected_start_rate=0.99,
            expected_close_rate=0.97,
            role_stability=0.88,
            opportunity_score=0.84,
            opportunity_confidence=0.8,
            availability_modifier=0.0,
            vacated_minutes_bonus=0.0,
            vacated_usage_bonus=0.0,
            injury_entries=[],
        ),
        features=FeatureSnapshot(
            team_abbreviation="LAL",
            opponent_abbreviation="DAL",
            is_home=False,
            days_rest=1,
            back_to_back=False,
            sample_size=20,
            season_points_avg=26.8,
            last10_points_avg=28.1,
            last5_points_avg=29.0,
            season_minutes_avg=34.8,
            last10_minutes_avg=35.1,
            last5_minutes_avg=35.6,
            season_usage_pct=30.2,
            opponent_def_rating=113.1,
            opponent_pace=99.2,
            team_pace=100.4,
        ),
        recent_game_log=[
            GameLogEntry(
                game_id="0022400999",
                game_date=datetime(2026, 3, 10, 0, 0, tzinfo=timezone.utc),
                opponent="PHX",
                is_home=True,
                minutes=36.0,
                points=31.0,
                rebounds=8.0,
                assists=9.0,
                steals=1.0,
                blocks=1.0,
                turnovers=3.0,
                threes_made=2.0,
                field_goals_made=11.0,
                field_goals_attempted=19.0,
                free_throws_made=7.0,
                free_throws_attempted=8.0,
                plus_minus=12.0,
            )
        ],
    )
