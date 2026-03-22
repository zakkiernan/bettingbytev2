# Project State

Last updated: 2026-03-22
Project root: `E:\dev\projects\bettingbyte-v2`

## Product Goal

Backend-first NBA prop analytics platform with:
- reliable pregame signal generation first
- live modeling only after pregame readiness, auditability, and calibration are trustworthy

Frontend remains frozen.

## Current Backend Status

### Ingestion / Database

- Historical game logs, advanced logs, and rotation data are live.
- Official NBA injury-report ingestion/backfill is live.
- Injury-report player matching uses one canonical normalizer in `analytics/name_matching.py`.
  - named entry match rate: `100.00%`
- FanDuel pregame and live odds ingestion is live.
- `odds_snapshots` captures phased pregame writes, rolling accumulation, and live snapshots.
- Append-only `signal_audit_trail` table is live.
- 12 additional stats.nba.com ingestion surfaces are live (shot chart, hustle, matchup, win probability, clutch, synergy, tracking, on/off, defensive, shot locations, lineup stats).
- Health reporting covers line archive density, injury match coverage, readiness/blocker counts, and audit summary.

### Analytics

- Shared opportunity backbone is the standard runtime path.
- Separate stat engines are live for points, rebounds, assists, threes.
- Absence-impact coefficients are re-enabled at conservative defaults:
  - `minutes_factor=0.15`, `usage_factor=0.10`, `touches_factor=0.08`, `passes_factor=0.06`
  - `confidence_floor=0.35`
- Absence-impact pair-level quality gates tightened:
  - `sample_confidence >= 0.25`
  - `source_out_game_count >= 3`
  - `beneficiary_out_game_count >= 3`
  - `|impact_score| >= 0.05`
- A/B backtest comparator added: runs points backtest with coefficients on vs off for controlled comparison.
- Evaluation/reporting includes error summaries, decision summaries, absence-impact summaries, calibration curves, threshold analysis.

## Current Modeling State

### Pregame Baselines

Window: `2026-01-01` through `2026-03-12`

| Stat type | Sample | MAE | RMSE | Bias |
|---|---:|---:|---:|---:|
| Points | 9,147 | 4.6386 | 5.8930 | 0.6946 |
| Rebounds | 9,147 | 1.8497 | 2.4091 | -0.0148 |
| Assists | 9,147 | 1.3510 | 1.7811 | 0.1559 |
| Threes | 9,147 | 0.9084 | 1.2157 | 0.1428 |

### Recommendation Read

- Points and rebounds recommendations are conservative after calibration review.
- Assists thresholds unchanged.
- Threes thresholds unchanged (zero historical line coverage).

### Absence-Impact

- Conservative coefficients are live (re-enabled 2026-03-19).
- Signed-delta plumbing is fixed.
- Pair-level quality gates tightened (2026-03-22).
- A/B backtest comparator available via `build_absence_impact_ab_report()`.
- Source-pool: 30 overrides, 149 selected sources, 1,426 summaries.

## Current Phase Progress

### Phase 1–3: Analytics Architecture, Rotation Data, Rotation Hardening
Status: complete

### Phase 4: Opportunity Model Improvement
Status: in progress

Completed:
- official injury report wiring
- historical pregame context backfill
- empirical absence-impact layer with signed deltas
- source override expansion
- conservative coefficient re-enable
- pair-level quality gates

Open:
- run A/B backtest to validate absence-impact layer
- improve how matched official injury rows affect player-level opportunity context

### Phase 5: Pregame Reliability Hardening
Status: in progress

Completed:
- readiness gates (blocked/limited/ready)
- signal audit trail
- calibration curve and threshold analysis utilities
- provisional threshold tightening for points and rebounds

Open:
- collect more line coverage before treating calibration as stable
- revisit assists/threes thresholds once archive density improves

## Current Next Phase Gate

Before live modeling starts:

1. Run the A/B backtest to confirm absence-impact helps before tuning further.
2. Let odds archive accumulate for real edge validation.
3. Improve how official injury rows change player-level opportunity context.
4. Re-run calibration once line coverage is denser.

Live modeling should remain blocked until these pregame reliability gates are stronger.

## Important Design Decisions

- Shared opportunity backbone, separate stat engines.
- Backend/model quality over frontend work.
- Conservative readiness and recommendation thresholds preferred.
- Audit trail is append-only.
- Do not trust betting-edge conclusions until line archive coverage is larger.

## Useful Commands

### Tests
```powershell
E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m pytest tests/ -q
```

### Compile checks
```powershell
E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m compileall database ingestion analytics tests api
```

### Migrations
```powershell
E:\dev\projects\bettingbyte-v2\.venv\Scripts\alembic.exe upgrade head
```
