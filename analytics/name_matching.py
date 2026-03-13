from __future__ import annotations

import re
import unicodedata


_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
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


def _raw_word_tokens(name: str) -> list[str]:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
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
