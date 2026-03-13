from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from api.schemas import GameLogEntry, PlayerProfileResponse, PropBoardRow, SeasonAverages, TrendPoint

router = APIRouter(prefix="/players", tags=["players"])


ACTIVE_PROP = PropBoardRow(
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
    key_factor="Recent form and matchup both trend positive",
)

PROFILE = PlayerProfileResponse(
    player_id="2544",
    full_name="LeBron James",
    first_name="LeBron",
    last_name="James",
    team_abbreviation="LAL",
    team_full_name="Los Angeles Lakers",
    season_averages=SeasonAverages(
        games_played=58,
        ppg=26.8,
        rpg=7.2,
        apg=8.1,
        mpg=34.8,
        fg_pct=0.516,
        three_pct=0.381,
        ft_pct=0.742,
        usage_pct=30.2,
        ts_pct=0.618,
    ),
    active_props=[ACTIVE_PROP],
)


@router.get("/{player_id}", response_model=PlayerProfileResponse)
def get_player_profile(player_id: str) -> PlayerProfileResponse:
    return PROFILE.model_copy(update={"player_id": player_id})


@router.get("/{player_id}/props", response_model=list[PropBoardRow])
def get_player_props(player_id: str) -> list[PropBoardRow]:
    return [ACTIVE_PROP.model_copy(update={"player_id": player_id})]


@router.get("/{player_id}/game-log", response_model=list[GameLogEntry])
def get_player_game_log(player_id: str) -> list[GameLogEntry]:
    return [
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
    ]


@router.get("/{player_id}/trends", response_model=list[TrendPoint])
def get_player_trends(player_id: str) -> list[TrendPoint]:
    return [
        TrendPoint(
            game_date=datetime(2026, 3, 10, 0, 0, tzinfo=timezone.utc),
            value=31.0,
            line=26.5,
            hit=True,
        )
    ]
