#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from nbarotations_scraper.scraper import NBARotationsScraper, save_payload
from nbarotations_scraper.validation import validate_payload


def _acquire_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = lock_path.open("a+", encoding="utf-8")
    try:
        import fcntl

        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fh.seek(0)
        fh.truncate(0)
        fh.write(str(os.getpid()))
        fh.flush()
        return fh
    except BlockingIOError as exc:
        fh.seek(0)
        pid = fh.read().strip() or "unknown"
        raise RuntimeError(f"another scrape is already running (lock pid={pid})") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape nbarotations.info")
    parser.add_argument("--max-games", type=int, default=None, help="Limit number of game pages")
    parser.add_argument("--data-dir", default="data", help="Output directory (default: data)")
    parser.add_argument("--pretty", action="store_true", help="Print payload summary")
    parser.add_argument(
        "--strict",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fail with non-zero exit code on validation errors (default: true)",
    )
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Also fail on validation warnings",
    )
    parser.add_argument(
        "--lock-file",
        default=None,
        help="Lock file path (default: <data-dir>/.scrape.lock)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    lock_path = Path(args.lock_file) if args.lock_file else (data_dir / ".scrape.lock")

    lock_handle = None
    try:
        lock_handle = _acquire_lock(lock_path)

        scraper = NBARotationsScraper()
        payload = scraper.scrape(max_games=args.max_games)
        errors, warnings = validate_payload(payload)

        latest_path, history_path = save_payload(payload, base_dir=data_dir)

        if args.pretty:
            print(
                json.dumps(
                    {
                        "fetched_at_utc": payload.get("fetched_at_utc"),
                        "games": len(payload.get("games", [])),
                        "payload_hash": payload.get("payload_hash"),
                        "latest": str(latest_path),
                        "history": str(history_path),
                        "validation_errors": errors,
                        "validation_warnings": warnings,
                    },
                    indent=2,
                )
            )
        else:
            print(str(latest_path))

        if args.strict and errors:
            return 2
        if args.fail_on_warn and warnings:
            return 3
        return 0

    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    finally:
        if lock_handle is not None:
            try:
                lock_handle.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
