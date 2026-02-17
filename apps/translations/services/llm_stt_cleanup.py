# apps/translations/services/llm_stt_cleanup.py

from django.conf import settings
from openai import OpenAI
from apps.translations.services.prompt_builder_stt import build_stt_cleanup_prompt


def clean_stt_transcript(*, text: str, language: str) -> dict:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    messages = build_stt_cleanup_prompt(
        source_text=text,
        language=language,
    )

    resp = client.chat.completions.create(
        model=settings.OPENAI_STT_CLEANUP_MODEL,
        messages=messages,
        temperature=0.1,  # 🔑 very conservative
    )

    final_text = resp.choices[0].message.content.strip()
    if not final_text:
        raise RuntimeError("Empty STT cleanup output")

    return {
        "text": final_text,
        "model": settings.OPENAI_STT_CLEANUP_MODEL,
    }
