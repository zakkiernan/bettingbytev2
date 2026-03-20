# Absence-Impact Diagnosis

Last updated: 2026-03-18

## Window

- Evaluation window: 2026-01-01 through 2026-03-12
- Comparison target: the exact rows where the empirical absence-impact layer fired in the 2026-03-18 active-config run
- Controlled counterfactual: same rows reprojected with `PregameOpportunityModelConfig()` zeroed

## Root Cause Summary

The absence-impact rows are not just harder rows. The active layer made those same rows modestly worse on points, while doing nothing at all to minutes because the live config had no minutes coefficient enabled.

The strongest causal issue is the positive-only gate:

- `AbsenceImpactSummary` contains a large negative tail
- `analytics/features_opportunity.py` was discarding negative `minutes_delta`, `usage_delta`, `touches_delta`, and `passes_delta`
- `analytics/opportunity_context.py` was also clamping applied bonuses to positive-only ranges

That meant the model could only move upward when a teammate was out, even in historical cases where the empirical summary said the beneficiary usually lost role, minutes, or usage.

## Controlled Comparison: Same Rows, Layer On vs Off

Rows where the active layer fired:

- Points rows: 702
- Opportunity rows: 702

### Points

| Comparison | Value |
|---|---:|
| Improved rows | 124 |
| Worsened rows | 575 |
| Unchanged rows | 3 |
| Mean abs-error delta (on - off) | +0.0541 |
| Median abs-error delta (on - off) | +0.0450 |

Interpretation:

- On the exact same rows, the active absence-impact layer was net harmful.
- The effect size was modest, which matches the fact that the active config only applied a small usage bump.
- This isolates the layer contribution from selection bias: these rows were harder, but the layer still made them slightly worse on top of that.

### Opportunity / Minutes

| Comparison | Value |
|---|---:|
| Improved rows | 0 |
| Worsened rows | 0 |
| Unchanged rows | 702 |
| Mean abs-error delta (on - off) | 0.0000 |

Interpretation:

- This run did not change minutes at all because the checked-in live config had `absence_impact_minutes_factor=0.0`.
- The minutes underperformance seen on “active” rows was therefore selection effect, not a causal impact from the active config.

## Raw Delta Distribution On Fired Rows

Matched fired-row deltas before coefficient scaling:

| Metric | Mean | Median |
|---|---:|---:|
| `absence_impact_minutes_delta` | 5.8568 | 4.4125 |
| `absence_impact_usage_delta` | 0.0358 | 0.0289 |

Applied bonuses in the live config:

| Metric | Mean applied bonus |
|---|---:|
| Minutes bonus | 0.0000 |
| Usage bonus | 0.0059 |

Interpretation:

- The stored raw deltas are not small, especially on minutes.
- The live run only converted that into a tiny positive usage bump.
- The problem was not “too much active lift” in the 2026-03-18 run. The bigger issue was asymmetric upward-only handling.

## Negative-Delta Suppression

### Full summary table

| Metric | Count | Share |
|---|---:|---:|
| Summary rows with negative `minutes_delta` | 810 / 2,609 | 31.05% |
| Summary rows with negative `usage_delta` | 1,005 / 2,600 | 38.65% |

### Matched rows inside the fired sample

| Metric | Count |
|---|---:|
| Matched summaries with negative `minutes_delta` | 308 |
| Matched summaries with negative `usage_delta` | 158 |

Interpretation:

- Negative empirical signals are common, not rare.
- The positive-only gate was discarding a meaningful fraction of the stored evidence.
- This created systematic upward bias in exactly the injury/absence cases where the model already tended to overproject.

## Sample Confidence Distribution

Confidence buckets on the rows where the layer fired:

| Bucket | Count |
|---|---:|
| `0.65+` | 655 |
| `0.50-0.64` | 45 |
| `0.40-0.49` | 2 |
| `0.18-0.39` | 0 |

Interpretation:

- The low confidence floor (`0.18`) was not the main problem on the rows that actually fired.
- Most active rows were already high-confidence by the current summary metric.
- Raising the floor may still be useful later, but it is not the first-order fix.

## Source And Pair Outliers

Worst source players by average increase in points abs error on the same-row controlled comparison (`count >= 3`):

- Aaron Nesmith: `12` rows, `+0.1854`
- Kelly Oubre Jr.: `6` rows, `+0.1703`
- Andrew Nembhard: `3` rows, `+0.1510`
- Pascal Siakam: `12` rows, `+0.1471`
- Johnny Furphy: `23` rows, `+0.1311`
- Saddiq Bey: `12` rows, `+0.1129`
- Herbert Jones: `12` rows, `+0.1129`
- Tyrese Maxey: `9` rows, `+0.1066`
- Paul George: `31` rows, `+0.1049`
- Deni Avdija: `6` rows, `+0.1048`

Worst source -> beneficiary pairs (`count >= 2`):

- Aaron Nesmith -> Kam Jones: `+0.2325`
- Pascal Siakam -> Micah Potter: `+0.2300`
- Aaron Nesmith -> Micah Potter: `+0.2290`
- Pascal Siakam -> Jarace Walker: `+0.2285`
- Aaron Nesmith -> Jarace Walker: `+0.2270`
- Shai Gilgeous-Alexander -> Aaron Wiggins: `+0.2190`
- Ajay Mitchell -> Aaron Wiggins: `+0.2190`
- Stephen Curry -> Gui Santos: `+0.2170`
- Moses Moody -> Gui Santos: `+0.2170`
- Joel Embiid -> Kelly Oubre Jr.: `+0.2165`

Interpretation:

- Pair quality is uneven even after the source override expansion.
- Several noisy bench-beneficiary cases still look unreliable.
- If signed deltas alone do not recover the layer, the next filter should be pair-level suppression or a higher per-pair sample minimum.

## Recommendation

Priority order:

1. Remove the positive-only gate and allow signed deltas to flow end-to-end.
2. Clamp absence-impact bonuses symmetrically in the opportunity layer.
3. Re-test with conservative coefficients before re-enabling anything by default.
4. If still noisy, add pair-level suppression or raise per-pair sample thresholds rather than globally cranking coefficients.

## Implementation Decision

Based on this diagnosis, the first fix to try is:

- keep the current confidence logic for now
- allow negative deltas in `analytics/features_opportunity.py`
- allow symmetric caps in `analytics/opportunity_context.py`
- only re-enable coefficients if the post-fix controlled comparison is actually better
