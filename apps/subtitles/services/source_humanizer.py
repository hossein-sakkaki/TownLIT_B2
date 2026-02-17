# apps/subtitles/services/source_humanizer.py

from __future__ import annotations
import logging

from django.conf import settings

from apps.translations.services.llm_humanize import humanize_translation
from apps.translations.services.language_hints import get_language_hints
from apps.subtitles.services.prompt_builder_transcript import build_transcript_humanize_prompt

logger = logging.getLogger(__name__)
 


def humanize_transcript_text(*, text: str, language: str) -> str:
    # Fail-safe transcript cleanup
    if not text or not text.strip():
        return text

    if not getattr(settings, "SUBTITLES_HUMANIZE_SOURCE_ENABLED", True):
        return text

    if not settings.OPENAI_API_KEY:
        logger.warning("[subtitles] OPENAI_API_KEY missing; skipping humanize")
        return text

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        model = getattr(settings, "OPENAI_TRANSCRIPT_HUMANIZE_MODEL", None) or getattr(
            settings, "OPENAI_TRANSLATION_MODEL", "gpt-4o-mini"
        )

        messages = build_transcript_humanize_prompt(
            language=language or "en",
            raw_text=text,
        )

        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
        )

        out = (resp.choices[0].message.content or "").strip()
        if not out:
            return text

        return out

    except Exception:
        logger.exception("[subtitles] transcript humanize failed")
        return text
