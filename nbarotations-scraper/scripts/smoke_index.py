#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict

from nbarotations_scraper.scraper import NBARotationsScraper


if __name__ == "__main__":
    scraper = NBARotationsScraper()
    html = scraper.fetch_html("https://nbarotations.info/")
    games = scraper.parse_index(html)
    print(json.dumps({"game_count": len(games), "sample": [asdict(g) for g in games[:5]]}, indent=2))
