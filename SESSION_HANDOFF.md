# Session Handoff

Date: 2026-03-12
Repo: `E:\dev\projects\bettingbyte-v2`

## What Was Completed This Session
- Continued Phase 4 opportunity work.
- Added official NBA injury-report PDF ingestion and normalization.
- Backfilled historical official injury snapshots into the local DB.
- Wired official injury context into runtime opportunity feature construction.
- Wired official injury context into the historical opportunity backtest path.
- Fixed the historical evaluator so it selects the latest official report before tip using canonical game times.
- Added coverage metrics for official injury context inside opportunity backtests and diagnostics.
- Identified that generic team-level injury counts were degrading opportunity quality when treated as player-role signals.
- Fixed the injury feature semantics so official team summaries no longer fabricate `teammate_out_count_top7/top9` values.
- Removed the generic team-injury-to-minutes bonus from the opportunity model.
- Re-ran diagnostics and backtests after the semantic fix.
- Updated project docs to reflect current Phase 4 status and next steps.

## Files Added / Changed That Matter Most
- `PROJECT_STATE.md`
- `SESSION_HANDOFF.md`
- `ingestion/injury_reports.py`
- `analytics/injury_report_loader.py`
- `analytics/features_opportunity.py`
- `analytics/opportunity_model.py`
- `analytics/evaluation.py`
- `analytics/diagnostics.py`
- `tests/test_injury_reports.py`
- `tests/test_injury_report_loader.py`
- `tests/test_evaluation.py`

## Current Safe Understanding
- Phase 1 is complete.
- Phase 2 is complete.
- Phase 3 is complete.
- Phase 4 is in progress.
- Runtime rotation ingestion is scraper-backed, not `GameRotation`-backed.
- The local rotation pipeline is stable.
- Historical official NBA injury data is now stored and queryable from `2025-12-22` forward, with source-side gaps outside that range.
- Opportunity diagnostics/backtests now reflect the live injury-aware architecture.
- Official team-level injury summaries should be treated as weak context only.
- Strong opportunity adjustments should come from player-specific status and true vacated-role signals.

## Current Metrics Snapshot
- `rotation_games`: `948`
- `rotation_coverage_pct`: `99.27`
- `official_injury_reports`: `600`
- `official_injury_report_entries`: `78181`
- Opportunity backtest window: `2026-01-01` through `2026-03-12`
- Opportunity sample size: `9064`
- Minutes MAE: `4.9556`
- Minutes RMSE: `6.4431`
- Minutes bias: `0.1252`
- Official injury player match pct: `0.0190`
- Official injury team-context pct: `0.3641`

## Known Source Gaps
The following games are currently missing from `nbarotations.info` and are intentionally quarantined as `source_missing_game`:
- `0022500314` - CHI at ORL on 2025-12-01
- `0022500523` - LAL at SAS on 2026-01-07
- `0022500576` - NYK at SAC on 2026-01-14
- `0022500581` - OKC at HOU on 2026-01-15
- `0022500595` - IND at DET on 2026-01-17
- `0022500620` - CLE at CHA on 2026-01-21
- `0022500753` - GSW at LAL on 2026-02-07

These pages return site-level not-found content and no `displayGame(...)` payloads.

## Verification Completed
- `E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m unittest discover tests -v`
- `E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m py_compile analytics\evaluation.py analytics\diagnostics.py analytics\analytics.py analytics\features_opportunity.py analytics\opportunity_model.py`
- Historical opportunity backtest rerun on `2026-01-01` through `2026-03-12`
- Injury-aware vs injury-disabled comparison run on the same backtest window
- Confirmed that the injury semantic fix made the official injury layer close to neutral instead of harmful

## Next Recommended Task
1. Continue Phase 4 opportunity improvement.
2. Tighten player-level injury / availability matching before increasing injury model influence.
3. Keep official team-summary injury data as weak context only.
4. Use the pregame context pack for real vacated-role and starter signals.
5. Revisit denser near-tip historical injury backfill only if we need stronger backtest fidelity.

## Things To Be Careful About
- Do not start live modeling yet.
- Do not jump straight to points recalibration before improving opportunity features further.
- Do not treat official team-level injury counts as player-specific opportunity signals.
- Do not spread scraper-specific or source-specific logic outside the adapter/normalization layer.
- Do not assume the quarantined rotation games will become available unless the source site changes.

## Quick Restart Prompt
If starting a new Codex session, point it to:
- `AGENTS.md`
- `PROJECT_STATE.md`
- `SESSION_HANDOFF.md`

Then ask it to continue with:
- Phase 4 opportunity model improvement
- tighten player-specific injury and pregame-context matching
- keep official team injury summaries as weak context only
