# Project State

Last updated: 2026-03-18
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
- Injury-report player matching now uses one canonical normalizer in `analytics/name_matching.py`.
- Local injury-entry backfill resolved all named `player_id = NULL` rows.
- FanDuel pregame and live odds ingestion is live.
- `odds_snapshots` now captures:
  - phased pregame writes (`early`, `late`, `tip`)
  - rolling pregame accumulation (`accumulation`)
  - live snapshots (`live`)
- New append-only signal audit table exists:
  - `signal_audit_trail`
- Health reporting now covers:
  - line archive density
  - injury-entry match coverage
  - readiness counts by stat type
  - blocker reason counts
  - audit coverage summary

### Analytics

- Shared opportunity backbone is the standard runtime path.
- Separate stat engines are live for:
  - points
  - rebounds
  - assists
  - threes
- Absence-impact plumbing remains intact but default coefficients are zeroed.
- Evaluation/reporting now includes:
  - error summaries
  - decision summaries
  - absence-impact summaries
  - calibration curves
  - threshold analysis

## Current Modeling State

### Pregame Baselines

Window: `2026-01-01` through `2026-03-12`

| Stat type | Sample | MAE | RMSE | Bias |
|---|---:|---:|---:|---:|
| Points | 9,147 | 4.6386 | 5.8930 | 0.6946 |
| Rebounds | 9,147 | 1.8497 | 2.4091 | -0.0148 |
| Assists | 9,147 | 1.3510 | 1.7811 | 0.1559 |
| Threes | 9,147 | 0.9084 | 1.2157 | 0.1428 |

Interpretation:
- points and rebounds both improved materially this session
- rebounds bias has been effectively neutralized
- assists remains the cleanest untouched engine
- threes still needs archive accumulation before any edge claims are meaningful

### Recommendation Read

- Points recommendations are now more conservative after calibration review.
- Rebounds recommendations are also tighter after calibration review.
- Assists thresholds are unchanged for now.
- Threes thresholds are unchanged because historical line coverage is still zero.

### Opportunity / Context

- Opportunity remains the shared dependency for every stat engine.
- Readiness now blocks any signal with `opportunity_confidence < 0.35`.
- Missing stat-specific feature coverage and thin non-zero sample are now first-class blockers.
- Official injury archive coverage is now:
  - overall entry match rate: `93.21%`
  - named entry match rate: `100.00%`

### Absence-Impact

- Default absence-impact coefficients remain zero.
- Signed-delta plumbing is fixed.
- Source-pool overrides expanded again:
  - total overrides in DB: `30`
- Current starter-pool rebuild:
  - `149` selected sources
  - `1,426` summaries persisted in the rebuild batch

## Current Phase Progress

### Phase 1: Analytics Architecture
Status: complete

Completed:
- shared opportunity backbone
- separate stat engines
- transparent breakdowns
- backtest/reporting structure

### Phase 2: Rotation Data Layer
Status: complete

### Phase 3: Rotation Backfill And Hardening
Status: complete

### Phase 4: Opportunity Model Improvement
Status: in progress

Completed inside Phase 4:
- official injury report wiring
- historical pregame context backfill
- empirical absence-impact layer
- signed-delta absence-impact fix
- source override expansion

Open inside Phase 4:
- improve pair quality before re-enabling absence-impact bonuses
- improve how matched official injury rows affect player-level opportunity context

### Phase 5: Pregame Reliability Hardening
Status: in progress

#### Phase 1 readiness gates
Status: complete

Completed:
- blocked / limited / ready status surfaced end-to-end
- stat-specific readiness checks
- opportunity-confidence blocker
- stale archive warning
- health blocker counts by reason / stat type

#### Phase 2 signal audit trail
Status: complete

Completed:
- append-only `signal_audit_trail`
- audit endpoints
- audit summary in health

#### Phase 3 calibration
Status: started

Completed:
- calibration curve utilities
- threshold analysis utilities
- calibration output added to report builders
- provisional threshold tightening for points and rebounds

Still needed:
- collect more line coverage before treating calibration as stable
- revisit assists / threes thresholds once archive density improves

## Current Next Phase Gate

Before live modeling starts:

1. Let the hardened odds archive accumulate enough multi-snapshot coverage to support real edge validation.
2. Improve how matched official injury rows change player-level opportunity context; raw named-entry matching is no longer the main bottleneck.
3. Revisit absence-impact with pair-level suppression / stricter pair sampling.
4. Re-run calibration once line coverage is materially denser.

Live modeling should remain blocked until those pregame reliability gates are stronger.

## Important Design Decisions

- Shared opportunity backbone, separate stat engines.
- Backend/model quality over frontend work.
- Conservative readiness and recommendation thresholds are preferred.
- Audit trail is append-only.
- Do not trust betting-edge conclusions until line archive coverage is materially larger.
- Do not start live model implementation yet.

## Useful Commands

### Tests
```powershell
E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m unittest discover -s E:\dev\projects\bettingbyte-v2\tests -p "test_*.py" -v
```

### Compile checks
```powershell
E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m compileall E:\dev\projects\bettingbyte-v2\database E:\dev\projects\bettingbyte-v2\ingestion E:\dev\projects\bettingbyte-v2\analytics E:\dev\projects\bettingbyte-v2\tests E:\dev\projects\bettingbyte-v2\api
```

### Pytest coverage for ingestion / health
```powershell
E:\dev\projects\bettingbyte-v2\.venv\Scripts\python.exe -m pytest E:\dev\projects\bettingbyte-v2\tests\test_jobs.py E:\dev\projects\bettingbyte-v2\tests\test_scheduler.py E:\dev\projects\bettingbyte-v2\tests\test_health_service.py -q
```

### Migrations
```powershell
E:\dev\projects\bettingbyte-v2\.venv\Scripts\alembic.exe upgrade head
```
