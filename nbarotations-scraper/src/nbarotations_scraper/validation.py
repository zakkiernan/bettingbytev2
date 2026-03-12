from __future__ import annotations

from typing import Any


REQUIRED_TOP_KEYS = {"source_url", "fetched_at_utc", "games", "payload_hash"}
REQUIRED_GAME_KEYS = {
    "game_id",
    "date_label",
    "away_team",
    "away_score",
    "home_team",
    "home_score",
    "title",
    "url",
    "raw_sections",
}


def validate_payload(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a full scrape payload."""
    errors: list[str] = []
    warnings: list[str] = []

    top_missing = REQUIRED_TOP_KEYS - set(payload.keys())
    if top_missing:
        errors.append(f"missing top-level keys: {sorted(top_missing)}")

    games = payload.get("games")
    if not isinstance(games, list):
        errors.append("games is not a list")
        return errors, warnings

    if not games:
        warnings.append("games list is empty")
        return errors, warnings

    seen_ids: set[str] = set()
    for i, game in enumerate(games):
        g_errors, g_warnings = validate_game(game, index=i)
        errors.extend(g_errors)
        warnings.extend(g_warnings)

        game_id = game.get("game_id")
        if isinstance(game_id, str):
            if game_id in seen_ids:
                errors.append(f"duplicate game_id: {game_id}")
            seen_ids.add(game_id)

    return errors, warnings


def validate_game(game: dict[str, Any], index: int | None = None) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for one game payload."""
    prefix = f"game[{index}]" if index is not None else f"game[{game.get('game_id', '?')}]"
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(game, dict):
        return [f"{prefix}: not an object"], warnings

    missing = REQUIRED_GAME_KEYS - set(game.keys())
    if missing:
        errors.append(f"{prefix}: missing keys {sorted(missing)}")

    # If the scraper explicitly stored an error, keep as warning (partial fetch behavior is expected).
    if game.get("error"):
        warnings.append(f"{prefix}: scrape error present: {game.get('error')}")

    sections = game.get("raw_sections")
    if not isinstance(sections, list):
        errors.append(f"{prefix}: raw_sections is not a list")
        return errors, warnings

    display_sections = [s for s in sections if isinstance(s, dict) and s.get("section_type") == "display_game"]
    if not display_sections:
        warnings.append(f"{prefix}: no display_game sections found")
        return errors, warnings

    sides = {s.get("side") for s in display_sections}
    if sides != {"away", "home"}:
        warnings.append(f"{prefix}: expected away+home display sections, got {sorted(str(x) for x in sides)}")

    for sec in display_sections:
        side = sec.get("side")
        players = sec.get("players")
        if not isinstance(players, list):
            errors.append(f"{prefix}:{side}: players is not a list")
            continue

        hist_lens: set[int] = set()
        for p_idx, p in enumerate(players):
            if not isinstance(p, dict):
                errors.append(f"{prefix}:{side}: player[{p_idx}] is not an object")
                continue

            hist = p.get("histogram")
            if not isinstance(hist, list):
                errors.append(f"{prefix}:{side}: player[{p_idx}] histogram not list")
                continue

            hist_lens.add(len(hist))
            for v_idx, v in enumerate(hist):
                if not isinstance(v, (int, float)):
                    errors.append(f"{prefix}:{side}: player[{p_idx}] histogram[{v_idx}] non-numeric")
                    break
                if v < -1e-9 or v > 1 + 1e-9:
                    errors.append(f"{prefix}:{side}: player[{p_idx}] histogram[{v_idx}] out of range {v}")
                    break

        if len(hist_lens) > 1:
            errors.append(f"{prefix}:{side}: inconsistent histogram lengths {sorted(hist_lens)}")
        elif hist_lens and next(iter(hist_lens)) != 48:
            warnings.append(f"{prefix}:{side}: histogram length {next(iter(hist_lens))} (expected 48 regulation buckets)")

        # Validate lineup conservation if lengths are present.
        if players and hist_lens:
            h_len = next(iter(hist_lens))
            for minute_idx in range(h_len):
                minute_sum = 0.0
                valid = True
                for p in players:
                    hist = p.get("histogram")
                    if not isinstance(hist, list) or len(hist) <= minute_idx:
                        valid = False
                        break
                    minute_sum += float(hist[minute_idx])
                if not valid:
                    break
                if abs(minute_sum - 5.0) > 0.05:
                    warnings.append(
                        f"{prefix}:{side}: minute[{minute_idx}] occupancy sum={minute_sum:.3f} (expected ~5.0)"
                    )
                    break

    return errors, warnings
