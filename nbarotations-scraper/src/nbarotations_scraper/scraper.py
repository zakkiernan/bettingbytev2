from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

LOGGER = logging.getLogger(__name__)

BASE_URL = "https://nbarotations.info"
INDEX_URL = BASE_URL + "/"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


@dataclass(slots=True)
class GameLink:
    game_id: str
    date_label: str
    title: str
    url: str


class NBARotationsScraper:
    def __init__(
        self,
        timeout: int = 25,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.5,
        use_scrapling: bool = True,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._scrapling_fetcher = None

        if use_scrapling:
            self._initialize_scrapling()

    def _initialize_scrapling(self) -> None:
        try:
            from scrapling import Fetcher

            try:
                # Avoid deprecated ctor flags and keep behavior explicit.
                Fetcher.configure(auto_match=False)
            except Exception:
                pass

            self._scrapling_fetcher = Fetcher()
            LOGGER.info("Scrapling fetcher initialized")
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("Scrapling unavailable, using requests+bs4 fallback: %s", exc)
            self._scrapling_fetcher = None

    def fetch_html(self, url: str) -> str:
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if self._scrapling_fetcher is not None:
                    resp = self._scrapling_fetcher.get(url, timeout=self.timeout * 1000)
                    status = getattr(resp, "status", 200)
                    if int(status) >= 400:
                        raise RuntimeError(f"Scrapling status {status} for {url}")
                    html = getattr(resp, "html_content", "")
                    if html:
                        return html

                r = self.session.get(url, timeout=self.timeout)
                r.raise_for_status()
                return r.text
            except Exception as exc:  # pragma: no cover
                last_error = exc
                if attempt < self.max_retries:
                    sleep_s = self.retry_backoff_seconds * (2 ** (attempt - 1))
                    LOGGER.warning(
                        "Fetch failed (%s/%s) for %s: %s. Retrying in %.1fs",
                        attempt,
                        self.max_retries,
                        url,
                        exc,
                        sleep_s,
                    )
                    time.sleep(sleep_s)
                else:
                    LOGGER.error("Fetch failed permanently for %s: %s", url, exc)

        raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error

    def parse_index(self, html: str) -> list[GameLink]:
        soup = BeautifulSoup(html, "lxml")
        links: list[GameLink] = []
        seen: set[str] = set()

        for a in soup.select("a[href^='/game/']"):
            href = a.get("href", "").strip()
            match = re.search(r"/game/(\d+)", href)
            if not match:
                continue

            game_id = match.group(1)
            if game_id in seen:
                continue

            title = " ".join(a.get_text(" ", strip=True).split())
            date_label = ""

            td = a.find_parent("td")
            if td:
                td_text = " ".join(td.get_text(" ", strip=True).split())
                date_label = td_text.replace(title, "").strip()

            seen.add(game_id)
            links.append(
                GameLink(
                    game_id=game_id,
                    date_label=date_label,
                    title=title,
                    url=urljoin(BASE_URL, f"/game/{game_id}"),
                )
            )

        return links

    def parse_game(self, game: GameLink, html: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        header_node = soup.select_one(".gameHeader")
        header_text = " ".join(header_node.get_text(" ", strip=True).split()) if header_node else game.title

        away_team, away_score, home_team, home_score = self._parse_matchup(header_text)

        raw_sections = self._extract_raw_sections(soup)

        return {
            "game_id": game.game_id,
            "date_label": game.date_label,
            "away_team": away_team,
            "away_score": away_score,
            "home_team": home_team,
            "home_score": home_score,
            "title": header_text,
            "url": game.url,
            "raw_sections": raw_sections,
        }

    @staticmethod
    def _parse_matchup(text: str) -> tuple[str | None, int | None, str | None, int | None]:
        cleaned = " ".join(text.split())
        m = re.match(r"^(.*?)\s+(\d+)\s+@\s+(.*?)\s+(\d+)$", cleaned)
        if not m:
            return None, None, None, None
        away_team, away_score, home_team, home_score = m.groups()
        return away_team.strip(), int(away_score), home_team.strip(), int(home_score)

    def _extract_raw_sections(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []

        # Parse embedded displayGame("away"|"home", [ ...players... ]) payloads
        for script in soup.find_all("script"):
            script_text = script.string or script.get_text("", strip=False)
            if not script_text or "displayGame(" not in script_text:
                continue

            for side in ("away", "home"):
                marker = f'displayGame("{side}",'
                start = script_text.find(marker)
                if start == -1:
                    continue

                array_text = _extract_json_array(script_text, script_text.find("[", start))
                if not array_text:
                    continue

                try:
                    payload = json.loads(array_text)
                except Exception:
                    continue

                sections.append(
                    {
                        "section_type": "display_game",
                        "side": side,
                        "player_count": len(payload) if isinstance(payload, list) else None,
                        "players": payload if isinstance(payload, list) else [],
                    }
                )

        # Generic table capture fallback
        for idx, table in enumerate(soup.find_all("table")):
            rows: list[list[str]] = []
            for tr in table.find_all("tr"):
                cells = [" ".join(cell.get_text(" ", strip=True).split()) for cell in tr.find_all(["th", "td"])]
                if any(cells):
                    rows.append(cells)

            if rows:
                sections.append(
                    {
                        "section_type": "table",
                        "index": idx,
                        "rows": rows,
                    }
                )

        return sections

    def scrape(self, max_games: int | None = None) -> dict[str, Any]:
        fetched_at = datetime.now(timezone.utc).isoformat()

        index_html = self.fetch_html(INDEX_URL)
        games = self.parse_index(index_html)
        if max_games is not None:
            games = games[:max_games]

        output_games: list[dict[str, Any]] = []
        for game in games:
            try:
                game_html = self.fetch_html(game.url)
                payload = self.parse_game(game, game_html)
            except Exception as exc:
                payload = {
                    "game_id": game.game_id,
                    "date_label": game.date_label,
                    "away_team": None,
                    "away_score": None,
                    "home_team": None,
                    "home_score": None,
                    "title": game.title,
                    "url": game.url,
                    "raw_sections": [],
                    "error": str(exc),
                }
            output_games.append(payload)

        canonical = {
            "source_url": INDEX_URL,
            "fetched_at_utc": fetched_at,
            "games": output_games,
        }
        canonical["payload_hash"] = _stable_hash(canonical)
        return canonical


def scrape_nba_rotations(max_games: int | None = None) -> dict[str, Any]:
    scraper = NBARotationsScraper()
    return scraper.scrape(max_games=max_games)


def _extract_json_array(text: str, start_index: int) -> str | None:
    if start_index < 0 or start_index >= len(text) or text[start_index] != "[":
        return None

    depth = 0
    in_string = False
    escaped = False

    for i in range(start_index, len(text)):
        ch = text[i]

        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start_index : i + 1]

    return None


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def save_payload(payload: dict[str, Any], base_dir: Path | str = "data") -> tuple[Path, Path]:
    base = Path(base_dir)
    hist = base / "history"
    hist.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    history_path = hist / f"{ts}.json"
    latest_path = base / "latest.json"

    history_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    latest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return latest_path, history_path
