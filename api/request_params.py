from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from fastapi import Path, Query

ID_PATTERN = r"^[A-Za-z0-9._:-]+$"
MAX_ID_LENGTH = 64

StatType: TypeAlias = Literal["points", "rebounds", "assists", "threes"]
TrendStatType: TypeAlias = Literal["points", "rebounds", "assists"]

GameIdPath: TypeAlias = Annotated[
    str,
    Path(min_length=1, max_length=MAX_ID_LENGTH, pattern=ID_PATTERN, description="Canonical NBA game ID"),
]
PlayerIdPath: TypeAlias = Annotated[
    str,
    Path(min_length=1, max_length=MAX_ID_LENGTH, pattern=ID_PATTERN, description="Canonical NBA player ID"),
]
TeamIdPath: TypeAlias = Annotated[
    str,
    Path(min_length=1, max_length=MAX_ID_LENGTH, pattern=ID_PATTERN, description="Canonical NBA team ID"),
]
OptionalGameIdQuery: TypeAlias = Annotated[
    str | None,
    Query(min_length=1, max_length=MAX_ID_LENGTH, pattern=ID_PATTERN, description="Filter to a single game"),
]
OptionalStatTypeQuery: TypeAlias = Annotated[
    StatType | None,
    Query(description="Filter to a specific stat type"),
]
ShotChartGameIdQuery: TypeAlias = Annotated[
    str | None,
    Query(min_length=1, max_length=MAX_ID_LENGTH, pattern=ID_PATTERN, description="Single game filter"),
]
TrendStatTypeQuery: TypeAlias = Annotated[
    TrendStatType,
    Query(description="Stat type: points, rebounds, assists"),
]
SignalHistoryStatTypeQuery: TypeAlias = Annotated[
    StatType,
    Query(description="Stat type: points, rebounds, assists, threes"),
]
