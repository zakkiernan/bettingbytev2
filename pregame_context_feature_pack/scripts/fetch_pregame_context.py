#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging

from nbarotations_scraper.pregame_context import PregameContextIngestor, save_pregame_payload


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch normalized NBA pregame context prototype payload")
    p.add_argument("--timeout", type=int, default=20, help="HTTP timeout per request in seconds")
    p.add_argument("--base-dir", default="data/pregame_context", help="Output directory")
    p.add_argument("--pretty", action="store_true", help="Print payload to stdout")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    ingestor = PregameContextIngestor(timeout_seconds=args.timeout)
    payload = ingestor.fetch()
    latest_path, history_path = save_pregame_payload(payload, base_dir=args.base_dir)

    print(f"Saved latest: {latest_path}")
    print(f"Saved history: {history_path}")

    if args.pretty:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
