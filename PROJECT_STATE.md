# Project State

Last updated: 2026-03-12
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
- Rotation sync queue/state exists for durable backfill tracking.
- Postgame enrichment enqueues rotation work instead of fetching it inline.
- Runtime rotation ingestion now uses scraper-backed pages from `nbarotations.info` via `ingestion/rotation_provider.py`.
- The old NBA `GameRotation` runtime path has been removed from `ingestion/nba_client.py`.
- Rotation health reports pending/retry/quarantine counts and recent failure categories.
- Official NBA injury-report PDF ingestion is now live via `ingestion/injury_reports.py`.
- Historical official injury snapshots are stored in normalized DB tables and available to analytics.
- Pregame context prototype data is available through the isolated feature-pack bridge and can feed opportunity features.

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
- Points now consume the shared opportunity backbone.
- Historical pregame line coverage is still too thin for serious edge conclusions.

Most recent broad points backtest after wiring opportunity into the points engine:
- Sample size: `14,547`
- MAE: `5.0822`
- RMSE: `6.5295`
- Bias: `0.4156`
- Within 2 points: about `25.7%`
- Within 4 points: about `48.7%`

Interpretation:
- architecture is cleaner
- points got a small projection improvement
- the next real gains still depend on better opportunity/context quality

### Opportunity Model Snapshot
Most recent injury-aware opportunity backtest on `2026-01-01` through `2026-03-12`:
- Sample size: `9,064`
- Minutes MAE: `4.9556`
- Minutes RMSE: `6.4431`
- Minutes bias: `0.1252`
- Usage MAE: `0.0486`
- Start accuracy: `0.8890`
- Close accuracy: `0.5690`
- Official injury player match pct: `0.0190`
- Official injury team-context pct: `0.3641`

Interpretation:
- injury-aware backtest path is now correctly wired
- official injury data is measurable and no longer meaningfully harmful after the semantic fix
- but it is not yet a strong positive signal because historical player-level attachment is still sparse and coarse

### Miss Profile Summary
Largest opportunity miss buckets in the current top-error sample are roughly:
- minutes spikes
- minutes shortfall
- availability / DNP

Main conclusion:
- role/opportunity modeling still matters more than more point-formula tweaking
- direct player availability and real vacated-role context matter more than generic team injury counts

## Current Phase Progress
### Phase 1: Analytics Architecture
Status: complete

Completed:
- split shared opportunity features from points-specific features
- added standalone opportunity model
- kept points engine separate
- preserved tests and runtime entrypoints

### Phase 2: Rotation Data Layer
Status: complete

Completed:
- added rotation ORM tables:
  - `team_rotation_games`
  - `player_rotation_games`
  - `player_rotation_stints`
- added Alembic migration:
  - `alembic/versions/7d5583207ad0_add_rotation_data_layer.py`
- added writer persistence for rotation tables
- added rotation backlog / health reporting
- added `backfill_historical_rotations()` job
- added `rotation_sync_states` queue table and Alembic migration:
  - `alembic/versions/1f5d5a1f4c4e_add_rotation_sync_states.py`
- added queue bootstrap / selection / retry tracking in:
  - `ingestion/rotation_sync.py`
- changed postgame enrichment to enqueue rotation sync instead of fetching inline
- added separate queue worker:
  - `process_rotation_sync_queue()`
- added scheduler hook for queue processing in:
  - `ingestion/scheduler.py`

### Phase 3: Rotation Backfill And Hardening
Status: complete

Completed:
- replaced runtime `GameRotation` dependency with scraper-backed ingestion from `nbarotations.info`
- added source-specific rotation provider in `ingestion/rotation_provider.py`
- removed old runtime `GameRotation` bundle/fetch logic from `ingestion/nba_client.py`
- preserved queue/backoff/quarantine state machinery
- tightened queue success to require complete normalized rotation coverage for the game
- fixed false failures caused by:
  - low-minute box-score players absent from the scraper page
  - extra fringe scraper players
  - zero-window scraper players
- fixed targeted retry runs so specific game IDs do not get reselected repeatedly across batches
- backfilled all reachable 2025-26 rotation pages
- explicitly classified missing scraper pages as `source_missing_game`
- immediately quarantine source-missing games instead of wasting retries

Operational read:
- the local rotation pipeline is stable
- the dominant remaining misses are source gaps, not parser or DB bugs
- `nbarotations.info` is now a workable primary source for this phase
- rotation data is ready to inform the next modeling step

Current health snapshot:
- `teams`: `30`
- `players`: `5123`
- `games`: `974`
- `historical_game_logs`: `20721`
- `historical_advanced_logs`: `24909`
- `enriched_games`: `955`
- `enrichment_coverage_pct`: `100.0`
- `team_rotation_games`: `1896`
- `player_rotation_games`: `20538`
- `player_rotation_stints`: `64461`
- `rotation_games`: `948`
- `rotation_coverage_pct`: `99.27`
- `rotation_queue_pending`: `0`
- `rotation_queue_retry`: `0`
- `rotation_queue_quarantined`: `7`
- `rotation_recent_failure_counts`:
  - `source_missing_game`: `7`

Known source-missing games:
- `0022500314` - CHI at ORL on 2025-12-01
- `0022500523` - LAL at SAS on 2026-01-07
- `0022500576` - NYK at SAC on 2026-01-14
- `0022500581` - OKC at HOU on 2026-01-15
- `0022500595` - IND at DET on 2026-01-17
- `0022500620` - CLE at CHA on 2026-01-21
- `0022500753` - GSW at LAL on 2026-02-07

## Current Next Phase Gate
### Phase 4: Opportunity Model Improvement
Status: in progress

Completed inside Phase 4 so far:
- added rotation-derived opportunity features and calibration
- wired opportunity outputs into the points model
- added isolated pregame context bridge for projected starters / availability context
- added official NBA injury PDF ingestion and historical backfill
- wired official injury context into runtime and historical opportunity evaluation
- fixed the initial injury-feature semantics so official team summaries no longer masquerade as player-specific `top7/top9` teammate-out signals

Current next work:
- improve player-level pregame availability matching and coverage
- make injury features stronger only when they are player-specific or role-specific
- keep official team summaries as weak context / diagnostics unless better mapping exists
- revisit denser near-tip historical injury snapshots if we need stronger backtest fidelity

## Important Design Decisions
- Shared opportunity backbone, separate stat engines.
- Do not begin live modeling yet.
- Do not expand to rebounds/assists/threes until points pregame structure is trusted.
- Do not assume betting edge quality until we have larger historical line archives.
- Every model change should be isolated and re-backtested.
- Treat sportsbook IDs as adapter IDs, not canonical IDs.
- Keep the scraper source isolated behind a provider layer rather than spreading source-specific logic through jobs/writers.
- Treat official team-level injury counts as weak context, not direct player-opportunity movers.
- Reserve strong minutes/usage shifts for player-specific availability and true vacated-role signals.

## Useful Commands
### Tests
```powershell
E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m unittest E:\dev\projects\bettingbyte-v2\tests\test_pregame_model.py E:\dev\projects\bettingbyte-v2\tests\test_opportunity_model.py E:\dev\projects\bettingbyte-v2\tests\test_rotation_hardening.py -v
```

### Compile checks
```powershell
E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m compileall E:\dev\projects\bettingbyte-v2\database E:\dev\projects\bettingbyte-v2\ingestion E:\dev\projects\bettingbyte-v2\analytics E:\dev\projects\bettingbyte-v2\tests
```

### Migrations
```powershell
E:\dev\projects\bettingbyte-v2\.venv\Scripts\alembic.exe upgrade head
```

### Rotation queue batch
```powershell
from ingestion.jobs import backfill_historical_rotations
print(backfill_historical_rotations(season='2025-26', batch_size=10, max_batches=1))
```

### Direct queue worker
```powershell
from ingestion.jobs import process_rotation_sync_queue
print(process_rotation_sync_queue(season='2025-26', batch_size=10, max_batches=1))
```

### Health report
```powershell
from ingestion.validation import summarize_ingestion_health
print(summarize_ingestion_health())
```

### Queue diagnostics
```powershell
from ingestion.validation import get_rotation_queue_diagnostics
print(get_rotation_queue_diagnostics(season='2025-26'))
```
