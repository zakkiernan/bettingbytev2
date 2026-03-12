#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from nbarotations_scraper.pregame_feature_view import (
    build_pregame_feature_rows,
    load_team_priors,
    save_feature_rows,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build per-player pregame context feature rows")
    p.add_argument(
        "--input",
        default="data/pregame_context/latest.json",
        help="Normalized pregame context payload",
    )
    p.add_argument(
        "--team-priors",
        default=None,
        help="Optional team priors JSON path",
    )
    p.add_argument(
        "--output",
        default="data/pregame_context/features/latest.json",
        help="Output feature rows path",
    )
    p.add_argument("--pretty", action="store_true", help="Print output rows to stdout")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    payload = json.loads(open(args.input, "r", encoding="utf-8").read())
    priors = load_team_priors(args.team_priors)
    rows = build_pregame_feature_rows(payload, priors_by_team_id=priors)
    out = save_feature_rows(rows, args.output)

    print(f"Saved feature rows: {out}")
    print(f"Row count: {len(rows)}")

    if args.pretty:
        print(json.dumps(rows[:20], indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
