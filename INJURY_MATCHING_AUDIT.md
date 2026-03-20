# Injury Matching Audit

## Coverage
- Total `official_injury_report_entries`: 102421
- Entries with `player_id`: 94878 (92.64%)
- Entries with `player_id = NULL`: 7543 (7.36%)
- Named player entries: 95463
- Named entries with `player_id`: 94878 (99.39%)
- Named entries with `player_id = NULL`: 585 (0.61%)

## Top Unmatched Names
- `ATL / Nikola Djurisic`: 336 rows; closest DB match `Nikola \u0110uri\u0161i\u0107` (token score 1.00)
- `POR / Hansen Yang`: 249 rows; closest DB match `Yang Hansen` (token score 1.00)

## Failure Bucket Distribution
- `transliteration_or_alias_mismatch`: 336
- `name_order_mismatch`: 249

## Bucket Examples
### name_order_mismatch
- PDF name: `Hansen Yang` (POR)
- Legacy ingestion keys: `['hansen yang']`
- Canonical matcher keys: `['hansen yang', 'yang hansen']`
- Closest DB match: `Yang Hansen` with normalized form `yang hansen` and token score 1.00

### transliteration_or_alias_mismatch
- PDF name: `Nikola Djurisic` (ATL)
- Legacy ingestion keys: `['nikola djurisic']`
- Canonical matcher keys: `['nikola djurisic']`
- Closest DB match: `Nikola \u0110uri\u0161i\u0107` with normalized form `nikola djurisic` and token score 1.00

## Recommendation

- Replace the ingestion-local normalizer with `analytics/name_matching.py` so ingestion and analytics stop drifting.
- Add a tiny audited alias layer for real recurring name-order mismatches such as `Hansen Yang -> Yang Hansen`.
- Add team-scoped fuzzy fallback only after exact key lookup fails.
- Backfill existing named `player_id = NULL` rows once the new matcher is in place.
