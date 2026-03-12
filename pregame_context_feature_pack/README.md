# Pregame Context Feature Pack (NBA)

Isolated bundle for pregame context ingestion + feature-ready per-player rows.

## Contents

- `src/nbarotations_scraper/pregame_context.py` — isolated adapters + normalization
- `src/nbarotations_scraper/pregame_feature_view.py` — thin feature-ready view builder
- `scripts/fetch_pregame_context.py` — ingestion CLI
- `scripts/build_pregame_feature_view.py` — feature row build CLI
- `config/team_priors.example.json` — optional priors schema example
- `tests/test_pregame_context.py` / `tests/test_pregame_feature_view.py`
- `requirements.txt` — minimal deps

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 1) Build normalized pregame context
PYTHONPATH=src python scripts/fetch_pregame_context.py --base-dir data/pregame_context

# 2) Build per-player feature-ready rows (no priors)
PYTHONPATH=src python scripts/build_pregame_feature_view.py \
  --input data/pregame_context/latest.json \
  --output data/pregame_context/features/latest.json

# 3) Build rows with team priors (recommended)
PYTHONPATH=src python scripts/build_pregame_feature_view.py \
  --input data/pregame_context/latest.json \
  --team-priors config/team_priors.example.json \
  --output data/pregame_context/features/latest.json
```

## Wiring Contract (main repo)

Use this pack as a boundary. Keep adapters out of model code.

- Ingestion layer imports only `PregameContextIngestor`
- Feature layer imports only `build_pregame_feature_rows`
- Opportunity/model layer consumes only feature rows

Expected output fields per player/game:

- `expected_start`
- `starter_confidence`
- `official_available`
- `projected_available`
- `late_scratch_risk`
- `teammate_out_count_top7`
- `teammate_out_count_top9`
- `missing_high_usage_teammates`
- `missing_primary_ballhandler`
- `missing_frontcourt_rotation_piece`
- `vacated_minutes_proxy`
- `vacated_usage_proxy`
- `projected_lineup_confirmed`
- `official_starter_flag`
- `pregame_context_confidence`

## Notes

- Handles NBA pregame 403 gaps with retries and partial-data tolerance.
- Keeps Rotowire parsing isolated from model code.
- Does not silently map unresolved players to IDs.
