# Eval Results

Last updated: 2026-03-18

## Standard Window

- Eval window: `2026-01-01` through `2026-03-12` inclusive
- Minimum history: `8` games
- Minimum projected-role filter: `12.0` expected minutes
- Absence-impact coefficients remain zeroed in `PregameOpportunityModelConfig`

## Current Pregame Baselines

| Stat type | Sample | Line coverage | MAE | RMSE | Bias | Recommendations | Hit rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Points | 9,147 | 0.94% | 4.6386 | 5.8930 | 0.6946 | 59 | 0.5932 |
| Rebounds | 9,147 | 0.90% | 1.8497 | 2.4091 | -0.0148 | 33 | 0.8182 |
| Assists | 9,147 | 0.51% | 1.3510 | 1.7811 | 0.1559 | 27 | 0.7407 |
| Threes | 9,147 | 0.00% | 0.9084 | 1.2157 | 0.1428 | 0 | n/a |

Key takeaways:
- Rebounds was the highest-ROI fix this session and is now the cleanest engine after assists on raw error.
- Points bias is materially lower than the prior `+1.60` state and now sits under the `<0.8` target.
- Assists and threes biases stayed small enough that no coefficient changes were justified.
- Historical line coverage is still extremely thin, so recommendation conclusions remain provisional.

## Task 1: Rebounds Bias Fix

### Population read

Using the backtest population with `expected_minutes >= 12`, actual rebound rate came in at:

- Actual population rebounds per minute: `0.180871`

That is far below the old regression anchor of `0.28`, which was systematically pulling the engine upward.

### Before vs after

| State | MAE | RMSE | Bias |
|---|---:|---:|---:|
| Before | 2.1636 | 2.6786 | 1.1736 |
| After | 1.8497 | 2.4091 | -0.0148 |

### Final config changes

Applied in `analytics/rebounds_model.py`:

- `rpm_regression_target`: `0.28 -> 0.16`
- `rpm_regression_factor`: `0.88 -> 0.90`
- `reb_pct_delta_factor`: `8.0 -> 4.0`
- `oreb_share_factor`: `0.9 -> 0.0`
- `opponent_reb_rate_factor`: `8.0 -> 0.0`
- `pace_factor`: `0.07 -> 0.03`
- `home_bonus`: `0.10 -> 0.0`
- `back_to_back_penalty`: `0.35 -> 0.60`
- added `missing_frontcourt_rotation_bonus` and left it at `0.0`

Interpretation:
- The big miss was not just one noisy bonus.
- The old RPM anchor, opponent rebound bonus, and frontcourt replacement bump were all pushing the model too high on the same rows.
- Rebounds is now effectively bias-neutral across the full eval window.

## Task 2: Points Bias Reduction

### Population read

Using the same backtest population with `expected_minutes >= 12`, actual points per minute came in at:

- Actual population points per minute: `0.477222`

That was well below the old `0.67` regression target.

### Before vs after

| State | MAE | RMSE | Bias |
|---|---:|---:|---:|
| Before | 4.7595 | 6.0073 | 1.5997 |
| After | 4.6386 | 5.8930 | 0.6946 |

### Final config changes

Applied in `analytics/pregame_model.py`:

- `ppm_regression_target`: `0.67 -> 0.42`
- `ppm_regression_factor`: `0.90 -> 0.80`
- `home_bonus`: `0.30 -> 0.0`

Interpretation:
- The old points model was also regressing toward a population that did not match the backtest rows actually making it through the `12.0` expected-minutes filter.
- Lowering the anchor and removing the automatic home lift improved both MAE and bias.

## Assist / Threes Bias Check

No coefficient changes were applied to assists or threes.

Reason:
- Assists bias remained modest at `+0.1559`.
- Threes bias remained modest at `+0.1428`.
- Threes still has zero historical line coverage in this window, so threshold tuning would be pure guesswork.

## Task 3: Readiness Gate Hardening

Implemented in `api/services/stats_signal_service.py` and health schemas/services:

- blocked signals still have `recommended_side=None`, and that suppression now remains enforced after readiness evaluation on every board/detail/persist path
- added stat-specific blockers for missing core feature fields
- added stat-specific non-zero sample blockers for rebounds / assists / threes
- added an opportunity-confidence blocker at `< 0.35`
- added stale odds-archive warning when the last `odds_snapshots` capture is more than `120` minutes old inside the final `4` hours before tip
- health now reports:
  - `signals_by_stat_type`
  - `blocked_by_stat_type`
  - `blocked_reasons`

Readiness result:
- Phase 1 hardening from `PREGAME_BEFORE_LIVE_PLAN.md` is now functionally complete.

## Task 4: Signal Audit Trail

Implemented:

- new append-only table: `signal_audit_trail`
- Alembic migration: `b8c9d0e1f2a3_add_signal_audit_trail.py`
- every persisted signal snapshot now also appends an audit row
- new API endpoints:
  - `GET /api/audit/player/{player_id}/game/{game_id}`
  - `GET /api/audit/game/{game_id}`
  - `GET /api/audit/recent?limit=50`
- health now includes:
  - total audit rows
  - rows by snapshot phase
  - games with full `early + late + tip` audit coverage
  - most recent audit capture timestamp

Operational note:
- current production-style persistence still centers on `snapshot_phase="current"`, so full phased audit coverage will build over time as those signal phases are added to the signal snapshot cadence.

## Task 5: Calibration Analysis

### Points

Calibration read:
- actual line-relative calibration was noisy and slightly anti-calibrated above `0.70` confidence
- recommendation hit rate was steadier than raw calibration, but still improved when confidence was tightened

Best threshold region from current archive:
- `edge >= 1.5`
- `confidence >= 0.65`
- hit rate: `0.6410`
- graded sample: `39`

Applied threshold change in `analytics/pregame_model.py`:
- `MIN_EDGE_TO_RECOMMEND`: `1.0 -> 1.5`
- `MIN_CONFIDENCE_TO_RECOMMEND`: `0.58 -> 0.65`

### Rebounds

Calibration read:
- recommendation hit rate improved as confidence and edge thresholds rose
- best practical tradeoff was more conservative than the original defaults

Best threshold region from current archive:
- `edge >= 1.0`
- `confidence >= 0.65`
- hit rate: `0.9000`
- graded sample: `20`

Applied threshold change in `analytics/rebounds_model.py`:
- `MIN_EDGE_TO_RECOMMEND`: `0.8 -> 1.0`
- `MIN_CONFIDENCE_TO_RECOMMEND`: `0.56 -> 0.65`

### Assists

Calibration read:
- the `0.70-0.80` confidence bucket was directionally strongest
- best archive read was around `edge >= 0.5`, `confidence >= 0.70`, but the sample was only `14`

Decision:
- leave assists thresholds unchanged for now
- evidence is positive, but still too thin to justify a threshold rewrite this session

### Threes

Calibration read:
- no usable calibration or threshold analysis is possible yet because line coverage is still `0`

Decision:
- no threshold changes

## Task 6: Remaining Core Source Audit

Audited prior missing-core list:

- Added overrides:
  - `Mikal Bridges` (`NYK`)
  - `Isaac Okoro` (`CHI`)
  - `Royce O'Neale` (`PHX`)
  - `Brandin Podziemski` (`GSW`)
  - `Donovan Clingan` (`POR`)
  - `Kris Dunn` (`LAC`)
- Skipped:
  - `Leaky Black` (`WAS`) — only `5` games in the audited window; not a stable core source

Current override count in DB:
- `30`

Current starter-pool rebuild result:
- selected sources: `149`
- summaries persisted in the rebuild batch: `1,426`

Selection confirmation:
- all six added overrides now appear in the starter-pool batch
- `Leaky Black` remains intentionally excluded

Interpretation:
- the missing-core cleanup is effectively complete for the audited list
- next absence-impact improvement should focus on pair quality, not more blanket source expansion

## Absence-Impact Status

This session did not re-enable absence-impact coefficients.

Current stance:
- signed-delta plumbing remains intact
- default coefficients stay at zero
- source coverage is better, but pair-level quality still needs work before the layer should influence projections again

## Injury Matching Improvement

### Audit before fixes

Saved in `INJURY_MATCHING_AUDIT.md`.

Direct injury-entry audit before the matcher changes and backfill:

| Metric | Before |
|---|---:|
| Total `official_injury_report_entries` | 102,421 |
| Entries with `player_id` | 94,878 |
| Entries with `player_id = NULL` | 7,543 |
| Named player entries | 95,463 |
| Named entries with `player_id` | 94,878 |
| Named entries with `player_id = NULL` | 585 |
| Named entry match rate | 99.39% |

All named unmatched rows collapsed to only two recurring names:

- `ATL / Nikola Djurisic` (`336` rows): transliteration mismatch against `Nikola \u0110uri\u0161i\u0107`
- `POR / Hansen Yang` (`249` rows): first/last order mismatch against `Yang Hansen`

Failure bucket distribution:

- `transliteration_or_alias_mismatch`: `336`
- `name_order_mismatch`: `249`

### Fixes applied

Implemented:

- canonicalized ingestion-time matching onto `analytics/name_matching.py`
- added transliteration replacements so `\u0110` style names normalize to stable ASCII keys
- added a small audited alias map for `Hansen Yang -> Yang Hansen`
- added team-scoped fuzzy fallback in ingestion matching
- added analytics-side unique last-name fallback for team/date injury rows
- added idempotent `backfill_injury_entry_player_ids()` plus a jobs wrapper
- added health coverage metrics for overall vs named injury-entry matching

### Backfill result

`backfill_injury_entry_player_ids()` result:

- `total_null`: `585`
- `resolved`: `585`
- `still_null`: `0`

Direct coverage after backfill:

| Metric | After |
|---|---:|
| Total `official_injury_report_entries` | 102,421 |
| Entries with `player_id` | 95,463 |
| Entries with `player_id = NULL` | 6,958 |
| Named player entries | 95,463 |
| Named entries with `player_id` | 95,463 |
| Named entries with `player_id = NULL` | 0 |
| Overall entry match rate | 93.21% |
| Named entry match rate | 100.00% |

Interpretation:

- The remaining `NULL` rows are nameless team-level report entries, overwhelmingly `NOT_YET_SUBMITTED`.
- The player-name matching problem is effectively solved in the local archive.

### Opportunity evaluation read

Standard window: `2026-01-01` through `2026-03-12`

| Metric | Before backfill | After backfill |
|---|---:|---:|
| Sample size | 9,794 | 9,794 |
| Minutes MAE | 4.9270 | 4.9272 |
| Minutes RMSE | 6.3640 | 6.3641 |
| Minutes bias | 1.6310 | 1.6313 |
| Start accuracy | 90.59% | 90.59% |
| Close accuracy | 67.89% | 67.89% |
| `official_injury_player_match_count` | 221 | 221 |
| `official_injury_player_match_pct` | 2.26% | 2.26% |
| `official_injury_team_context_count` | 3,937 | 3,937 |
| `official_injury_team_context_pct` | 40.20% | 40.20% |

Interpretation:

- Backfilling the unresolved entry rows did not change opportunity accuracy.
- The opportunity backtest metric is measuring player-level injury attachment on target rows, not raw entry-resolution coverage.
- Matching coverage was not the dominant blocker for opportunity accuracy in this eval window.
- The next injury-related work should focus on how matched injury rows feed role/context logic, not on more name-normalization work.

## Files Changed This Session

- `analytics/pregame_model.py`
- `analytics/rebounds_model.py`
- `analytics/evaluation.py`
- `analytics/analytics.py`
- `analytics/injury_matching_audit.py`
- `analytics/injury_report_loader.py`
- `analytics/name_matching.py`
- `api/services/stats_signal_service.py`
- `api/services/audit_service.py`
- `api/services/health_service.py`
- `api/routes/audit.py`
- `api/routes/__init__.py`
- `api/main.py`
- `api/schemas/audit.py`
- `api/schemas/health.py`
- `api/schemas/__init__.py`
- `database/models.py`
- `alembic/versions/b8c9d0e1f2a3_add_signal_audit_trail.py`
- `ingestion/injury_reports.py`
- `ingestion/jobs.py`
- `INJURY_MATCHING_AUDIT.md`
- `tests/test_stats_signal_service.py`
- `tests/test_evaluation.py`
- `tests/test_audit_service.py`
- `tests/test_health_service.py`
- `tests/test_injury_report_loader.py`
- `tests/test_injury_reports.py`
- `tests/test_jobs.py`

## Verification

- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v`
- `.\.venv\Scripts\python.exe -m compileall database ingestion analytics tests api`
- `.\.venv\Scripts\python.exe -m pytest tests\test_jobs.py tests\test_scheduler.py tests\test_health_service.py -q`
