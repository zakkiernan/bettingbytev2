from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from analytics.evaluation import PregamePointsBacktestResult, backtest_pregame_points
from analytics.features_opportunity import build_pregame_opportunity_features
from analytics.opportunity_model import project_pregame_opportunity
from analytics.pregame_model import MODEL_NAME, MODEL_VERSION, generate_pregame_points_signals


@dataclass(slots=True)
class PregamePointsRunResult:
    model_name: str
    model_version: str
    market_count: int
    generated_signal_count: int
    recommended_signal_count: int
    persisted: bool
    captured_at: datetime | None
    completed_at: datetime


@dataclass(slots=True)
class PregameOpportunityRunResult:
    feature_count: int
    projection_count: int
    captured_at: datetime | None
    completed_at: datetime


def run_pregame_points_pipeline(*, captured_at: datetime | None = None, limit: int | None = None, persist: bool = False) -> PregamePointsRunResult:
    signals = generate_pregame_points_signals(captured_at=captured_at, limit=limit, persist=persist)
    return PregamePointsRunResult(
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        market_count=len(signals),
        generated_signal_count=len(signals),
        recommended_signal_count=sum(1 for signal in signals if signal["recommended_side"] is not None),
        persisted=persist,
        captured_at=captured_at,
        completed_at=datetime.utcnow(),
    )


def run_pregame_opportunity_pipeline(*, captured_at: datetime | None = None, stat_type: str = "points", limit: int | None = None) -> PregameOpportunityRunResult:
    features = build_pregame_opportunity_features(captured_at=captured_at, stat_type=stat_type, limit=limit)
    projections = [project_pregame_opportunity(feature) for feature in features]
    return PregameOpportunityRunResult(
        feature_count=len(features),
        projection_count=len(projections),
        captured_at=captured_at,
        completed_at=datetime.utcnow(),
    )


def run_pregame_points_backtest(*, start_date: datetime | None = None, end_date: datetime | None = None, min_history: int = 8, limit: int | None = None) -> PregamePointsBacktestResult:
    return backtest_pregame_points(start_date=start_date, end_date=end_date, min_history=min_history, limit=limit)
