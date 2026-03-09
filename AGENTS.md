# Project Working Rules

## Product Scope
- Backend first. Do not spend time on frontend or UX unless explicitly requested.
- Current analytics focus is NBA only.
- Current modeling focus is pregame player points only.
- Do not begin live modeling until the pregame structure is trusted.

## Architecture
- Keep a shared opportunity backbone and separate stat engines.
- Shared layers belong in `analytics/features_opportunity.py` and `analytics/opportunity_model.py`.
- Stat-specific logic belongs in separate modules, starting with `analytics/features_pregame.py` and `analytics/pregame_model.py` for points.
- Do not collapse points, rebounds, assists, and threes into one giant model module.
- Keep ingestion, analytics, evaluation, and API concerns separate.

## Data / Database Rules
- Use Alembic for schema changes. Do not mutate schema at runtime.
- SQLite is the current local DB. Prefer correctness and inspectability over premature infra changes.
- FanDuel is the current test book. Treat it as an adapter, not canonical truth.
- Canonical IDs are NBA game/team/player IDs. Do not let sportsbook IDs leak into canonical joins.

## Modeling Rules
- Transparent baseline first, then calibrate, then expand.
- Opportunity should be modeled before points.
- Every model change should be isolated, measurable, and reversible.
- Keep diagnostics and backtests current with the actual runtime architecture.
- Do not trust betting-edge conclusions until historical line coverage is meaningfully larger.

## Code Quality Rules
- Avoid spaghetti code and hidden coupling.
- Prefer small modules with clear single responsibilities.
- Prefer explicit dataclasses/config objects over magic constants spread through functions.
- Keep debug visibility high: store breakdowns, metrics, and health outputs.
- Do not leave half-wired scaffolding behind.

## Current Phase Order
1. Analytics architecture
2. Rotation data layer
3. Rotation backfill and hardening
4. Opportunity model improvement
5. Refactor pregame points to consume opportunity outputs
6. Recalibrate pregame points
7. Only then revisit live modeling
