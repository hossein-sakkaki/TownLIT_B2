# apps/translations/services/language_hints.py

from __future__ import annotations


_LANGUAGE_HINTS: dict[str, list[str]] = {
    "fa": [
        (
            "Use natural contemporary Persian suitable for an app interface. "
            "Avoid literal English sentence structures."
        ),
        (
            "Prefer warm, clear, everyday Persian over formal, academic, "
            "bureaucratic, or machine-translated wording."
        ),
        (
            "In Persian Christian usage, use 'محبت' rather than 'عشق' "
            "when the source refers to spiritual or caring love."
        ),
        (
            "Use natural Persian pronouns and verb forms. Do not preserve "
            "English word order when it sounds unnatural in Persian."
        ),
    ],
    "ar": [
        (
            "Use natural modern Arabic suitable for an app interface. "
            "Avoid literal English structures and unnecessarily classical wording."
        ),
    ],
    "en": [
        (
            "Keep the tone modern, clear, warm, and conversational."
        ),
    ],
}


def _base_language_code(
    value: str | None,
) -> str:
    """
    Resolve the base BCP-47 language code.
    """

    return (
        str(
            value or ""
        )
        .strip()
        .replace(
            "_",
            "-",
        )
        .lower()
        .split(
            "-",
            1,
        )[0]
    )


def get_language_hints(
    target_language: str,
) -> list[str]:
    """
    Return soft hints for a target language.
    """

    base_code = _base_language_code(
        target_language
    )

    return _LANGUAGE_HINTS.get(
        base_code,
        [],
    ).copy()