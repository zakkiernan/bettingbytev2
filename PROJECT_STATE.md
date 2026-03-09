# Project State

Last updated: 2026-03-09
Project root: `E:\dev\projects\bettingbyte-v2`

## Product Goal
Sellable NBA betting analytics product with:
- pregame signals
- stronger live betting analytics later

Current priority is backend only:
- ingestion reliability
- database structure
- analytics foundation
- pregame points model before any live model work

## Current Backend Status
### Ingestion / Database
- Alembic is in place and managing schema.
- Historical game-log ingestion is complete.
- Historical advanced/tracking enrichment is complete.
- Canonical historical game coverage is complete.
- Live and pregame market/state ingestion are working.
- FanDuel remains the current test sportsbook adapter.

### Analytics
- Pregame analytics architecture is split into:
  - shared opportunity layer
  - separate points engine
  - evaluation and diagnostics layers
- Current shared opportunity modules:
  - `analytics/features_opportunity.py`
  - `analytics/opportunity_model.py`
- Current points modules:
  - `analytics/features_pregame.py`
  - `analytics/pregame_model.py`
- Evaluation/diagnostics:
  - `analytics/evaluation.py`
  - `analytics/diagnostics.py`

## Current Modeling State
### Pregame Points Baseline
- Transparent baseline model exists and runs.
- Backtest is projection-quality, not true betting-edge quality.
- Historical pregame line coverage is still too thin for serious edge conclusions.

Most recent broad projection backtest baseline after conservative opponent calibration:
- Sample size: `14,547`
- MAE: `5.0843`
- RMSE: `6.5387`
- Bias: `0.3972`
- Within 2 points: about `25.5%`
- Within 4 points: about `48.8%`

Interpretation:
- model infrastructure is real
- model quality is not good enough yet
- biggest missing concept is pregame opportunity / role expectation

### Miss Profile Summary
Largest miss buckets in top-error sample were roughly:
- scoring outlier upside
- minutes spikes
- opponent-adjustment heavy cases
- minutes shortfall

Main conclusion:
- role/opportunity modeling matters more right now than more point-formula tweaking

## Current Phase Progress
### Phase 1: Analytics Architecture
Status: complete

Completed:
- split shared opportunity features from points-specific features
- added standalone opportunity model
- kept points engine separate
- preserved tests and runtime entrypoints

### Phase 2: Rotation Data Layer
Status: complete as a backend layer

Completed:
- added rotation ORM tables:
  - `team_rotation_games`
  - `player_rotation_games`
  - `player_rotation_stints`
- added Alembic migration:
  - `alembic/versions/7d5583207ad0_add_rotation_data_layer.py`
- added normalized rotation bundle in `ingestion/nba_client.py`
- added writer persistence for rotation tables
- added rotation backlog / health reporting
- added `backfill_historical_rotations()` job
- postgame enrichment now also attempts rotation sync

Smoke-tested:
- one-game rotation backfill succeeded
- wrote:
  - `team_rotation_games: 2`
  - `player_rotation_games: 27`
  - `player_rotation_stints: 85`

Current health snapshot after phase 2 smoke test:
- `teams`: `30`
- `players`: `5123`
- `games`: `974`
- `historical_game_logs`: `20721`
- `historical_advanced_logs`: `24909`
- `enriched_games`: `955`
- `enrichment_coverage_pct`: `100.0`
- `team_rotation_games`: `2`
- `player_rotation_games`: `27`
- `player_rotation_stints`: `85`
- `rotation_games`: `1`
- `rotation_coverage_pct`: `0.1`

## Next Phase
### Phase 3: Rotation Backfill And Hardening
Goal:
- backfill historical rotation data across the season
- validate endpoint reliability
- make rotation coverage a real modeling input, not just a smoke-tested table set

Expected work:
- run chunked `backfill_historical_rotations()`
- inspect failures/timeouts
- verify rerun safety and idempotency
- improve retry behavior if `GameRotation` is noisy
- get rotation coverage meaningfully above `0.1%`

## Important Design Decisions
- Shared opportunity backbone, separate stat engines.
- Do not begin live modeling yet.
- Do not expand to rebounds/assists/threes until points pregame structure is trusted.
- Do not assume betting edge quality until we have larger historical line archives.
- Every model change should be isolated and re-backtested.

## Useful Commands
### Tests
```powershell
E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m unittest E:\dev\projects\bettingbyte-v2\tests\test_pregame_model.py E:\dev\projects\bettingbyte-v2\tests\test_opportunity_model.py -v
```

### Compile checks
```powershell
E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m compileall E:\dev\projects\bettingbyte-v2\database E:\dev\projects\bettingbyte-v2\ingestion E:\dev\projects\bettingbyte-v2\analytics E:\dev\projects\bettingbyte-v2\tests
```

### Migrations
```powershell
E:\dev\projects\bettingbyte-v2\.venv\Scripts\alembic.exe upgrade head
```

### Rotation smoke test
```powershell
from ingestion.jobs import backfill_historical_rotations
print(backfill_historical_rotations(batch_size=1, max_batches=1, specific_game_ids=['0022500868']))
```

### Health report
```powershell
from ingestion.validation import summarize_ingestion_health
print(summarize_ingestion_health())
```
