# apps/translations/services/llm_humanize.py

import logging
from django.conf import settings

from apps.translations.services.prompt_builder import build_humanize_prompt
from apps.translations.services.language_hints import get_language_hints

logger = logging.getLogger(__name__)


# Extract text from LLM response ----------------------------------------------
def _extract_text_from_chat(resp) -> str:
    try:
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""


# Humanize translation --------------------------------------------------------
def humanize_translation(
    *,
    source_text: str,
    translated_text: str,
    target_language: str,
) -> dict:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing")

    model = settings.OPENAI_TRANSLATION_MODEL
    prompt_version = settings.TRANSLATIONS_HUMANIZE_PROMPT_VERSION

    language_hints = get_language_hints(target_language)

    messages = build_humanize_prompt(
        source_text=source_text,
        translated_text=translated_text,
        target_language=target_language,
        language_hints=language_hints,
    )

    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
    )

    final_text = _extract_text_from_chat(resp)
    if not final_text:
        raise RuntimeError("Empty LLM output")

    return {
        "text": final_text,
        "model": model,
        "prompt_version": prompt_version,
    }
