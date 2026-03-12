# NBA Rotations Scraper

Scrapes [nbarotations.info](https://nbarotations.info) with a **Scrapling-first** fetch strategy and a robust `requests + BeautifulSoup` fallback.

## Features

- Index scrape for all `/game/{id}` links
- Per-game scrape of matchup metadata
- Extracts embedded `displayGame("away"|"home", [...])` player rotation payloads into `raw_sections`
- Graceful per-game error capture (one bad game page won't kill the run)
- Retry + backoff + timeout + browser-like User-Agent
- Writes:
  - `data/latest.json`
  - `data/history/YYYYMMDD_HHMMSS.json`
- Adds deterministic `payload_hash` for change detection

## Output schema

```json
{
  "source_url": "https://nbarotations.info/",
  "fetched_at_utc": "2026-03-10T03:55:00+00:00",
  "games": [
    {
      "game_id": "0022500930",
      "date_label": "Mar 08",
      "away_team": "Chicago Bulls",
      "away_score": 110,
      "home_team": "Sacramento Kings",
      "home_score": 126,
      "title": "Chicago Bulls 110 @ Sacramento Kings 126",
      "url": "https://nbarotations.info/game/0022500930",
      "raw_sections": [
        {
          "section_type": "display_game",
          "side": "away",
          "player_count": 9,
          "players": [{"name": "...", "pid": 123, "histogram": [...] }]
        }
      ]
    }
  ],
  "payload_hash": "sha256..."
}
```

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run full scraper

```bash
PYTHONPATH=src python scripts/scrape_nbarotations.py --pretty
```

Optional limit:

```bash
PYTHONPATH=src python scripts/scrape_nbarotations.py --max-games 5 --pretty
```

Hardening flags:

```bash
# default strict validation + lock file
PYTHONPATH=src python scripts/scrape_nbarotations.py --pretty

# fail on warnings too
PYTHONPATH=src python scripts/scrape_nbarotations.py --pretty --fail-on-warn

# disable strict-mode failure (still emits validation arrays)
PYTHONPATH=src python scripts/scrape_nbarotations.py --pretty --no-strict
```

## Backfill individual game files

```bash
# Resume-safe backfill (skips existing files in data/games)
PYTHONPATH=src python scripts/backfill_games.py --pretty

# Example: just fill 25 new games quickly
PYTHONPATH=src python scripts/backfill_games.py --max-new 25 --pretty
```

## Smoke test (index only)

```bash
PYTHONPATH=src python scripts/smoke_index.py
```

## Notes

- Scrapling dependency chain can vary by environment; this project includes fallback fetch logic so scraping still works when Scrapling isn't available at runtime.
- If site structure changes, adjust parser logic in `src/nbarotations_scraper/scraper.py`.
