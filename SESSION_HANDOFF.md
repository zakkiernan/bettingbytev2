# SESSION_HANDOFF.md

## Session Date
2026-03-19

## Current Priority

Pregame reliability is still the priority. The codebase is now namespaced for multi-sport growth: shared infrastructure stays in common/shared packages, NBA-specific code lives under `nba/`, and MLB stubs are in place for the next sport without changing today's business logic.

## What Was Completed

### Stats contract cleanup for new NBA data surfaces

Focused cleanup landed across the new game/player/team stats surfaces to reduce wiring drift between ingestion, API, and frontend consumers.

What changed:
- added `api/services/nba/stats_contracts.py` as a small shared contract layer for:
  - default NBA season resolution
  - NBA season start derivation
  - probability normalization to percentage points
  - canonical on/off status normalization
- removed duplicated hardcoded season handling from:
  - `api/services/nba/player_stats_service.py`
  - `api/services/nba/team_stats_service.py`
  - `api/services/nba/player_service.py`
  - `api/services/nba/game_context_service.py`
- fixed win-probability API shaping so decimal probabilities are normalized into percentage points before they hit the frontend chart
- fixed player shot-chart `last_n` behavior so recency is based on actual game date/time instead of row insertion time
- normalized on/off API responses to lowercase `on` / `off` and aligned the frontend consumer to that contract
- fixed defensive tracking UI deltas so `pct_plusminus` is treated consistently as a decimal differential instead of mixing decimal and whole-percent assumptions
- fixed lineup spotlight qualification to use per-game minutes, matching the lineup endpoint's `PerGame` ingestion mode

Regression coverage added:
- `tests/nba/test_stats_services.py`
  - win probability contract normalization
  - shot-chart recency ordering
  - on/off status normalization

Verification:
- `E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m pytest tests/ -q` -> `173 passed`
- `E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m compileall analytics api ingestion database tests` -> success

Frontend verification note:
- attempted frontend build verification
- `pnpm` is not installed in the current environment
- `npm run build` could not be completed because the local tool sandbox errored during command setup

### NBA ingestion now pulls 12 additional stats.nba.com endpoints

Added 12 new NBA ingestion surfaces across the existing client -> writer -> job -> scheduler pipeline:

Postgame enrichment per game:
- shot chart detail
- hustle boxscore
- matchup boxscore
- win probability play-by-play

Daily season-level jobs:
- player clutch stats
- player hustle stats
- synergy play types
- player tracking season stats (`CatchShoot`, `PullUpShot`, `Drives`)
- player on/off stats
- player defensive tracking
- player shot locations
- lineup stats

Database/runtime changes:
- added 12 new SQLAlchemy models in `database/models/nba.py`
- added matching writer upserts in `ingestion/common/writer.py`
- added new bundle functions in `ingestion/nba/nba_client.py`
- wired new daily jobs in `ingestion/nba/jobs.py`
- scheduled the new daily jobs in `ingestion/common/scheduler.py`
- extended postgame enrichment so finished games now also archive the four new per-game feeds
- generated a new Alembic migration: `alembic/versions/f4a95813c268_add_extended_nba_stats_ingestion_tables.py`

Implementation notes:
- all new client calls use `_call_with_retries(...)`
- all calls apply rate limiting after each request
- player on/off uses a heavier delay because it loops over all 30 teams
- shot-location parsing handles the grouped zone-header response shape from `LeagueDashPlayerShotLocations`
- synergy play types currently uses a single empty `play_type_nullable=""` request because the current nba_api response returns all play types in one payload

Verification:
- `E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m pytest tests/ -q` -> `165 passed`
- `E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m compileall analytics api ingestion database tests` -> success
- targeted syntax check passed for the modified client, jobs, writer, scheduler, models, and migration files

### Backend and frontend were restructured for sport namespaces

Backend layout changes:
- shared analytics moved under `analytics/common/`
- NBA analytics moved under `analytics/nba/`
- shared ingestion moved under `ingestion/common/`
- NBA ingestion moved under `ingestion/nba/`
- NBA API routes, schemas, and services moved under `api/routes/nba/`, `api/schemas/nba/`, and `api/services/nba/`
- database models now live in the `database/models/` package with `common.py`, `nba.py`, and an MLB stub
- `api/main.py` now mounts NBA routes at `/api/nba/*` and also keeps the old `/api/*` paths working for backward compatibility

Compatibility strategy:
- every old Python module path that moved now exists as a shim that aliases the real module object
- this preserves old imports like `from analytics.pregame_model import ...`
- it also preserves monkeypatching and private-helper imports used by tests

Frontend layout changes:
- NBA pages moved under `frontend/src/app/(app)/nba/`
- legacy `/games`, `/live`, `/props`, and `/player` pages now redirect to the new `/nba/...` routes
- shared types were split into `frontend/src/types/common.ts`
- NBA types now live in `frontend/src/types/nba.ts`
- `frontend/src/types/api.ts` is now a backward-compat re-export shim
- `frontend/src/lib/nba-api.ts` now targets `/api/nba`
- `frontend/src/lib/api.ts` remains the shared entrypoint and re-exports NBA fetchers
- navigation and the app shell now expose an explicit sport selector/context

Verification:
- `E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m pytest tests/ -q` -> `165 passed`
- `E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m compileall analytics api ingestion database tests` -> success
- local API smoke checks:
  - `GET /api/nba/games/today` -> `200`
  - `GET /api/games/today` -> `200`
  - `GET /api/nba/live/active` -> `200`
  - `GET /health` -> `200`
- frontend verification:
  - `npm run build` in `frontend/` completed successfully
  - Next emitted a non-fatal ESLint patch warning during build, but the build finished and generated both legacy and `/nba/*` routes
### Absence-impact defaults were re-enabled conservatively

Verified the current absence-impact pipeline end to end:
- `analytics/features_opportunity.py` is already passing signed deltas through `_build_absence_impact_features`
- `analytics/opportunity_context.py` is already clamping absence-impact adjustments symmetrically
- `analytics/opportunity_model.py` now uses conservative non-zero defaults:
  - `absence_impact_minutes_factor=0.15`
  - `absence_impact_minutes_cap=3.0`
  - `absence_impact_usage_factor=0.10`
  - `absence_impact_usage_cap=0.02`
  - `absence_impact_touches_factor=0.08`
  - `absence_impact_touches_cap=3.0`
  - `absence_impact_passes_factor=0.06`
  - `absence_impact_passes_cap=2.0`

Important note:
- `absence_impact_confidence_floor` remains `0.35` in code
- the task prompt said this "should be ~0.18", but the instruction also said not to change logic beyond the coefficient re-enable, so the floor was left unchanged intentionally

Verification:
- `E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m pytest tests/ -q`
- result after later ingestion additions: `165 passed`

### Live model and live API endpoints were implemented

Added backend-only live projection support:
- new live model module: `analytics/live_model.py`
- new service layer: `api/services/live_service.py`
- `api/routes/live.py` now queries the DB through `Depends(get_db)` instead of returning mocks

Implemented behavior:
- pace-adjusted live projections for points, rebounds, assists, and threes
- regulation-progress blending between pregame and live pace extrapolation
- foul-trouble minutes reduction
- live alerts for hot starts, cold starts, edge emergence, pace shifts, and foul trouble
- `/api/live/active` returns real active-game summaries
- `/api/live/{game_id}` returns real game detail payloads with players, alerts, and pace summary

Verification:
- `E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m compileall analytics api`
- local API smoke test against a short-lived server:
  - `GET /api/live/active` -> `200`, returned `11` active games in the current DB
  - `GET /api/live/0022501008` -> `200`, returned valid JSON detail payload

### 1. Fixed the highest-value stat-model biases

#### Rebounds
- Old state: `MAE 2.1636`, `bias +1.1736`
- New state: `MAE 1.8497`, `bias -0.0148`

Applied in `analytics/rebounds_model.py`:
- much lower RPM regression target
- removed the automatic home bump
- increased back-to-back penalty
- removed the frontcourt replacement auto-bonus
- zeroed the opponent rebound bonus
- reduced rebound-rate trend pressure

#### Points
- Old state: `MAE 4.7595`, `bias +1.5997`
- New state: `MAE 4.6386`, `bias +0.6946`

Applied in `analytics/pregame_model.py`:
- much lower PPM regression target
- lower regression factor
- removed the automatic home bump

Assists and threes were checked and left unchanged because their biases remained small.

### 2. Hardened readiness gates

Implemented in `api/services/stats_signal_service.py`:
- blocked signals never surface a recommendation
- stat-specific missing-feature blockers
- stat-specific non-zero sample blockers
- opportunity-confidence blocker at `< 0.35`
- stale archive warning when `odds_snapshots` has not updated inside the final pregame window

Health now exposes:
- `signals_by_stat_type`
- `blocked_by_stat_type`
- `blocked_reasons`

### 3. Added append-only signal audit trail

New pieces:
- ORM model: `SignalAuditTrail`
- Alembic migration: `b8c9d0e1f2a3_add_signal_audit_trail.py`
- API service: `api/services/audit_service.py`
- Routes:
  - `GET /api/audit/player/{player_id}/game/{game_id}`
  - `GET /api/audit/game/{game_id}`
  - `GET /api/audit/recent?limit=50`

`persist_current_signal_snapshots()` and `repair_current_signal_snapshots()` now append audit rows alongside `stats_signal_snapshots`.

### 4. Started calibration analysis properly

Added in `analytics/evaluation.py`:
- `compute_calibration_curve(...)`
- `analyze_recommendation_thresholds(...)`

Wired into `analytics/analytics.py` report builders for:
- points
- rebounds
- assists
- threes

Threshold decisions:
- tightened points recommendations
- tightened rebounds recommendations
- left assists unchanged for now
- left threes unchanged because line coverage is still zero

### 5. Cleared most of the remaining source-pool audit list

Inserted new `absence_source_overrides` for:
- `Mikal Bridges`
- `Isaac Okoro`
- `Royce O'Neale`
- `Brandin Podziemski`
- `Donovan Clingan`
- `Kris Dunn`

Skipped:
- `Leaky Black` because the role sample was too small to treat as a stable core source

Current override count in DB:
- `30`

Starter-pool rebuild result:
- `149` selected sources
- `1,426` summaries in the rebuild batch

All six newly added overrides now show up in the starter-pool selection output.

### 6. Finished the injury-report player matching cleanup

Implemented:
- unified ingestion-time matching onto `analytics/name_matching.py`
- added transliteration handling for names like `Nikola \u0110uri\u0161i\u0107`
- added an audited alias for the `Hansen Yang` / `Yang Hansen` order mismatch
- added team-scoped fuzzy fallback at ingestion time
- added analytics-side unique last-name fallback for team/date matching
- added `backfill_injury_entry_player_ids()` plus a jobs wrapper
- added health coverage metrics for injury-entry match quality

Audit result before backfill:
- total entry match rate: `92.64%`
- named entry match rate: `99.39%`
- all `585` named unmatched rows were only:
  - `Nikola Djurisic` (`336`)
  - `Hansen Yang` (`249`)

Backfill result:
- `total_null`: `585`
- `resolved`: `585`
- `still_null`: `0`

Current injury-entry coverage:
- total entry match rate: `93.21%`
- named entry match rate: `100.00%`

Important nuance:
- the opportunity backtest's `official_injury_player_match_pct` stayed flat at `2.26%`
- opportunity accuracy also stayed flat
- that means raw name resolution was not the main reason opportunity metrics were weak in this window

## Current Model State

Window: `2026-01-01` through `2026-03-12`

| Stat type | Sample | MAE | RMSE | Bias |
|---|---:|---:|---:|---:|
| Points | 9,147 | 4.6386 | 5.8930 | 0.6946 |
| Rebounds | 9,147 | 1.8497 | 2.4091 | -0.0148 |
| Assists | 9,147 | 1.3510 | 1.7811 | 0.1559 |
| Threes | 9,147 | 0.9084 | 1.2157 | 0.1428 |

Recommendation read:
- points recommendations are now more conservative
- rebounds recommendations are now more conservative
- assists still looks good but is running on a thin line sample
- threes still has no usable historical line archive in this window

Absence-impact status:
- signed-delta plumbing is fixed
- conservative default coefficients are re-enabled
- confidence floor is still `0.35` in code
- next absence-impact work should be a controlled backtest on the re-enabled signed layer, then pair-quality filtering if noise remains

Official injury matching status:
- raw named-entry resolution is effectively complete in the local archive
- next injury-related work should focus on how matched injury rows influence player-level context features

## What To Do Next

### Highest-value next steps
1. Audit how player-level official injury rows are used in opportunity features. Matching coverage is fixed, but it is not moving opportunity accuracy yet.
2. Run a controlled absence-impact backtest now that signed deltas and conservative defaults are live. Confirm the re-enabled layer helps before tuning further.
3. Let the new odds archive accumulate. Calibration and edge validation are still bottlenecked by sparse line history.
4. Revisit assists and threes threshold policy only after line coverage is denser.
5. If the absence-impact layer is still noisy, add pair-level suppression / stronger pair thresholds instead of increasing coefficients.

### What not to do next
- do not expand live modeling beyond the current backend implementation until pregame trust improves
- do not touch the frontend
- do not increase absence-impact aggressiveness without a new controlled backtest

## Verification

Run before handing off or merging:

```powershell
E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m unittest discover -s E:\dev\projects\bettingbyte-v2\tests -p "test_*.py" -v
E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m compileall E:\dev\projects\bettingbyte-v2\database E:\dev\projects\bettingbyte-v2\ingestion E:\dev\projects\bettingbyte-v2\analytics E:\dev\projects\bettingbyte-v2\tests E:\dev\projects\bettingbyte-v2\api
E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m pytest E:\dev\projects\bettingbyte-v2\tests\test_jobs.py E:\dev\projects\bettingbyte-v2\tests\test_scheduler.py E:\dev\projects\bettingbyte-v2\tests\test_health_service.py -q
E:\dev\projects\bettingbyte-v2\.venv\Scripts\alembic.exe upgrade head
```

