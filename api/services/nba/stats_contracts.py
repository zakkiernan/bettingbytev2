from __future__ import annotations

import os
from datetime import datetime
from typing import Literal

CourtStatus = Literal["on", "off"]

DEFAULT_NBA_SEASON = os.getenv("NBA_DEFAULT_SEASON", "2025-26")


def resolve_nba_season(season: str | None = None) -> str:
    return season or DEFAULT_NBA_SEASON


def nba_season_start(season: str | None = None) -> datetime:
    resolved = resolve_nba_season(season)
    start_year_token = resolved.split("-", maxsplit=1)[0]
    start_year = int(start_year_token)
    return datetime(start_year, 10, 1)


def as_percentage_points(value: float | None, *, default: float | None = None) -> float | None:
    if value is None:
        return default

    numeric = float(value)
    if 0.0 <= numeric <= 1.0:
        return numeric * 100.0
    return numeric


def normalize_court_status(value: str | None) -> CourtStatus:
    normalized = (value or "").strip().lower()
    return "off" if normalized == "off" else "on"
