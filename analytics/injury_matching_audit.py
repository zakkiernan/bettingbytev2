from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any

from analytics.name_matching import candidate_name_keys, normalize_name
from database.db import session_scope
from database.models import OfficialInjuryReportEntry, Player

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def _legacy_normalize_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", ascii_name.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _legacy_candidate_name_keys(name: str) -> list[str]:
    normalized = _legacy_normalize_name(name)
    if not normalized:
        return []
    keys = [normalized]
    tokens = normalized.split()
    while tokens and tokens[-1] in _SUFFIXES:
        tokens = tokens[:-1]
        if tokens:
            candidate = " ".join(tokens)
            if candidate not in keys:
                keys.append(candidate)
    return keys


def _safe_text(value: str | None) -> str:
    return (value or "").encode("ascii", "backslashreplace").decode("ascii")


def _player_rows() -> list[dict[str, Any]]:
    with session_scope() as session:
        players = session.query(Player.player_id, Player.full_name).all()
    rows: list[dict[str, Any]] = []
    for player_id, full_name in players:
        normalized_name = normalize_name(full_name)
        rows.append(
            {
                "player_id": str(player_id),
                "full_name": str(full_name),
                "safe_full_name": _safe_text(str(full_name)),
                "normalized_name": normalized_name,
                "tokens": tuple(normalized_name.split()),
            }
        )
    return rows


def _closest_player_match(player_name: str, players: list[dict[str, Any]]) -> dict[str, Any] | None:
    target_tokens = tuple(normalize_name(player_name).split())
    if not target_tokens:
        return None

    best_match: dict[str, Any] | None = None
    best_score = 0.0
    target_token_set = set(target_tokens)
    for player in players:
        player_tokens = player["tokens"]
        if not player_tokens:
            continue
        shared_tokens = target_token_set & set(player_tokens)
        score = len(shared_tokens) / max(len(target_tokens), len(player_tokens))
        if score <= best_score:
            continue
        best_score = score
        best_match = {
            "player_id": player["player_id"],
            "full_name": player["safe_full_name"],
            "normalized_name": player["normalized_name"],
            "score": round(score, 4),
        }
    return best_match


def _classify_unmatched_name(player_name: str, closest_match: dict[str, Any] | None) -> str:
    if closest_match is None:
        return "player_not_in_db"

    normalized_name = normalize_name(player_name)
    name_tokens = normalized_name.split()
    closest_tokens = str(closest_match.get("normalized_name") or "").split()
    if not closest_tokens:
        return "player_not_in_db"
    if set(name_tokens) == set(closest_tokens) and name_tokens != closest_tokens:
        return "name_order_mismatch"
    if closest_match.get("score", 0.0) >= 0.5:
        return "transliteration_or_alias_mismatch"
    return "player_not_in_db"


def build_injury_matching_audit() -> dict[str, Any]:
    with session_scope() as session:
        entries = session.query(OfficialInjuryReportEntry).all()

    players = _player_rows()
    unmatched_named_entries = [entry for entry in entries if not entry.player_id and entry.player_name]
    unmatched_counter = Counter(
        (
            str(entry.team_abbreviation or ""),
            str(entry.player_name or ""),
        )
        for entry in unmatched_named_entries
    )
    bucket_counts = Counter()
    examples_by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    top_unmatched: list[dict[str, Any]] = []

    for (team_abbreviation, player_name), count in unmatched_counter.most_common(50):
        closest_match = _closest_player_match(player_name, players)
        bucket = _classify_unmatched_name(player_name, closest_match)
        bucket_counts[bucket] += count
        example = {
            "team_abbreviation": team_abbreviation,
            "player_name": player_name,
            "count": count,
            "legacy_keys": _legacy_candidate_name_keys(player_name),
            "canonical_keys": candidate_name_keys(player_name),
            "closest_match": closest_match,
        }
        if len(examples_by_bucket[bucket]) < 10:
            examples_by_bucket[bucket].append(example)
        top_unmatched.append(example)

    total_entries = len(entries)
    entries_with_player_id = sum(1 for entry in entries if entry.player_id)
    entries_without_player_id = total_entries - entries_with_player_id
    named_entries = sum(1 for entry in entries if entry.player_name)
    named_entries_without_player_id = len(unmatched_named_entries)
    named_entries_with_player_id = named_entries - named_entries_without_player_id

    return {
        "total_entries": total_entries,
        "entries_with_player_id": entries_with_player_id,
        "entries_without_player_id": entries_without_player_id,
        "named_entries": named_entries,
        "named_entries_with_player_id": named_entries_with_player_id,
        "named_entries_without_player_id": named_entries_without_player_id,
        "top_unmatched": top_unmatched,
        "failure_bucket_distribution": dict(bucket_counts),
        "examples_by_bucket": dict(examples_by_bucket),
    }


def render_injury_matching_audit_markdown(audit: dict[str, Any]) -> str:
    total_entries = int(audit["total_entries"])
    entries_with_player_id = int(audit["entries_with_player_id"])
    entries_without_player_id = int(audit["entries_without_player_id"])
    named_entries = int(audit["named_entries"])
    named_entries_with_player_id = int(audit["named_entries_with_player_id"])
    named_entries_without_player_id = int(audit["named_entries_without_player_id"])
    bucket_distribution = audit["failure_bucket_distribution"]
    examples_by_bucket = audit["examples_by_bucket"]
    top_unmatched = audit["top_unmatched"]

    lines = [
        "# Injury Matching Audit",
        "",
        "## Coverage",
        f"- Total `official_injury_report_entries`: {total_entries}",
        f"- Entries with `player_id`: {entries_with_player_id} ({entries_with_player_id / total_entries:.2%})",
        f"- Entries with `player_id = NULL`: {entries_without_player_id} ({entries_without_player_id / total_entries:.2%})",
        f"- Named player entries: {named_entries}",
        f"- Named entries with `player_id`: {named_entries_with_player_id} ({named_entries_with_player_id / named_entries:.2%})",
        f"- Named entries with `player_id = NULL`: {named_entries_without_player_id} ({named_entries_without_player_id / named_entries:.2%})",
        "",
        "## Top Unmatched Names",
    ]

    if not top_unmatched:
        lines.append("- No unmatched named injury rows were found.")
    else:
        for row in top_unmatched[:50]:
            closest = row.get("closest_match") or {}
            closest_label = closest.get("full_name") or "None"
            closest_score = closest.get("score")
            lines.append(
                f"- `{row['team_abbreviation']} / {row['player_name']}`: {row['count']} rows; closest DB match `{closest_label}`"
                + (f" (token score {closest_score:.2f})" if closest_score is not None else "")
            )

    lines.extend(
        [
            "",
            "## Failure Bucket Distribution",
        ]
    )
    if not bucket_distribution:
        lines.append("- No unmatched named injury rows were found.")
    else:
        for bucket, count in sorted(bucket_distribution.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- `{bucket}`: {count}")

    lines.extend(
        [
            "",
            "## Bucket Examples",
        ]
    )
    for bucket, examples in sorted(examples_by_bucket.items()):
        lines.append(f"### {bucket}")
        for example in examples:
            closest = example.get("closest_match") or {}
            lines.append(f"- PDF name: `{example['player_name']}` ({example['team_abbreviation']})")
            lines.append(f"- Legacy ingestion keys: `{example['legacy_keys']}`")
            lines.append(f"- Canonical matcher keys: `{example['canonical_keys']}`")
            lines.append(
                f"- Closest DB match: `{closest.get('full_name') or 'None'}`"
                + (
                    f" with normalized form `{closest.get('normalized_name')}` and token score {closest.get('score', 0.0):.2f}"
                    if closest
                    else ""
                )
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"
