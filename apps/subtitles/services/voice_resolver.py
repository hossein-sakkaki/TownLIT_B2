# apps/subtitles/services/voice_resolver.py

from __future__ import annotations

from apps.accounts.constants import MALE, FEMALE
from apps.subtitles.constants import (
    DEFAULT_VOICE_BY_LANGUAGE,
    DEFAULT_VOICE_BY_LANGUAGE_GENDER,
    DEFAULT_SAFE_VOICE,
    OPENAI_TTS_ALLOWED_VOICES,
)

def canonical_lang(lang: str) -> str:
    return (lang or "").split("-")[0].strip().lower()

def normalize_gender(g: str | None) -> str:
    """
    Convert project gender ("Male"/"Female") to resolver gender ("male"/"female"/"")
    """
    if g == MALE:
        return "male"
    if g == FEMALE:
        return "female"
    return ""

def resolve_voice_id(*, target_language: str, owner_gender: str | None) -> str:
    """
    Always returns an explicit, valid OpenAI voice_id.
    - gender-aware if possible
    - never returns "default" or "auto"
    """
    lang = canonical_lang(target_language)
    g = normalize_gender(owner_gender)

    candidate = (
        (DEFAULT_VOICE_BY_LANGUAGE_GENDER.get(lang, {}).get(g) if g else None)
        or DEFAULT_VOICE_BY_LANGUAGE.get(lang)
        or DEFAULT_SAFE_VOICE
        or "nova"
    )

    candidate = (candidate or "").strip().lower()

    # Clamp to allowed voices (avoid 400 invalid_value)
    if candidate not in OPENAI_TTS_ALLOWED_VOICES:
        candidate = (DEFAULT_SAFE_VOICE or "nova").strip().lower()

    return candidate
