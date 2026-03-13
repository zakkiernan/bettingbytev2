from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from api.schemas import LiveAlert, LiveGameResponse, LiveGameSummary, LivePlayerRow, PaceSummary, TeamBrief

router = APIRouter(prefix="/live", tags=["live"])


CELTICS = TeamBrief(team_id="1610612738", abbreviation="BOS", full_name="Boston Celtics", city="Boston", nickname="Celtics")
HEAT = TeamBrief(team_id="1610612748", abbreviation="MIA", full_name="Miami Heat", city="Miami", nickname="Heat")

LIVE_SUMMARY = LiveGameSummary(
    game_id="0022500099",
    home_team=HEAT,
    away_team=CELTICS,
    home_score=48,
    away_score=54,
    period=2,
    game_clock="4:32",
    live_edge_count=3,
    updated_at=datetime(2026, 3, 13, 1, 15, tzinfo=timezone.utc),
)


@router.get("/active", response_model=list[LiveGameSummary])
def get_active_live_games() -> list[LiveGameSummary]:
    return [LIVE_SUMMARY]


@router.get("/{game_id}", response_model=LiveGameResponse)
def get_live_game(game_id: str) -> LiveGameResponse:
    live_payload = LIVE_SUMMARY.model_dump()
    live_payload["game_id"] = game_id
    return LiveGameResponse(
        **live_payload,
        players=[
            LivePlayerRow(
                player_id="1628369",
                player_name="Jayson Tatum",
                team_abbreviation="BOS",
                stat_type="points",
                line=28.5,
                current_stat=14.0,
                live_projection=30.1,
                pace_projection=29.3,
                live_edge=1.6,
                pregame_projection=29.0,
                on_court=True,
                minutes_played=18.2,
                fouls=1.0,
            )
        ],
        alerts=[
            LiveAlert(
                id="alert-1",
                type="hot_start",
                player_name="Jayson Tatum",
                message="Tatum is tracking above his pregame scoring pace",
                edge_value=1.6,
                created_at=datetime(2026, 3, 13, 1, 14, tzinfo=timezone.utc),
            )
        ],
        pace=PaceSummary(current_pace=102.0, expected_pace=98.5, scoring_impact_pct=3.2),
    )
