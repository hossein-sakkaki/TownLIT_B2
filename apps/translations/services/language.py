# apps/translations/services/language.py
from django.conf import settings

DEFAULT_GUEST_LANGUAGE = getattr(settings, "DEFAULT_GUEST_LANGUAGE", "en")


def resolve_target_language(
    *,
    user=None,
    source_language: str | None = None,
    override_language: str | None = None,
) -> str:
    """
    Decide target language using approved policy.
    """

    # Explicit user override always wins
    if override_language:
        return override_language

    # Logged-in user
    if user and user.is_authenticated:
        primary = getattr(user, "primary_language", None)
        secondary = getattr(user, "secondary_language", None)

        # Prefer translating away from source language
        if source_language and secondary and source_language == primary:
            return secondary

        return primary or DEFAULT_GUEST_LANGUAGE

    # Guest fallback
    return DEFAULT_GUEST_LANGUAGE
