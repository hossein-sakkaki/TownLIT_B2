# apps/subtitles/services/tts_openai.py

from __future__ import annotations

import os
import tempfile
import hashlib
from typing import Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage

from openai import OpenAI

from apps.subtitles.constants import (
    VOICE_ENABLED_LANGUAGES,
    DEFAULT_VOICE_BY_LANGUAGE,
    DEFAULT_SAFE_VOICE,
    OPENAI_TTS_ALLOWED_VOICES,
    DEFAULT_VOICE_BY_LANGUAGE_GENDER,
)

# ------------------------------------------------------------------
# Cache (prevents repeated paid TTS calls)
# ------------------------------------------------------------------
TTS_CACHE_TTL = 60 * 60 * 24 * 60  # 60 days


# ------------------------------------------------------------------
# Language helpers
# ------------------------------------------------------------------
def _normalize_lang(language: str) -> str:
    if not language or language in ("default", "auto"):
        raise ValueError("Invalid TTS language")
    return language.strip()


def _canonical_lang(lang: str) -> str:
    # fr-CA -> fr, zh-TW -> zh
    return (lang or "").split("-")[0].strip().lower()


def _is_voice_language_enabled(language: str) -> bool:
    """
    Gate TTS by canonical language.
    """
    if not VOICE_ENABLED_LANGUAGES:
        return True

    canon = _canonical_lang(language)
    allowed = {_canonical_lang(x) for x in VOICE_ENABLED_LANGUAGES}
    return canon in allowed


# ------------------------------------------------------------------
# Voice resolver (deterministic & safe)
# ------------------------------------------------------------------
def _resolve_voice_id(
    *,
    language: str,
    voice_id: str | None,
    gender: str | None = None,
) -> str:
    """
    Deterministic voice resolver.
    RULE:
    - If gender is known -> NEVER fall back to gender-agnostic voices
    - If gender unknown -> language default
    """

    lang = _canonical_lang(_normalize_lang(language))
    raw = (voice_id or "").strip().lower()

    # Normalize gender
    g = (gender or "").strip().lower()
    if g not in ("male", "female"):
        g = None

    # 1) Explicit voice always wins
    if raw and raw in OPENAI_TTS_ALLOWED_VOICES:
        return raw

    # 2) Gender-aware (STRICT)
    if g:
        gender_map = DEFAULT_VOICE_BY_LANGUAGE_GENDER.get(lang)
        if gender_map:
            candidate = gender_map.get(g)
            if candidate in OPENAI_TTS_ALLOWED_VOICES:
                return candidate

        # Absolute gender fallback (language-agnostic but gender-safe)
        return "onyx" if g == "male" else "nova"

    # 3) Gender unknown -> language default
    candidate = DEFAULT_VOICE_BY_LANGUAGE.get(lang)
    if candidate in OPENAI_TTS_ALLOWED_VOICES:
        return candidate

    # 4) Final safety
    return DEFAULT_SAFE_VOICE or "nova"


# ------------------------------------------------------------------
# Cache helpers
# ------------------------------------------------------------------
def _tts_cache_key(
    *,
    text: str,
    language: str,
    voice_id: str,
    gender: str | None,
) -> str:
    raw = f"{language}|{voice_id}|{gender or ''}|{text}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"tts:{h}"


# ------------------------------------------------------------------
# Local TTS (used by timeline builder)
# ------------------------------------------------------------------
def synthesize_speech_to_local_mp3(
    *,
    text: str,
    language: str,
    voice_id: str | None,
    gender: str | None = None,
    out_dir: str,
    name_hint: str = "seg",
) -> str:
    """
    Generate local mp3 with aggressive cache.
    NEVER re-calls OpenAI for identical input.
    """

    lang = _normalize_lang(language)

    # Gate by canonical language
    if not _is_voice_language_enabled(lang):
        raise ValueError(f"TTS is not enabled for language: {lang}")

    resolved_voice = _resolve_voice_id(
        language=lang,
        voice_id=voice_id,
        gender=gender,
    )

    # ---------- CACHE ----------
    cache_key = _tts_cache_key(
        text=text or "",
        language=lang,
        voice_id=resolved_voice,
        gender=gender,
    )

    cached_path = cache.get(cache_key)
    if cached_path and os.path.exists(cached_path):
        return cached_path

    # ---------- OPENAI TTS ----------
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    response = client.audio.speech.create(
        model=settings.OPENAI_TTS_MODEL,
        voice=resolved_voice,
        input=text or "",
    )

    os.makedirs(out_dir, exist_ok=True)
    tmp_path = os.path.join(out_dir, f"{name_hint}.mp3")

    with open(tmp_path, "wb") as f:
        f.write(response.read())

    # Cache local file path
    cache.set(cache_key, tmp_path, TTS_CACHE_TTL)

    return tmp_path


# ------------------------------------------------------------------
# Storage-based TTS (legacy / direct usage)
# ------------------------------------------------------------------
def synthesize_speech(
    *,
    text: str,
    language: str,
    voice_id: str | None,
    gender: str | None = None,
) -> Tuple[str, Optional[int]]:
    """
    Generate TTS and store in default_storage.
    Used only if you ever need non-timeline TTS.
    """

    lang = _normalize_lang(language)

    if not _is_voice_language_enabled(lang):
        raise ValueError(f"TTS is not enabled for language: {lang}")

    resolved_voice = _resolve_voice_id(
        language=lang,
        voice_id=voice_id,
        gender=gender,
    )

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    response = client.audio.speech.create(
        model=settings.OPENAI_TTS_MODEL,
        voice=resolved_voice,
        input=text or "",
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp.write(response.read())
        tmp.flush()
        tmp_path = tmp.name

    try:
        filename = os.path.basename(tmp_path)
        storage_path = f"subtitles/voice/{filename}"

        with open(tmp_path, "rb") as rf:
            default_storage.save(storage_path, rf)

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return storage_path, None
