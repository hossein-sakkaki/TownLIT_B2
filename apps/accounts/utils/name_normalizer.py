# apps/accounts/utils/name_normalizer.py

import re
from typing import Optional


# Common particles in Western names (keep lowercase when not first word)
# Short list on purpose (safe / minimal)
_LOWER_PARTICLES = {
    "de", "del", "della", "der", "den", "di", "da", "dos", "du",
    "la", "le", "van", "von", "bin", "ibn", "al", "el",
}


def _collapse_spaces(value: str) -> str:
    # Trim + collapse repeated whitespace
    return re.sub(r"\s+", " ", value.strip())


def _capitalize_word(word: str) -> str:
    # Basic English-like capitalization
    if not word:
        return word
    return word[0].upper() + word[1:].lower()


def normalize_person_name(value: Optional[str]) -> Optional[str]:
    """
    Normalize personal names for storage:
    - Keep multi-word names (space-separated)
    - Trim and collapse extra spaces
    - Title-case each token: "abas abadi" -> "Abas Abadi"
    - Keep certain particles lowercase when NOT the first word: "van der sar" -> "Van der Sar"
    Notes:
    - Conservative: does not try to be perfect for all cultures.
    - If value is None/empty -> returns as-is.
    """
    if value is None:
        return None

    raw = _collapse_spaces(value)
    if raw == "":
        return ""

    parts = raw.split(" ")

    out = []
    for i, p in enumerate(parts):
        token = p.strip()
        if token == "":
            continue

        lower = token.lower()

        # Keep particles lowercase if not the first word
        if i != 0 and lower in _LOWER_PARTICLES:
            out.append(lower)
            continue

        out.append(_capitalize_word(token))

    return " ".join(out)
