from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, TypeVar

FeatureT = TypeVar("FeatureT")
ProjectionT = TypeVar("ProjectionT")


def generate_model_signals(
    *,
    build_features: Callable[[datetime | None, int | None], list[FeatureT]],
    project: Callable[[FeatureT], ProjectionT],
    captured_at: datetime | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    features = build_features(captured_at, limit)
    return [project(feature).to_signal() for feature in features]


def persist_generated_model_signals(signals: list[dict[str, Any]]) -> int:
    if not signals:
        return 0

    from ingestion.writer import write_model_signals

    write_model_signals(signals)
    return len(signals)
