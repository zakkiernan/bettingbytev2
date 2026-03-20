# SESSION_HANDOFF.md

## Session Date
2026-03-18

## Current Priority

Pregame reliability is still the priority. Frontend stays frozen. Live-model work stays blocked until pregame readiness, auditability, and historical line coverage are stronger.

## What Was Completed

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
- default coefficients remain zero
- next absence-impact work should be pair-quality filtering, not coefficient tuning

Official injury matching status:
- raw named-entry resolution is effectively complete in the local archive
- next injury-related work should focus on how matched injury rows influence player-level context features

## What To Do Next

### Highest-value next steps
1. Audit how player-level official injury rows are used in opportunity features. Matching coverage is fixed, but it is not moving opportunity accuracy yet.
2. Let the new odds archive accumulate. Calibration and edge validation are still bottlenecked by sparse line history.
3. Revisit assists and threes threshold policy only after line coverage is denser.
4. Add pair-level suppression / stronger pair thresholds before trying to re-enable absence-impact bonuses.

### What not to do next
- do not start live model work yet
- do not touch the frontend
- do not re-enable absence-impact by default without a new controlled backtest

## Verification

Run before handing off or merging:

```powershell
E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m unittest discover -s E:\dev\projects\bettingbyte-v2\tests -p "test_*.py" -v
E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m compileall E:\dev\projects\bettingbyte-v2\database E:\dev\projects\bettingbyte-v2\ingestion E:\dev\projects\bettingbyte-v2\analytics E:\dev\projects\bettingbyte-v2\tests E:\dev\projects\bettingbyte-v2\api
E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m pytest E:\dev\projects\bettingbyte-v2\tests\test_jobs.py E:\dev\projects\bettingbyte-v2\tests\test_scheduler.py E:\dev\projects\bettingbyte-v2\tests\test_health_service.py -q
E:\dev\projects\bettingbyte-v2\.venv\Scripts\alembic.exe upgrade head
```
