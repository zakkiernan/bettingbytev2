#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from nbarotations_scraper.scraper import INDEX_URL, NBARotationsScraper
from nbarotations_scraper.validation import validate_game


def _load_existing_ids(games_dir: Path) -> set[str]:
    out: set[str] = set()
    if not games_dir.exists():
        return out
    for p in games_dir.glob("*.json"):
        if p.stem.isdigit():
            out.add(p.stem)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill individual game payloads")
    parser.add_argument("--data-dir", default="data", help="Output directory (default: data)")
    parser.add_argument("--max-games", type=int, default=None, help="Limit number of index games examined")
    parser.add_argument("--max-new", type=int, default=None, help="Stop after writing N new games")
    parser.add_argument("--sleep-ms", type=int, default=250, help="Sleep between game fetches")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True, help="Skip already saved game files")
    parser.add_argument("--strict", action=argparse.BooleanOptionalAction, default=True, help="Skip writes for validation-error payloads")
    parser.add_argument("--pretty", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    games_dir = data_dir / "games"
    games_dir.mkdir(parents=True, exist_ok=True)

    scraper = NBARotationsScraper()
    index_html = scraper.fetch_html(INDEX_URL)
    links = scraper.parse_index(index_html)
    if args.max_games is not None:
        links = links[: args.max_games]

    existing = _load_existing_ids(games_dir) if args.resume else set()

    wrote = 0
    skipped_existing = 0
    skipped_invalid = 0
    errors: list[dict[str, str]] = []

    for game in links:
        if args.resume and game.game_id in existing:
            skipped_existing += 1
            continue

        try:
            html = scraper.fetch_html(game.url)
            payload = scraper.parse_game(game, html)
            g_errors, g_warnings = validate_game(payload)

            payload["validated_at_utc"] = datetime.now(timezone.utc).isoformat()
            payload["validation_errors"] = g_errors
            payload["validation_warnings"] = g_warnings

            if args.strict and g_errors:
                skipped_invalid += 1
                errors.append({"game_id": game.game_id, "error": "; ".join(g_errors[:3])})
                continue

            out_path = games_dir / f"{game.game_id}.json"
            out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            wrote += 1

            if args.max_new is not None and wrote >= args.max_new:
                break

            if args.sleep_ms > 0:
                time.sleep(args.sleep_ms / 1000.0)

        except Exception as exc:
            errors.append({"game_id": game.game_id, "error": str(exc)})

    summary = {
        "index_games_seen": len(links),
        "written_new": wrote,
        "skipped_existing": skipped_existing,
        "skipped_invalid": skipped_invalid,
        "errors_count": len(errors),
        "errors_sample": errors[:10],
        "games_dir": str(games_dir),
    }

    manifest = {
        "ran_at_utc": datetime.now(timezone.utc).isoformat(),
        **summary,
    }
    (data_dir / "backfill_last_run.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if args.pretty:
        print(json.dumps(summary, indent=2))
    else:
        print(json.dumps(summary))

    return 0 if len(errors) == 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())
