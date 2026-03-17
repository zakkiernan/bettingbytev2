from __future__ import annotations

from importlib import import_module

_EXPORTS: dict[str, tuple[str, str]] = {
    "PregameOpportunityFeatures": ("analytics.features_opportunity", "PregameOpportunityFeatures"),
    "PregameOpportunityProjection": ("analytics.opportunity_model", "PregameOpportunityProjection"),
    "PregameOpportunityRunResult": ("analytics.analytics", "PregameOpportunityRunResult"),
    "PregameOpportunityBacktestRow": ("analytics.evaluation", "PregameOpportunityBacktestRow"),
    "PregameOpportunityBacktestResult": ("analytics.evaluation", "PregameOpportunityBacktestResult"),
    "PregameOpportunityBacktestSummary": ("analytics.evaluation", "PregameOpportunityBacktestSummary"),
    "PregamePointsFeatures": ("analytics.features_pregame", "PregamePointsFeatures"),
    "PregamePointsProjection": ("analytics.pregame_model", "PregamePointsProjection"),
    "PregamePointsRunResult": ("analytics.analytics", "PregamePointsRunResult"),
    "PregamePointsBacktestRow": ("analytics.evaluation", "PregamePointsBacktestRow"),
    "PregamePointsBacktestResult": ("analytics.evaluation", "PregamePointsBacktestResult"),
    "PregamePointsBacktestSummary": ("analytics.evaluation", "PregamePointsBacktestSummary"),
    "PregameOpportunityMissBucket": ("analytics.diagnostics", "PregameOpportunityMissBucket"),
    "PregameOpportunityMissAnalysis": ("analytics.diagnostics", "PregameOpportunityMissAnalysis"),
    "PregamePointsMissBucket": ("analytics.diagnostics", "PregamePointsMissBucket"),
    "PregamePointsMissAnalysis": ("analytics.diagnostics", "PregamePointsMissAnalysis"),
    "analyze_pregame_opportunity_misses": ("analytics.diagnostics", "analyze_pregame_opportunity_misses"),
    "analyze_pregame_points_misses": ("analytics.diagnostics", "analyze_pregame_points_misses"),
    "build_pregame_opportunity_features": ("analytics.features_opportunity", "build_pregame_opportunity_features"),
    "build_pregame_points_features": ("analytics.features_pregame", "build_pregame_points_features"),
    "project_pregame_opportunity": ("analytics.opportunity_model", "project_pregame_opportunity"),
    "project_pregame_points": ("analytics.pregame_model", "project_pregame_points"),
    "run_pregame_opportunity_backtest": ("analytics.analytics", "run_pregame_opportunity_backtest"),
    "run_pregame_opportunity_pipeline": ("analytics.analytics", "run_pregame_opportunity_pipeline"),
    "run_pregame_points_pipeline": ("analytics.analytics", "run_pregame_points_pipeline"),
    "run_pregame_points_backtest": ("analytics.analytics", "run_pregame_points_backtest"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module 'analytics' has no attribute {name!r}")

    module_name, attribute_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
