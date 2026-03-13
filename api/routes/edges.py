from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from api.schemas import EdgeResponse

router = APIRouter(prefix="/edges", tags=["edges"])


@router.get("/today", response_model=list[EdgeResponse])
def get_edges_today() -> list[EdgeResponse]:
    return [
        EdgeResponse(
            signal_id=1,
            game_id="0022500001",
            game_time_utc=datetime(2026, 3, 13, 23, 30, tzinfo=timezone.utc),
            matchup="LAL @ DAL",
            player_id="2544",
            player_name="LeBron James",
            team_abbreviation="LAL",
            stat_type="points",
            line=26.5,
            projected_value=29.7,
            edge=3.2,
            confidence=0.81,
            recommended_side="OVER",
            key_factor="Opportunity stable with full starter workload",
        )
    ]
