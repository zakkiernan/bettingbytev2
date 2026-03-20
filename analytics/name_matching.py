from __future__ import annotations

import re
import unicodedata


_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
_TRANSLITERATION_REPLACEMENTS = {
    "Đ": "Dj",
    "đ": "dj",
    "Ł": "L",
    "ł": "l",
    "Ø": "O",
    "ø": "o",
    "Æ": "Ae",
    "æ": "ae",
    "Œ": "Oe",
    "œ": "oe",
    "ß": "ss",
}

# Keep aliases small and auditable. These entries come from the local injury audit.
PLAYER_NAME_ALIASES: dict[str, str] = {
    "hansen yang": "yang hansen",
}


def normalize_name(name: str) -> str:
    transliterated = "".join(_TRANSLITERATION_REPLACEMENTS.get(char, char) for char in name)
    ascii_name = unicodedata.normalize("NFKD", transliterated).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", ascii_name.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def candidate_name_keys(name: str) -> list[str]:
    normalized = normalize_name(name)
    if not normalized:
        return []

    tokens = normalized.split()
    raw_tokens = _raw_word_tokens(name)
    base_forms: list[str] = []

    _append_unique(base_forms, normalized)
    _append_unique(base_forms, _collapse_leading_initials(tokens))
    _append_unique(base_forms, _expand_leading_initials(tokens, raw_tokens))
    _append_alias_forms(base_forms, normalized)

    keys: list[str] = []
    for form in base_forms:
        form_tokens = form.split()
        while form_tokens:
            _append_unique(keys, " ".join(form_tokens))
            if form_tokens[-1] not in _SUFFIXES:
                break
            form_tokens = form_tokens[:-1]
    return keys


def _append_unique(keys: list[str], candidate: str | None) -> None:
    if candidate and candidate not in keys:
        keys.append(candidate)


def _append_alias_forms(base_forms: list[str], normalized: str) -> None:
    alias_targets: list[str] = []
    _append_unique(alias_targets, PLAYER_NAME_ALIASES.get(normalized))

    tokens = normalized.split()
    while tokens and tokens[-1] in _SUFFIXES:
        tokens = tokens[:-1]
        if not tokens:
            break
        _append_unique(alias_targets, PLAYER_NAME_ALIASES.get(" ".join(tokens)))

    for alias_target in alias_targets:
        _append_unique(base_forms, alias_target)
        _append_unique(base_forms, _collapse_leading_initials(alias_target.split()))


def _raw_word_tokens(name: str) -> list[str]:
    transliterated = "".join(_TRANSLITERATION_REPLACEMENTS.get(char, char) for char in name)
    ascii_name = unicodedata.normalize("NFKD", transliterated).encode("ascii", "ignore").decode("ascii")
    return re.findall(r"[A-Za-z0-9]+", ascii_name)


def _collapse_leading_initials(tokens: list[str]) -> str | None:
    leading_initial_count = 0
    for token in tokens:
        if len(token) == 1 and token.isalpha():
            leading_initial_count += 1
            continue
        break
    if leading_initial_count < 2:
        return None
    return " ".join(["".join(tokens[:leading_initial_count]), *tokens[leading_initial_count:]])


def _expand_leading_initials(tokens: list[str], raw_tokens: list[str]) -> str | None:
    if not tokens or not raw_tokens:
        return None

    normalized_first = tokens[0]
    raw_first = raw_tokens[0]
    if (
        len(normalized_first) != 2
        or not normalized_first.isalpha()
        or len(raw_first) != 2
        or not raw_first.isalpha()
        or not raw_first.isupper()
    ):
        return None
    return " ".join([normalized_first[0], normalized_first[1], *tokens[1:]])
