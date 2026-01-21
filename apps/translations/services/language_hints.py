# apps/translations/services/language_hints.py

from __future__ import annotations


# Minimal, soft hints only.
# Never used as hard replacement rules.

_LANGUAGE_HINTS: dict[str, list[str]] = {
    "fa": [
        "In Persian Christian usage, 'love' is often expressed as 'محبت' rather than 'عشق'.",
        "Use modern Persian, not formal or archaic religious language.",
    ],
    "ar": [
        "Prefer commonly used modern Arabic faith terms, avoid classical or sermon-like wording.",
    ],
    "en": [
        "Keep the tone modern and conversational, not sermon-like.",
    ],
}


def get_language_hints(target_language: str) -> list[str]:
    """
    Return optional soft language hints for the target language.
    """
    return _LANGUAGE_HINTS.get(target_language, []).copy()
