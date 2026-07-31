# apps/translations/services/language.py

from __future__ import annotations

from functools import lru_cache

from django.conf import settings

from apps.translations.services.language_codes import (
    normalize_language_code,
)
from apps.translations.services.supported_languages import (
    get_supported_languages,
)


DEFAULT_GUEST_LANGUAGE = getattr(
    settings,
    "DEFAULT_GUEST_LANGUAGE",
    "en",
)

DEFAULT_SOURCE_LANGUAGE = "en"


def _comparison_code(
    value: str | None,
) -> str:
    """
    Normalize a language code for comparisons.
    """

    normalized = normalize_language_code(
        value,
    )

    return normalized.replace(
        "_",
        "-",
    ).lower()


@lru_cache(maxsize=1)
def get_supported_language_code_map() -> dict[str, str]:
    """
    Map normalized language codes to canonical configured codes.

    Examples:
        fa-af -> fa-AF
        fr-ca -> fr-CA
        zh-tw -> zh-TW
    """

    result: dict[str, str] = {}

    for language in get_supported_languages():
        canonical_code = str(
            language.get("code") or ""
        ).strip()

        normalized_code = _comparison_code(
            canonical_code,
        )

        if canonical_code and normalized_code:
            result[normalized_code] = canonical_code

    return result


def canonical_supported_language(
    value: str | None,
) -> str | None:
    """
    Return the canonical supported code for a language value.
    """

    normalized = _comparison_code(
        value,
    )

    if not normalized:
        return None

    return get_supported_language_code_map().get(
        normalized,
    )


def is_supported_language(
    value: str | None,
) -> bool:
    """
    Check whether a language is supported.
    """

    return (
        canonical_supported_language(
            value,
        )
        is not None
    )


def language_codes_match(
    first: str | None,
    second: str | None,
) -> bool:
    """
    Compare language codes safely.
    """

    first_code = _comparison_code(
        first,
    )
    second_code = _comparison_code(
        second,
    )

    return bool(
        first_code
        and second_code
        and first_code == second_code
    )


def resolve_default_language() -> str:
    """
    Resolve a safe application default language.
    """

    return (
        canonical_supported_language(
            DEFAULT_GUEST_LANGUAGE,
        )
        or DEFAULT_SOURCE_LANGUAGE
    )


def resolve_user_primary_language(
    *,
    user,
    fallback_language: str | None = None,
) -> str:
    """
    Resolve the authenticated user's primary language.

    Missing or unsupported values safely fall back to English
    or the supplied supported fallback.
    """

    fallback = (
        canonical_supported_language(
            fallback_language,
        )
        or resolve_default_language()
    )

    if user is None:
        return fallback

    if not getattr(
        user,
        "is_authenticated",
        False,
    ):
        return fallback

    primary_language = (
        canonical_supported_language(
            getattr(
                user,
                "primary_language",
                None,
            )
        )
    )

    return primary_language or fallback


def resolve_target_language(
    *,
    user=None,
    source_language: str | None = None,
    override_language: str | None = None,
) -> str:
    """
    Resolve a valid translation target language.

    Policy:
    - A supported explicit override wins.
    - Authenticated users use their primary language.
    - If source equals primary, a supported secondary language may be used.
    - Missing or unsupported values fall back safely.
    """

    override = canonical_supported_language(
        override_language,
    )

    if override:
        return override

    fallback = resolve_default_language()

    if user and getattr(
        user,
        "is_authenticated",
        False,
    ):
        primary = canonical_supported_language(
            getattr(
                user,
                "primary_language",
                None,
            )
        )

        secondary = canonical_supported_language(
            getattr(
                user,
                "secondary_language",
                None,
            )
        )

        if (
            source_language
            and primary
            and secondary
            and language_codes_match(
                source_language,
                primary,
            )
        ):
            return secondary

        return primary or fallback

    return fallback